#!/usr/bin/env python3
"""Analisa o CSV do driver do canal: latency por rodada.

Para cada limiar de classificacao (hit/miss), computa a sequencia recebida e
o erro em relacao a enviada (edit distance / Levenshtein, equivalente ao
Xiong). Gera tambem um PNG de apoyo (dispersao das latencias por bit).

Uso:
  analyze.py --csv file.csv [--png out.png]
"""

import argparse
import csv
import io
import sys


def edit_distance(a, b):
    """Levenshtein entre duas strings de bits."""
    if len(a) < len(b):
        a, b = b, a
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a):
        cur = [i + 1]
        for j, cb in enumerate(b):
            cur.append(
                min(prev[j + 1] + 1, cur[j] + 1, prev[j] + (ca != cb))
            )
        prev = cur
    return prev[len(b)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True)
    ap.add_argument("--png", default=None)
    args = ap.parse_args()

    rounds, bits, lats = [], [], []
    clean = io.StringIO()
    with open(args.csv, newline="") as f:
        for line in f:
            if not line.lstrip().startswith("#"):
                clean.write(line)
        clean.seek(0)
        for r in csv.DictReader(clean):
            rounds.append(int(r["round"]))
            bits.append(int(r["bit"]))
            lats.append(int(r["lat_cycles"]))

    sent = "".join(str(b) for b in bits)
    near = list(range(min(lats), max(lats) + 1))

    best = None
    for th in near:
        # Protocolo do driver 2-fios: bit 1 = transmissor evictou a vitima
        # da cache compartilhada (miss => latencia alta); bit 0 = vitima
        # presente (hit => latencia baixa).
        recv = "".join("1" if l >= th else "0" for l in lats)
        e = edit_distance(sent, recv)
        if best is None or e < best[0]:
            best = (e, th)

    n1 = sum(bits)
    n0 = len(bits) - n1
    avg1 = sum(l for b, l in zip(bits, lats) if b == 1) / max(n1, 1)
    avg0 = sum(l for b, l in zip(bits, lats) if b == 0) / max(n0, 1)

    print(f"nbits={len(bits)} (1={n1}, 0={n0})")
    print(f"latency  bit=1: avg={avg1:.1f}  bit=0: avg={avg0:.1f}")
    print(f"best threshold={best[1]}  edit_distance={best[0]}"
          f"  ({best[0]}/{len(bits)} bits)")
    if best[0] == 0:
        print("=> erro zero: canal decodificado perfeitamente neste limiar")

    if args.png:
        try:
            import matplotlib

            matplotlib.use("Agg")
            import matplotlib.pyplot as plt

            plt.figure(figsize=(8, 4))
            xs = [i for i, b in enumerate(bits)]
            plt.scatter(
                [x for x, b in zip(xs, bits) if b == 1],
                [l for l, b in zip(lats, bits) if b == 1],
                c="tab:green", s=12, label="bit=1 (envia 1)",
            )
            plt.scatter(
                [x for x, b in zip(xs, bits) if b == 0],
                [l for l, b in zip(lats, bits) if b == 0],
                c="tab:red", s=12, label="bit=0 (envia 0)",
            )
            plt.axhline(best[1], color="k", ls="--", lw=1,
                        label=f"limiar={best[1]}")
            plt.xlabel("rodada")
            plt.ylabel("latencia (ciclos)")
            plt.legend()
            plt.tight_layout()
            plt.savefig(args.png, dpi=150)
            print(f"plot salvos em {args.png}")
        except ImportError:
            print("matplotlib nao instalado; pulando plot", file=sys.stderr)


if __name__ == "__main__":
    main()