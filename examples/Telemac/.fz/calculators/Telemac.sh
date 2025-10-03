#!/bin/bash

# if direcotry as input, cd into it
if [ -d "$1" ]; then
  cd "$1"
  CAS=`ls *.cas | head -n 1`
  shift
# if $* are files, find the .cas file
elif [ $# -gt 1 ]; then
  CAS=""
  for f in "$@"; do
    if [ `echo $f | grep -c '\.cas$'` -eq 1 ]; then
      CAS="$f"
      break
    fi
  done
  if [ -z "$CAS" ]; then
    echo "No .cas file found in input files. Exiting."
    exit 1
  fi
  shift $#
else
  echo "Usage: $0 <case.cas or case_directory>"
  exit 2
fi

if [ 1 -le `echo \`pwd -P\` | grep --color='auto' -P -n "[\x80-\xFF]" | wc -l` ]; then
  echo "Telemac will not support non ISO char in path. Exiting."; 
  exit 3
fi

NCPU=`grep ^cpu\\\\scores /proc/cpuinfo | uniq |  awk '{print $4}'`

docker run -v `echo $PWD`:/workdir irsn/telemac-mascaret:latest telemac2d.py --ncsize=$NCPU $CAS &

PID=$!
echo $PID >> PID
wait $PID
rm -f PID

## Post processing to extract points from result file in CSV format
## For each *.poi files (pointname=coord on many lines) in the current directory, extract the points and interpolate the results in JSON dict for output S,H
## pip install https://github.com/CNR-Engineering/PyTelTools/zipball/master
## From example from https://github.com/CNR-Engineering/PyTelTools/blob/master/notebook/Post-processing%20examples.ipynb :

# test if PyTelTools is installed, otherwise install it in a tmp venv
python3 -c 'import pyteltools' 2>/dev/null
if [ $? -ne 0 ]; then
  echo "Installing PyTelTools in temporary venv"
  TMPDIR=`mktemp -d`
  python3 -m venv $TMPDIR/venv
  source $TMPDIR/venv/bin/activate
  pip install https://github.com/CNR-Engineering/PyTelTools/zipball/master
  trap "rm -rf $TMPDIR" EXIT
fi

function interpolate_poi () {
  python3 -c '
from pyteltools.geom import Shapefile
from pyteltools.slf.interpolation import MeshInterpolator
from pyteltools.slf import Serafin

# dict with point names and coordinates
points = '$2'

with Serafin.Read('$1', "en") as resin:
  resin.read_header()
  resin.get_time()
  # print header of csv with point names
  print("time," + ",".join(list(points.keys())))
  
  # Determine mesh interpolation
  mesh = MeshInterpolator(resin.header, True)
  is_inside, point_interpolators = mesh.get_point_interpolators(points.values())
  
  # Interpolate one variable and one frame only (the last)
  for it in range(len(resin.time)):
    results = [resin.time[it]]
    values = resin.read_var_in_frame(it, "'$3'")
    for pt_id, (point, point_interpolator) in enumerate(zip(points.values(), point_interpolators)):
      if point_interpolator is not None:
        (i, j, k), interpolator = point_interpolator
        results.append(interpolator.dot(values[[i, j, k]]))
    # print array values without brackets, types and add separator ','
    print(",".join([str(v) for v in results]))
'
}

RESULT_FILE=`grep "RESULT" $CAS | cut -d '=' -f 2 | tr -d ' '`
for f in *.poi; do
  if [ -f "$f" ]; then
    # convert poi file with lines 'point_name=coord' to python dict '{"point_name": [coord], ...}'
    POI_DICT=$(awk -F= '{gsub(/ /,"",$1); gsub(/ /,"",$2); print "\"" $1 "\": [" $2 "]"}' $f | paste -sd, -)
    POI_DICT=`echo $POI_DICT | tr -d '\n' | tr -d '\r' | tr -d ' '`
    POI_DICT="{${POI_DICT}}"
    # interpolate S and H and save to csv files
    interpolate_poi "$RESULT_FILE" "$POI_DICT" "S" > ${f%.poi}_S.csv 2>/dev/null
    interpolate_poi "$RESULT_FILE" "$POI_DICT" "H" > ${f%.poi}_H.csv 2>/dev/null
  fi
done

