#!/bin/bash
# CasmoSimulate.sh - fz runner for the CASMO5 -> CMS-LINK -> SIMULATE chain.
# Usage: CasmoSimulate.sh <case directory>
#
# Expected case layout (file names configurable, see below):
#   casmo/*.inp     CASMO lattice decks (one per fuel segment / reflector)
#   cmslink.inp     CMS-LINK deck, reading casmo/*.cax, writing the library
#   simulate.inp    SIMULATE deck, reading that library
#
# Launchers (each: *_CMD, else *_PATH/{,bin/}<name>, else <name> on PATH):
#   CASMO     CASMO_CMD    CASMO_PATH    cas5
#   CMS-LINK  CMSLINK_CMD  CMSLINK_PATH  cmslink5 cmslink link5
#   SIMULATE  SIMULATE_CMD SIMULATE_PATH sim5 simulate5 simulate3 s3
# Options: CASMO_OPTS (default "-p -k"), CMSLINK_OPTS, SIMULATE_OPTS (default none).
# CASMO_JOBS: number of CASMO decks run concurrently (default 1).
# CHAIN_CASMO_DIR, CHAIN_CMSLINK_INPUT, CHAIN_SIMULATE_INPUT override the layout.
# Exit status: 2 setup error, 10+ CASMO failure, 20+ CMS-LINK, 30+ SIMULATE.
source "$(dirname "$0")/cms_common.sh"
trap 'rm -f "${FZ_CASE_DIR:-.}/PID"' EXIT

CASMO_DIR=${CHAIN_CASMO_DIR:-casmo}
LINK_INP=${CHAIN_CMSLINK_INPUT:-cmslink.inp}
SIM_INP=${CHAIN_SIMULATE_INPUT:-simulate.inp}

# fz runs this script inside the case directory, passing the case files as
# arguments; a directory argument is also accepted
if [ -d "$1" ]; then cd "$1" || exit 2; fi
# tolerate one extra directory level (input directory copied as a subdirectory)
if [ ! -d "$CASMO_DIR" ]; then
  sub=$(ls -d */"$CASMO_DIR" 2>/dev/null | head -n 1)
  [ -n "$sub" ] && cd "$(dirname "$sub")"
fi
FZ_CASE_DIR=$(pwd)
for f in "$CASMO_DIR" "$LINK_INP" "$SIM_INP"; do
  [ -e "$f" ] || die 2 "Missing $f in $(pwd) (expected: $CASMO_DIR/*.inp, $LINK_INP, $SIM_INP)"
done

CAS5=$(find_launcher CASMO_CMD CASMO_PATH cas5) ||
  die 2 "CASMO5 launcher not found: set CASMO_CMD, CASMO_PATH or put cas5 on PATH"
LINK=$(find_launcher CMSLINK_CMD CMSLINK_PATH cmslink5 cmslink link5) ||
  die 2 "CMS-LINK launcher not found: set CMSLINK_CMD, CMSLINK_PATH or put it on PATH"
SIM=$(find_launcher SIMULATE_CMD SIMULATE_PATH sim5 simulate5 simulate3 s3) ||
  die 2 "SIMULATE launcher not found: set SIMULATE_CMD, SIMULATE_PATH or put it on PATH"
[ -n "$CASMO_PATH" ] && export CMSHOME="${CMSHOME:-$CASMO_PATH}"

# 1. CASMO: every lattice deck, CASMO_JOBS at a time
echo "== CASMO ($CAS5)"
decks=$(cd "$CASMO_DIR" && ls *.inp 2>/dev/null)
[ -n "$decks" ] || die 2 "No CASMO deck in $CASMO_DIR/"
(
  cd "$CASMO_DIR" || exit 2
  for d in $decks; do
    while [ "$(jobs -rp | wc -l)" -ge "${CASMO_JOBS:-1}" ]; do sleep 1; done
    echo "   $d"
    # $CAS5 and $CASMO_OPTS intentionally unquoted (may hold a command with options)
    run_tracked $CAS5 ${CASMO_OPTS--p -k} "$d" > "${d%.*}.log" 2>&1 &
  done
  wait
)
failed=0
for d in $decks; do
  b="$CASMO_DIR/${d%.*}"
  if [ ! -s "$b.out" ] || [ ! -e "$b.cax" ]; then
    echo "CASMO failed for $d (missing $b.out or $b.cax), see $b.log" >&2
    failed=$((failed + 1))
  fi
done
[ $failed -eq 0 ] || die 10 "$failed CASMO deck(s) failed"

# 2. CMS-LINK: build the SIMULATE library from the .cax files
echo "== CMS-LINK ($LINK)"
run_tracked $LINK $CMSLINK_OPTS "$LINK_INP"
status=$?
[ $status -eq 0 ] || die 20 "CMS-LINK exited with status $status"

# 3. SIMULATE
echo "== SIMULATE ($SIM)"
run_tracked $SIM $SIMULATE_OPTS "$SIM_INP"
status=$?
[ $status -eq 0 ] || die 30 "SIMULATE exited with status $status"
[ -s "${SIM_INP%.*}.out" ] || ls ./*.out >/dev/null 2>&1 || die 31 "SIMULATE produced no .out file"
exit 0
