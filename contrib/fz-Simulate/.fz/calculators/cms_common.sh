# cms_common.sh - shared helpers for the fz-Simulate runners (sourced, not executed).
#
# find_launcher VAR_CMD VAR_PATH name...
#   Prints the launcher command: $VAR_CMD if set; else the first <name> found in
#   $VAR_PATH or $VAR_PATH/bin; else the first <name> found on PATH.
find_launcher() {
  local cmd_var=$1 path_var=$2 name dir
  shift 2
  if [ -n "${!cmd_var}" ]; then echo "${!cmd_var}"; return 0; fi
  if [ -n "${!path_var}" ]; then
    for name in "$@"; do
      for dir in "${!path_var}" "${!path_var}/bin"; do
        [ -f "$dir/$name" ] && { echo "$dir/$name"; return 0; }
      done
    done
  fi
  for name in "$@"; do
    command -v "$name" 2>/dev/null && return 0
  done
  return 1
}

# run_tracked CMD... : run a command in the background, record its PID in ./PID so
# that fz can kill it on interrupt, wait for it and return its exit status.
run_tracked() {
  "$@" &
  local pid=$!
  echo $pid >> "$FZ_CASE_DIR/PID"
  wait $pid
  local status=$?
  sed -i.bak "/^$pid\$/d" "$FZ_CASE_DIR/PID" 2>/dev/null; rm -f "$FZ_CASE_DIR/PID.bak"
  return $status
}

die() { local code=$1; shift; echo "$*" >&2; exit "$code"; }
