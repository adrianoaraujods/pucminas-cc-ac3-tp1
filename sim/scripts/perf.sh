#!/usr/bin/env bash
# Frente de desempenho (Etapa 3): IPC / miss rates do microbenchmark scan
# sob LRU x SRRIP (scopes l2llc e all), extraidos do stats.txt do gem5.
# Uso: scripts/perf.sh [maxticks] [outdir]   (default maxticks=30e9 ~ 2.9M instrs)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GEM5="$ROOT/gem5/build/X86/gem5.opt"
CONFIG="$ROOT/configs/config_channel.py"
SCAN="$ROOT/results/bin/scan"
PY="$ROOT/.venv/bin/python"

MAXTICKS=30000000000
[ $# -ge 1 ] && MAXTICKS="$1"
OUT="${2:-$ROOT/results/runs/perf}"
mkdir -p "$OUT"
TSV="$OUT/perf.tsv"

extract() { # stats.txt name -> val
    "$PY" - "$1" "$2" <<'EOF'
import re, sys
path, name = sys.argv[1], sys.argv[2]
pat = re.compile(rf"^\s*{re.escape(name)}\s+([\d.]+)")
seen = None
for line in open(path):
    m = pat.match(line)
    if m:
        seen = m.group(1)
print(seen if seen is not None else "NA")
EOF
}

echo -e "policy\tscope\tmaxticks\tsim_insts\tnum_cycles\tipc\tl1d_miss_rate\tl2_miss_rate\tllc_miss_rate" > "$TSV"

for pol in lru srrrip; do
    for scope in l2llc all; do
        tmp="$(mktemp -d)"
        "$GEM5" -d "$tmp" "$CONFIG" \
            --binary "$SCAN" --cpu-type timing \
            --policy "$pol" --policy-scope "$scope" \
            --maxticks "$MAXTICKS" \
            --cmdargs "256" >/dev/null 2>&1
        stats="$tmp/stats.txt"
        insts="$(extract "$stats" simInsts)"
        cyc="$(extract "$stats" system.cpu.numCycles)"
        ipc="$(extract "$stats" system.cpu.ipc)"
        l1d="$(extract "$stats" system.cpu.dcache.overallMissRate::total)"
        l2="$(extract "$stats" system.l2.overallMissRate::total)"
        llc="$(extract "$stats" system.llc.overallMissRate::total)"
        echo -e "$pol\t$scope\t$MAXTICKS\t$insts\t$cyc\t$ipc\t$l1d\t$l2\t$llc" >> "$TSV"
        echo "[$pol/$scope] insts=$insts cycles=$cyc ipc=$ipc l1d=$l1d l2=$l2 llc=$llc"
        rm -rf "$tmp"
    done
done

echo "Resultados em $TSV"