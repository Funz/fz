# install examples environment

```bash
mkdir tmp
cd tmp
```
## PerfectGaz

input.txt:
```bash
echo '#!/bin/bash
# input file for Perfect Gaz Pressure, with variables n_mol, T_celsius, V_L
n_mol=$n_mol
T_kelvin=@($T_celsius + 273.15)
#@ def L_to_m3(L): 
#@     return(L / 1000)
V_m3=@(L_to_m3($V_L))' > input.txt
```

PerfectGazPressure.sh:
```bash
echo '#!/bin/bash
# read input file
source $1
sleep 5 # simulate a calculation time
echo "pressure = "`echo "scale=4;$n_mol*8.314*$T_kelvin/$V_m3" | bc` > output.txt
echo "Done"' > PerfectGazPressure.sh
chmod +x PerfectGazPressure.sh
```
PerfectGazPressureRandomFails.sh:
```bash
echo '#!/bin/bash
# read input file
source $1
sleep 5 # simulate a calculation time
if [ $((RANDOM % 2)) -eq 0 ]; then
  echo "pressure = "`echo "scale=4;$n_mol*8.314*$T_kelvin/$V_m3" | bc` > output.txt
  echo "Done"
else
  echo "Calculation failed" >&2
  exit 1
fi' > PerfectGazPressureRandomFails.sh
chmod +x PerfectGazPressureRandomFails.sh
```
PerfectGazPressureAlwaysFails.sh:
```bash
echo '#!/bin/bash
# read input file
source $1
sleep 5 # simulate a calculation time
echo "Calculation failed" >&2
exit 1' > PerfectGazPressureAlwaysFails.sh
chmod +x PerfectGazPressureAlwaysFails.sh
```

## Modelica

NewtonCooling.mo:
```bash
echo 'model NewtonCooling "An example of Newton s law of cooling"
  parameter Real T_inf=25 "Ambient temperature";
  parameter Real T0=90 "Initial temperature";
  parameter Real h=$(convection) "Convective cooling coefficient";
  parameter Real A=1.0 "Surface area";
  parameter Real m=0.1 "Mass of thermal capacitance";
  parameter Real c_p=1.2 "Specific heat";
  Real T "Temperature";
initial equation
  T = T0 "Specify initial value for T";
equation
  m*c_p*der(T) = h*A*(T_inf-T) "Newton s law of cooling";
end NewtonCooling;' > NewtonCooling.mo
```
Modelica.sh:
```bash
echo '#!/bin/bash

if [ ! ${1: -4} == ".mos" ]; then
  model=`grep "model" $1 | awk '"'"'{print $2}'"'"'`
  cat > $1.mos <<- EOM
loadModel(Modelica);
loadFile("$1");
simulate($model, stopTime=1,tolerance=0.001,outputFormat="csv");
EOM
  omc $1.mos > $1.moo 2>&1 &
else
  omc $1 > $1.moo 2>&1 &
fi

PID_OMC=$!
echo $PID_OMC >> PID #this will allow Funz to kill process if needed

wait $PID_OMC

rm -f PID

ERROR=`cat *.moo | grep "Failed"`
if [ ! "$ERROR" == "" ]; then
    echo $ERROR >&2
    exit 1
fi' > Modelica.sh
chmod +x Modelica.sh
```
install modelica compiler omc (assuming ubuntu or deb host):
```bash
sudo apt-get update
sudo apt-get install ca-certificates curl gnupg
sudo curl -fsSL http://build.openmodelica.org/apt/openmodelica.asc | \
  sudo gpg --dearmor -o /usr/share/keyrings/openmodelica-keyring.gpg

echo "deb [arch=amd64 signed-by=/usr/share/keyrings/openmodelica-keyring.gpg] \
  https://build.openmodelica.org/apt \
  $(cat /etc/os-release | grep "\(UBUNTU\\|DEBIAN\\|VERSION\)_CODENAME" | sort | cut -d= -f 2 | head -1) \
  stable" | sudo tee /etc/apt/sources.list.d/openmodelica.list

sudo apt install --no-install-recommends omc
```


## Telemac

copy t2d_breach.cas from examples/Telemac to tmp directory
```bash
cp -r ../examples/Telemac/t2d_breach.cas .
```
copy fz aliases for Telemac to tmp directory
```bash
cp -r ../examples/Telemac/.fz . # contains calculators/Telemac.sh, calculators/Localhost_Telemac.sh, models/Telemac.json
```
install docker (for Telemac, assuming ubuntu host)
```bash
# Add Docker's official GPG key:
sudo apt-get update
sudo apt-get install ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

# Add the repository to Apt sources:
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}") stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update

sudo apt-get install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo systemctl start docker
```


## python setup

```bash
python -m venv venv
source venv/bin/activate
pip install ..
pip install matplotlib pandas
```

```python
import fz
#fz.set_log_level(fz.LogLevel.DEBUG)
#import os
#os.chdir("tmp")
```

# test PerfectGaz example

```python
fz.fzi("input.txt",
{
    "varprefix": "$",
    "formulaprefix": "@",
    "delim": "()",
    "commentline": "#",
    "output": {"pressure": "grep 'pressure = ' output.txt | awk '{print $3}'"}
})
```

```python
fz.fzc("input.txt",
{
    "varprefix": "$",
    "formulaprefix": "@",
    "delim": "()",
    "commentline": "#",
    "output": {"pressure": "grep 'pressure = ' output.txt | awk '{print $3}'"}
},{
    "T_celsius": 20,
    "V_L": 1,
    "n_mol": 1
}, engine="python", outputdir="output")
```

run calculation for one case

```python
fz.fzr("input.txt",
{
    "varprefix": "$",
    "formulaprefix": "@",
    "delim": "()",
    "commentline": "#",
    "output": {"pressure": "grep 'pressure = ' output.txt | awk '{print $3}'"}
},{
    "T_celsius": 20,
    "V_L": 1,
    "n_mol": 1
}, engine="python", calculators="sh:///bin/bash ./PerfectGazPressure.sh", resultsdir="result")
```

run calculation for many cases (factorial design of experiments)

```python
fz.fzr("input.txt",
{
    "varprefix": "$",
    "formulaprefix": "@",
    "delim": "()",
    "commentline": "#",
    "output": {"pressure": "grep 'pressure = ' output.txt | awk '{print $3}'"}
},{
    "T_celsius": [20,25,30],
    "V_L": [1,1.5],
    "n_mol": 1
}, engine="python", calculators="sh:///bin/bash ./PerfectGazPressure.sh", resultsdir="results")
```

use fzo to get same results from previous fzr
```python
fz.fzo("results", {"output": {"pressure": "grep 'pressure = ' output.txt | awk '{print $3}'"}})
```

test cache (all cases should be in cache, so no more calculation should be done)
```python
fz.fzr("input.txt",
{
    "varprefix": "$",
    "formulaprefix": "@",
    "delim": "()",
    "commentline": "#",
    "output": {"pressure": "grep 'pressure = ' output.txt | awk '{print $3}'"}
},{
    "T_celsius": [20,25,30],
    "V_L": [1,1.5],
    "n_mol": 1
}, engine="python", calculators=["cache://results_*","sh:///bin/bash ./PerfectGazPressure.sh"], resultsdir="results")
```

# test parallel execution of calculators

robin-round distribution of calculations cases to calculators

here 2 calculators, 2 cases, so should run in 5 seconds instead of 10 seconds if run sequentially)
```python
fz.fzr("input.txt",
{
    "varprefix": "$",
    "formulaprefix": "@",
    "delim": "()",
    "commentline": "#",
    "output": {"pressure": "grep 'pressure = ' output.txt | awk '{print $3}'"}
},{
    "T_celsius": [20,25],
    "V_L": 1,
    "n_mol": 1
}, engine="python", calculators=["sh:///bin/bash ./PerfectGazPressure.sh","sh:///bin/bash ./PerfectGazPressure.sh"], resultsdir="results")
```

now 3 calculators, 2 cases, so should run in 5 seconds instead of 10 seconds if run sequentially)
```python
fz.fzr("input.txt",
{
    "varprefix": "$",
    "formulaprefix": "@",
    "delim": "()",
    "commentline": "#",
    "output": {"pressure": "grep 'pressure = ' output.txt | awk '{print $3}'"}
},{
    "T_celsius": [20,25],
    "V_L": 1,
    "n_mol": 1
}, engine="python", calculators=["sh:///bin/bash ./PerfectGazPressure.sh","sh:///bin/bash ./PerfectGazPressure.sh","sh:///bin/bash ./PerfectGazPressure.sh"], resultsdir="results")
```

now 2 calculators, 3 cases, so should run in 10 seconds instead of 15 seconds if run sequentially)
```python
fz.fzr("input.txt",
{
    "varprefix": "$",
    "formulaprefix": "@",
    "delim": "()",
    "commentline": "#",
    "output": {"pressure": "grep 'pressure = ' output.txt | awk '{print $3}'"}
},{
    "T_celsius": [20,25,30],
    "V_L": 1,
    "n_mol": 1
}, engine="python", calculators=["sh:///bin/bash ./PerfectGazPressure.sh","sh:///bin/bash ./PerfectGazPressure.sh"], resultsdir="results")
```

# test Modelica example

```python
fz.fzi("NewtonCooling.mo",
{
    "varprefix": "$",
    "formulaprefix": "@",
    "delim": "()",
    "commentline": "#",
    "output": {"res": "python -c 'import pandas;import glob;import json;print(json.dumps({f.split(\"_res.csv\")[0]:pandas.read_csv(f).to_dict() for f in glob.glob(\"*_res.csv\")}))'"}
})
```

```python
fz.fzc("NewtonCooling.mo",
{
    "varprefix": "$",
    "formulaprefix": "@",
    "delim": "()",
    "commentline": "#",
    "output": {"res": "python -c 'import pandas;import glob;import json;print(json.dumps({f.split(\"_res.csv\")[0]:pandas.read_csv(f).to_dict() for f in glob.glob(\"*_res.csv\")}))'"}
},{
    "convection": 123
}, engine="python", outputdir="output")
```

```python
results=fz.fzr("NewtonCooling.mo",
{
    "varprefix": "$",
    "formulaprefix": "@",
    "delim": "()",
    "commentline": "#",
    "output": {"res": "python -c 'import pandas;import glob;import json;print(json.dumps({f.split(\"_res.csv\")[0]:pandas.read_csv(f).to_dict() for f in glob.glob(\"*_res.csv\")}))'"}
},{
    "convection": [.123,.456, .789],
}, engine="python", calculators="sh:///bin/bash ./Modelica.sh", resultsdir="results")

# plot temperature for the 3 cases
import matplotlib.pyplot as plt
plt.plot(results["res"][0]["NewtonCooling"]["time"].values(), results["res"][0]["NewtonCooling"]["T"].values(), label="convection=.123")
plt.plot(results["res"][1]["NewtonCooling"]["time"].values(), results["res"][1]["NewtonCooling"]["T"].values(), label="convection=.456")
plt.plot(results["res"][2]["NewtonCooling"]["time"].values(), results["res"][2]["NewtonCooling"]["T"].values(), label="convection=.789")
plt.legend()
plt.show()
```

use fzo to get same results from previous fzr
```python
fz.fzo("results", {"output": {"res": "python -c 'import pandas;import glob;import json;print(json.dumps({f.split(\"_res.csv\")[0]:pandas.read_csv(f).to_dict() for f in glob.glob(\"*_res.csv\")}))'"}})
```

use cache of previous results
```python
fz.fzr("NewtonCooling.mo",
{
    "varprefix": "$",
    "formulaprefix": "@",
    "delim": "()",
    "commentline": "#",
    "output": {"res": "python -c 'import pandas;import glob;import json;print(json.dumps({f.split(\"_res.csv\")[0]:pandas.read_csv(f).to_dict() for f in glob.glob(\"*_res.csv\")}))'"}
},{
    "convection": [.123,.456, .789],
}, engine="python", calculators=["cache://results_*","sh:///bin/bash ./Modelica.sh"], resultsdir="results")
```

# test Telemac example

```python
fz.fzi("t2d_breach.cas",
{
    "varprefix": "$",
    "formulaprefix": "@",
    "delim": "()",
    "commentline": "#"
})
```

```python
fz.fzr("t2d_breach.cas",
{
    "id": "Telemac",
    "varprefix": "$",
    "formulaprefix": "@",
    "delim": "()",
    "commentline": "#",
    "output": {
        "S": "python -c 'import pandas;import glob;import json;print(json.dumps({f.split(\"_S.csv\")[0]:pandas.read_csv(f).to_dict() for f in glob.glob(\"*_S.csv\")}))'",
        "H": "python -c 'import pandas;import glob;import json;print(json.dumps({f.split(\"_H.csv\")[0]:pandas.read_csv(f).to_dict() for f in glob.glob(\"*_H.csv\")}))'"
    }
},var_values={}, engine="python", calculators="sh:///bin/bash .fz/calculators/Telemac.sh", resultsdir="result")
```

use cache and aliases for Telemac:
```python
fz.fzr("t2d_breach.cas","Telemac",var_values={}, engine="python", calculators="*", resultsdir="result")
```

# test ssh

add ssh server to localhost:
```bash
ssh-keygen -t rsa -b 4096 -f ~/.ssh/id_rsa -N ""
cat ~/.ssh/id_rsa.pub >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
sudo apt-get install openssh-server
sudo systemctl start ssh
```

```python
# get current dir path
import os
current_dir=os.getcwd()

# build calculator ssh uri
ssh_calculator=f"ssh://localhost//bin/bash {current_dir}/PerfectGazPressure.sh"

fz.fzr("input.txt",
{
    "varprefix": "$",
    "formulaprefix": "@",
    "delim": "()",
    "commentline": "#",
    "output": {"pressure": "grep 'pressure = ' output.txt | awk '{print $3}'"}
},{
    "T_celsius": [20,30,40],
    "V_L": 1,
    "n_mol": 1
}, engine="python", calculators=ssh_calculator, resultsdir="results")
```

# test parallel execution of calculators

```python
fz.fzr("input.txt",
{
    "varprefix": "$",
    "formulaprefix": "@",
    "delim": "()",
    "commentline": "#",
    "output": {"pressure": "grep 'pressure = ' output.txt | awk '{print $3}'"}
},{
    "T_celsius": [20,30,40],
    "V_L": [1,1.5],
    "n_mol": 1
}, engine="python", calculators=["sh:///bin/bash ./PerfectGazPressure.sh"]*6, resultsdir="results")
```

fzo to get same results from previous fzr
```python
fz.fzo("results", {"output": {"pressure": "grep 'pressure = ' output.txt | awk '{print $3}'"}})
```

# failure support

never fails
```python
fz.fzr("input.txt",
{
    "varprefix": "$",
    "formulaprefix": "@",
    "delim": "()",
    "commentline": "#",
    "output": {"pressure": "grep 'pressure = ' output.txt | awk '{print $3}'"}
},{
    "T_celsius": [20,25,30],
    "V_L": [1,1.5],
    "n_mol": [1,0]  
}, engine="python", calculators=["sh:///bin/bash ./PerfectGazPressure.sh"]*3, resultsdir="results")
```

sometimes fails, but retries and succeeds (must return numerics for all pressure values)
```python
fz.fzr("input.txt",
{
    "varprefix": "$",
    "formulaprefix": "@",
    "delim": "()",
    "commentline": "#",
    "output": {"pressure": "grep 'pressure = ' output.txt | awk '{print $3}'"}
},{
    "T_celsius": [20,25,30],
    "V_L": [1,1.5],
    "n_mol": [1,0] 
}, engine="python", calculators=["sh:///bin/bash ./PerfectGazPressureRandomFails.sh"]*3, resultsdir="results")
```

always fails (must return None in all pressure values)
```python
fz.fzr("input.txt",
{
    "varprefix": "$",
    "formulaprefix": "@",
    "delim": "()",
    "commentline": "#",
    "output": {"pressure": "grep 'pressure = ' output.txt | awk '{print $3}'"}
},{
    "T_celsius": [20,25,30],
    "V_L": [1,1.5],
    "n_mol": [1,0]
}, engine="python", calculators=["sh:///bin/bash ./PerfectGazPressureAlwaysFails.sh"]*3, resultsdir="results")
```

now use previous results in cache, but as failed should run calculations again
```python
fz.fzr("input.txt",
{
    "varprefix": "$",
    "formulaprefix": "@",
    "delim": "()",
    "commentline": "#",
    "output": {"pressure": "grep 'pressure = ' output.txt | awk '{print $3}'"}
},{
    "T_celsius": [20,25,30],
    "V_L": [1,1.5],
    "n_mol": [1,0]  
}, engine="python", calculators=["cache://_","sh:///bin/bash ./PerfectGazPressure.sh","sh:///bin/bash ./PerfectGazPressure.sh"], resultsdir="results")
```

# non-numeric variables

with some wrong values "abc", should fail for these cases only
```python
fz.fzr("input.txt",
{
    "varprefix": "$",
    "formulaprefix": "@",
    "delim": "()",
    "commentline": "#",
    "output": {"pressure": "grep 'pressure = ' output.txt | awk '{print $3}'"}
},{
    "T_celsius": ["20","25","abc"],
    "V_L": [1,1.5],
    "n_mol": [1,0]  
}, engine="python", calculators=["sh:///bin/bash ./PerfectGazPressure.sh"]*3, resultsdir="results")
```