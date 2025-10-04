#!/bin/bash

export MCNP_PATH="/Applications/MCNP6"
export DATAPATH=$MCNP_PATH"/MCNP_DATA"

ulimit -s unlimited

echo $$ >> PID

$MCNP_PATH/MCNP_CODE/bin/mcnp6 inp=$* &
PID_MCNP=$!
echo $PID_MCNP >> PID
wait $PID_MCNP

if [ -f "PID" ]; then
	rm -f "PID"
fi

