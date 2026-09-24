#!/bin/bash
# Simulate.sh - fz runner for Studsvik SIMULATE (core simulator).
# Usage: Simulate.sh <compiled SIMULATE input | directory containing it>
#
# Launcher lookup (first match wins):
#   $SIMULATE_CMD;  $SIMULATE_PATH/{,bin/}{sim5,simulate5,simulate3,s3};  same names on PATH.
# Extra launcher options: $SIMULATE_OPTS (default none).
# The nuclear data library (CMS-LINK output) must be reachable as named in the deck:
# ship it in the input directory, pass it with fzr --input_static, or use an
# absolute path in the deck.
source "$(dirname "$0")/cms_common.sh"
trap 'rm -f "${FZ_CASE_DIR:-.}/PID"' EXIT

# fz passes every file of the case (static files included) as arguments, in no
# guaranteed order: pick the SIMULATE deck among them.
if [ -d "$1" ]; then cd "$1" || exit 2; set --; fi
INP=""
for a in "$@"; do [ "$(basename "$a")" = simulate.inp ] && { INP="$a"; break; }; done
[ -z "$INP" ] && for a in "$@"; do case "$a" in *.inp) INP="$a"; break ;; esac; done
[ -z "$INP" ] && INP=$(ls simulate.inp 2>/dev/null || ls *.inp 2>/dev/null | head -n 1)
[ -n "$INP" ] && [ -f "$INP" ] || die 2 "No SIMULATE input file (*.inp) found"
cd "$(dirname "$INP")" || exit 2
INP=$(basename "$INP")
FZ_CASE_DIR=$(pwd)

SIM=$(find_launcher SIMULATE_CMD SIMULATE_PATH sim5 simulate5 simulate3 s3) ||
  die 2 "SIMULATE launcher not found: set SIMULATE_CMD, or SIMULATE_PATH (install dir), or put sim5/simulate3 on PATH"

echo "== SIMULATE: $SIM $SIMULATE_OPTS $INP"
# $SIM and $SIMULATE_OPTS are intentionally unquoted (may hold a command with options)
run_tracked $SIM $SIMULATE_OPTS "$INP"
status=$?
[ $status -eq 0 ] || die $status "SIMULATE exited with status $status"
ls ./*.out >/dev/null 2>&1 || die 1 "SIMULATE produced no .out file"
exit 0
