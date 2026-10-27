#!/usr/bin/env bash
# Demo for the video: build the image, run it on the organisers' 20-row sample
# the way the organisers run it, then show the first rows of the table it
# hands in and the validator's summary.
#
#   scripts/demo.sh             sample/sample.csv, fetched from the starter repo
#                               (QA-DNA/hype-arena-starter) when not here yet
#   scripts/demo.sh rows.csv    any id,text,date CSV, to rehearse
#
# The lexicon is sample/lexicon.json when the sample ships one, else
# data/lexicon.json. The run's universe/ and output/ stay in a temp folder
# whose path is printed at the end; the container is removed when it exits.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SAMPLE_URL="https://raw.githubusercontent.com/QA-DNA/hype-arena-starter/main/sample/sample.csv"
IMAGE="hype-demo"
MINUTES=30   # the organisers' run time limit
SHOW=20      # rows printed

TMP="${TMPDIR:-/tmp}"
WORK="$(mktemp -d "${TMP%/}/hype-demo.XXXXXX")"
mkdir -p "$WORK/universe" "$WORK/output"
chmod 777 "$WORK/output"   # the image runs as user 10001

step() { printf '\n== %s\n' "$*"; }

SAMPLE="${1:-$ROOT/sample/sample.csv}"
if [ ! -f "$SAMPLE" ]; then
  if [ $# -gt 0 ]; then
    echo "no such file: $SAMPLE" >&2
    rm -rf "$WORK"
    exit 1
  fi
  step "Fetching sample/sample.csv from the starter repo"
  if ! curl -fsL "$SAMPLE_URL" -o "$WORK/sample.csv"; then
    echo "The starter repo has no sample/sample.csv yet (it arrives on 29 Oct at 09:00)." >&2
    echo "To rehearse, pass any id,text,date CSV: scripts/demo.sh rows.csv" >&2
    rm -rf "$WORK"
    exit 1
  fi
  SAMPLE="$WORK/sample.csv"
fi
LEXICON="$ROOT/sample/lexicon.json"
[ -f "$LEXICON" ] || LEXICON="$ROOT/data/lexicon.json"

cp "$SAMPLE" "$WORK/universe/universe.csv"
cp "$LEXICON" "$WORK/universe/lexicon.json"
step "Universe: $(($(wc -l < "$WORK/universe/universe.csv") - 1)) rows from ${SAMPLE#"$ROOT/"}"
head -n 4 "$WORK/universe/universe.csv"

step "Building the image (docker build --platform linux/amd64)"
docker build --quiet --platform linux/amd64 -t "$IMAGE" "$ROOT" >/dev/null
docker image inspect "$IMAGE" --format 'user {{.Config.User}}, {{.Size}} bytes compressed'

step "Running it offline: 2 CPUs, 6 GiB, read-only root, ${MINUTES}-minute deadline"
start=$(date +%s)
docker run --rm --name "$IMAGE" --platform linux/amd64 \
  --network none --cpus 2 --memory 6g --pids-limit 256 \
  --read-only --tmpfs /tmp:size=128m \
  -v "$WORK/universe:/universe:ro" -v "$WORK/output:/output" \
  -e ARENA_DEADLINE=$(( start + MINUTES * 60 )) \
  "$IMAGE"
echo "finished in $(( $(date +%s) - start ))s"

OUT="$WORK/output/output.csv"
step "The first $SHOW rows of output/output.csv"
python3 - "$OUT" "$SHOW" <<'PY'
import csv, sys
from collections import Counter

rows = list(csv.DictReader(open(sys.argv[1], encoding="utf-8", newline="")))
for r in rows[: int(sys.argv[2])]:
    print(f"{r['id']}  {r['type']:9} {r['label']:5} {r['confidence']:5}  {r['text']}")
mix = Counter((r["type"], r["label"]) for r in rows)
print(f"\n{len(rows)} rows: " + ", ".join(
    f"{t} {mix[(t, 'true')]}/{mix[(t, 'false')]}"
    for t in ("fact", "compare", "change", "at_event", "relation")) + " (true/false)")
PY

step "Validator summary"
if [ -f "$ROOT/arena/validate.py" ]; then
  (cd "$ROOT" && python3 -m arena.validate "$OUT") || echo "(the validator reported invalid rows)"
else
  echo "arena/validate.py is not merged yet; skipped"
fi

step "Files"
echo "universe and output: $WORK"
