#!/usr/bin/env python3
"""Varredura de metricas do canal (Etapa 2): erro x parametros x taxa.

Para cada configuracao, roda o gem5 com o driver, extrai a latencia por bit
(analyze.py) e a taxa de transmissao efetiva:
    taxa = nbits / (tick_simulado)
onde tick_simulado vem da linha "Simulation end reached @ tick N" do gem5
(tick = ps). Taxa em Kbps (bits/segundo/1000).

O F6 (alg=3) roda o driver 2-fios em SMT (1 core, numThreads=2, L1
compartilhada, Prime+Probe): usa --num-threads 2 --num-cores 1 e o binario
channel_2t_dyn. O marketing das colunas e o mesmo do fio unico.

Uso: sweep.py [--out tsv]
"""

import argparse
import csv
import re
import subprocess
import sys

WORK = "/home/ads/Projects/puc/ac3"
GEM5 = f"{WORK}/sim/gem5/build/X86/gem5.opt"
CFG = f"{WORK}/sim/configs/config_channel.py"
CH = f"{WORK}/sim/results/bin/channel"
CH2T = f"{WORK}/sim/results/bin/channel_2t_dyn"
AN = f"{WORK}/sim/scripts/analyze.py"
PY = f"{WORK}/sim/.venv/bin/python"
NBITS = 64
PS_PER_S = 1e12

CONFIGS_SINGLE = [
    {"name": "lru_all_a1_d4", "policy": "lru", "scope": "all", "alg": 1, "d": 4},
    {"name": "lru_all_a1_d8", "policy": "lru", "scope": "all", "alg": 1, "d": 8},
    {"name": "lru_all_a1_d12", "policy": "lru", "scope": "all", "alg": 1, "d": 12},
    {"name": "srrrip_all_a1_d8", "policy": "srrrip", "scope": "all", "alg": 1, "d": 8},
    {"name": "lru_llc_a1_d8", "policy": "lru", "scope": "llc", "alg": 1, "d": 8},
    {"name": "lru_all_a2_d8", "policy": "lru", "scope": "all", "alg": 2, "d": 8},
]

CONFIGS_2T = [
    {"name": "f6_smt_lru_d8", "policy": "lru", "scope": "smt_l1", "alg": 3, "d": 8},
    {"name": "f6_smt_srrrip_d8", "policy": "srrrip", "scope": "smt_l1", "alg": 3, "d": 8},
    {"name": "f6_smt_rrrip_d8", "policy": "rrrip", "scope": "smt_l1", "alg": 3, "d": 8},
    {"name": "f6_smt_brrip_d8", "policy": "brrip", "scope": "smt_l1", "alg": 3, "d": 8},
    {"name": "f6_smt_lru_d4", "policy": "lru", "scope": "smt_l1", "alg": 3, "d": 4},
    {"name": "f6_smt_lru_d16", "policy": "lru", "scope": "smt_l1", "alg": 3, "d": 16},
]


def run_gem5(name, cfg, tmpdir):
    if cfg["alg"] == 3:
        cmd = [GEM5, "-d", tmpdir, CFG,
               "--binary", CH2T,
               "--cpu-type", "timing",
               "--num-threads", "2", "--num-cores", "1",
               "--policy", cfg["policy"], "--policy-scope", "l1",
               "--cmdargs", f"--out {tmpdir}/{name}.csv -d {cfg['d']}"]
    else:
        cmd = [GEM5, "-d", tmpdir, CFG,
               "--binary", CH, "--cpu-type", "timing",
               "--policy", cfg["policy"], "--policy-scope", cfg["scope"],
               "--cmdargs",
               f"--out {tmpdir}/{name}.csv --alg {cfg['alg']} -d {cfg['d']}"]
    out = subprocess.run(cmd, capture_output=True, text=True)
    m = re.search(r"Simulation end reached @ tick (\d+)", out.stdout)
    tick = int(m.group(1)) if m else None
    return tick


def analyze(name, tmpdir):
    csv_path = f"{tmpdir}/{name}.csv"
    r = subprocess.run(
        [PY, AN, "--csv", csv_path, "--png", f"{tmpdir}/{name}.png"],
        capture_output=True, text=True,
    )
    dist = None
    for line in r.stdout.splitlines():
        m = re.search(r"edit_distance=(\d+)", line)
        if m:
            dist = m.group(1)
    return dist, r.stdout


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=f"{WORK}/sim/results/runs/metrics.tsv")
    args = ap.parse_args()

    rows = []
    configs = CONFIGS_SINGLE + CONFIGS_2T
    for cfg in configs:
        tmpdir = subprocess.run(["/usr/bin/mktemp", "-d"],
                                capture_output=True, text=True).stdout.strip()
        tick = run_gem5(cfg["name"], cfg, tmpdir)
        dist, _ = analyze(cfg["name"], tmpdir)
        errors = int(dist.strip()) if dist else None
        rate_kbps = (NBITS / (tick / PS_PER_S)) / 1e3 if tick else None
        rows.append({**cfg, "tick": tick, "errors": errors,
                     "rate_kbps": rate_kbps,
                     "err_per_bit": (errors / NBITS) if errors is not None else None})
        print(f"{cfg['name']:24s} tick={tick:>12d} err={errors:>3}/{NBITS} "
              f"rate={rate_kbps:8.2f} Kbps")
        subprocess.run(["/usr/bin/rm", "-rf", tmpdir])

    with open(args.out, "w", newline="") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow(["name", "policy", "scope", "alg", "d", "tick_ps",
                    "errors", "rate_kbps", "err_per_bit"])
        for r in rows:
            w.writerow([r["name"], r["policy"], r["scope"], r["alg"], r["d"],
                        r["tick"], r["errors"],
                        f"{r['rate_kbps']:.3f}" if r["rate_kbps"] else "",
                        r["err_per_bit"]])
    print(f"tabela: {args.out}")


if __name__ == "__main__":
    main()