#!/usr/bin/env bash
# Executa o PoC do canal no L1 com as politicas configuradas e analisa.
# Uso: scripts/run_channel.sh [outdir]
# Requer: gem5 compilado, channel compilado (ver README.md da raiz de sim/).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GEM5="$ROOT/gem5/build/X86/gem5.opt"
CONFIG="$ROOT/configs/config_channel.py"
CHANNEL="$ROOT/results/bin/channel"
ANALYZE="$ROOT/scripts/analyze.py"
PY="$ROOT/.venv/bin/python"

OUT="${1:-$ROOT/results/runs/l1_lru_vs_rrip}"
mkdir -p "$OUT"

for pol in lru srrrip rrrip brrip; do
    csv="$OUT/channel_l1_${pol}.csv"
    png="$OUT/l1_${pol}.png"
    GEM5_OUT="$(mktemp -d)"
    "$GEM5" -d "$GEM5_OUT" "$CONFIG" \
        --binary "$CHANNEL" \
        --cpu-type timing \
        --policy "$pol" \
        --cmdargs "--out $csv" >/dev/null 2>&1
    "$PY" "$ANALYZE" --csv "$csv" --png "$png"
    rm -rf "$GEM5_OUT"
done

echo "Resultados em $OUT"