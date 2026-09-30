# Quick Start

Here's a complete example for a simple parametric study:

## 1. Create an Input Template

Create `input.txt`:
```text
# input file for Perfect Gaz Pressure, with variables n_mol, T_celsius, V_L
n_mol=$n_mol
T_kelvin=@{$T_celsius + 273.15}
#@ def L_to_m3(L):
#@     return(L / 1000)
V_m3=@{L_to_m3($V_L)}
```

Or using R for formulas (assuming R interpreter is set up: `fz.set_interpreter("R")`):
```text
# input file for Perfect Gaz Pressure, with variables n_mol, T_celsius, V_L
n_mol=$n_mol
T_kelvin=@{$T_celsius + 273.15}
#@ L_to_m3 <- function(L) {
#@     return (L / 1000)
#@ }
V_m3=@{L_to_m3($V_L)}
```

## 2. Create a Calculation Script

Create `PerfectGazPressure.sh`:
```bash
#!/bin/bash

# read input file
source $1

sleep 5 # simulate a calculation time

echo 'pressure = '`echo "scale=4;$n_mol*8.314*$T_kelvin/$V_m3" | bc` > output.txt

echo 'Done'
```

Make it executable:
```bash
chmod +x PerfectGazPressure.sh
```

## 3. Run Parametric Study

Create `run_study.py`:
```python
import fz

# Define the model
model = {
    "varprefix": "$",
    "formulaprefix": "@",
    "delim": "{}",
    "commentline": "#",
    "output": {
        "pressure": "grep 'pressure = ' output.txt | awk '{print $3}'"
        # or, shell-free (portable, no bash/FZ_SHELL_PATH needed):
        # "pressure": "python://grep(r'pressure = (\\S+)', 'output.txt')"
        # or, for JSON results, using jq (requires the jq executable):
        # "pressure": "jq://.pressure output.json"
        # or, for YAML/JSON/XML/TOML results, using yq (requires yq):
        # "pressure": "yq://.pressure output.yaml"
        # or, for XML results, using XPath (requires xmllint):
        # "pressure": "xpath://'//pressure/text()' output.xml"
    }
}

# Define parameter values
input_variables = {
    "T_celsius": [10, 20, 30, 40],  # 4 temperatures
    "V_L": [1, 2, 5],                # 3 volumes
    "n_mol": 1.0                     # fixed amount
}

# Run all combinations (4 × 3 = 12 cases)
results = fz.fzr(
    "input.txt",
    input_variables,
    model,
    calculators="sh://bash PerfectGazPressure.sh",
    results_dir="results"
)

# Display results
print(results)
print(f"\nCompleted {len(results)} calculations")
```

Run it:
```bash
python run_study.py
```

Expected output:
```
   T_celsius  V_L  n_mol     pressure status calculator       error command
0         10  1.0    1.0  235358.1200   done     sh://        None    bash...
1         10  2.0    1.0  117679.0600   done     sh://        None    bash...
2         10  5.0    1.0   47071.6240   done     sh://        None    bash...
3         20  1.0    1.0  243730.2200   done     sh://        None    bash...
...

Completed 12 calculations
```
