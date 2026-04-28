#!/usr/bin/env python3
"""
Generator script: creates all 5 fz stress-test Jupyter notebooks.
Run with: python3 generate_notebooks.py
"""
import nbformat as nbf
from pathlib import Path

OUT = Path(__file__).parent

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def md(text):
    return nbf.v4.new_markdown_cell(text)

def code(src):
    return nbf.v4.new_code_cell(src)

def save(nb, name):
    path = OUT / name
    nbf.write(nb, str(path))
    print(f"  wrote {path}")

# A helper snippet added to every notebook that needs to read compiled files.
# fzc always creates a subdirectory named  var1=val1,var2=val2,...
# EXCEPT when input_variables={} (all-defaults), in which case files land
# directly in the output directory.
READ_COMPILED_HELPER = """\
def read_compiled(out_dir, filename):
    \"\"\"Read compiled file – handles both direct and subdirectory layouts.\"\"\"
    direct = Path(out_dir) / filename
    if direct.exists():
        return direct.read_text()
    subdirs = sorted(d for d in Path(out_dir).iterdir()
                     if d.is_dir() and not d.name.startswith("."))
    if subdirs:
        return (subdirs[0] / filename).read_text()
    raise FileNotFoundError(f"{filename} not found in {out_dir}")

def case_dir(out_dir):
    \"\"\"Return the first case subdirectory (or out_dir itself for defaults).\"\"\"
    p = Path(out_dir)
    subdirs = sorted(d for d in p.iterdir()
                     if d.is_dir() and not d.name.startswith("."))
    return subdirs[0] if subdirs else p
"""

# ===========================================================================
# NOTEBOOK 1 – Getting Started
# ===========================================================================
def nb01():
    nb = nbf.v4.new_notebook()
    cells = []

    cells.append(md("""\
# FZ Getting Started: Perfect Gas Parametric Study

This notebook walks through **every core fz function** using a classic
thermodynamics example — the ideal gas law:

> **PV = nRT**  →  T = PV / (nR)

We will:
1. `fzl` — inspect installed models/calculators
2. `fzi` — detect variables in an input template
3. `fzc` — compile templates for specific parameter values
4. `fzo` — parse output files
5. `fzr` — run full parametric calculations in parallel

No external simulator needed — a tiny Python script acts as our "solver".
"""))

    cells.append(code("""\
import sys, json, shutil
from pathlib import Path
import fz
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

print(f"fz  {fz.__version__}")
fz.set_log_level("WARNING")   # suppress verbose INFO lines in the notebook
fz.print_config()
"""))

    cells.append(md("## 1 · Workspace setup"))

    cells.append(code("""\
WORK = Path("work_01_getting_started")
WORK.mkdir(exist_ok=True)
(WORK / "models").mkdir(exist_ok=True)
print("Workspace:", WORK.resolve())
"""))

    cells.append(md("## 2 · The simulator script\n\n"
"We write a tiny Python script that reads a compiled `params.in` file, "
"applies the ideal gas law, and writes `output.txt`."))

    cells.append(code("""\
SIM = WORK / "models" / "perfectgas.py"
SIM.write_text('''#!/usr/bin/env python3
\"\"\"Perfect Gas solver – reads params.in, writes output.txt\"\"\"
params = {}
with open("params.in") as fh:
    for line in fh:
        line = line.split("#")[0].strip()
        if "=" in line:
            k, v = line.split("=", 1)
            params[k.strip()] = float(v.strip())

P, V, n = params["P"], params["V"], params["n"]
R = 0.08206          # L·atm / (mol·K)
T = P * V / (n * R)

with open("output.txt", "w") as fh:
    fh.write(f"P = {P}\\\\n")
    fh.write(f"V = {V}\\\\n")
    fh.write(f"n = {n}\\\\n")
    fh.write(f"T = {T:.6f}\\\\n")
    fh.write("status = OK\\\\n")
''')
print("Created:", SIM)
"""))

    cells.append(md("## 3 · Input template\n\n"
"Variables are written as `${name~default}`.  "
"The `~default` part provides a fall-back when no value is passed to `fzc`."))

    cells.append(code("""\
TMPL = WORK / "params.in"
TMPL.write_text(
    "# Perfect Gas input parameters\\n"
    "P = ${P~1.013}   # pressure (atm)\\n"
    "V = ${V~22.4}    # volume (L)\\n"
    "n = ${n~1.0}     # moles of gas\\n"
)
print(TMPL.read_text())
"""))

    cells.append(md("## 4 · Model definition\n\n"
"The model tells fz:\n"
"- which characters mark variables/formulas\n"
"- how to extract output values from result files"))

    cells.append(code("""\
MODEL = {
    "varprefix":     "$",
    "formulaprefix": "@",
    "delim":         "{}",
    "commentline":   "#",
    "output": {
        "temperature": "grep '^T = ' output.txt | awk '{print $3}'",
        "pressure":    "grep '^P = ' output.txt | awk '{print $3}'",
    },
}
print(json.dumps(MODEL, indent=2))
"""))

    cells.append(md("## 5 · `fzl` — list installed models & calculators"))

    cells.append(code("""\
info = fz.fzl()
print("Models:")
for name, props in info["models"].items():
    print(f"  {name}: {props['path']}")
print("\\nCalculators:")
for name in info["calculators"]:
    print(f"  {name}")
"""))

    cells.append(md("## 6 · `fzi` — detect variables in the template"))

    cells.append(code("""\
variables = fz.fzi(str(TMPL), MODEL)
print("Detected variables (name → default):")
print(json.dumps(variables, indent=2))
"""))

    cells.append(md("## 7 · `fzc` — compile for a single parameter set\n\n"
"fzc **always** creates a subdirectory named `var1=val1,var2=val2,...` "
"inside the output directory."))

    cells.append(code(READ_COMPILED_HELPER + """\

out_single = WORK / "compiled_single"
fz.fzc(str(TMPL), {"P": 2.5, "V": 15.0, "n": 0.75}, MODEL,
       output_dir=str(out_single))
cd = case_dir(out_single)
print(f"Case directory: {cd.name}")
print("Compiled params.in:")
print(cd.read_text() if cd == out_single else (cd / "params.in").read_text())
"""))

    cells.append(md("## 8 · `fzc` — compile a Cartesian grid\n\n"
"When `input_variables` contains lists, fzc generates one subdirectory "
"per combination."))

    cells.append(code("""\
out_multi = WORK / "compiled_multi"
fz.fzc(str(TMPL),
       {"P": [1.0, 2.0, 3.0], "V": [10.0, 20.0], "n": [1.0]},
       MODEL,
       output_dir=str(out_multi))

dirs = sorted(d for d in out_multi.iterdir() if d.is_dir() and not d.name.startswith("."))
print(f"Created {len(dirs)} case directories:")
for d in dirs:
    print(f"  {d.name}")
"""))

    cells.append(md("## 9 · `fzo` — parse outputs (offline)\n\n"
"After the simulator has run, `fzo` harvests output values from "
"directories matching a glob pattern."))

    cells.append(code("""\
import subprocess
# Manually run one case so we have output.txt to parse
case_path = dirs[0]
subprocess.run(["python3", str(SIM.resolve())], cwd=str(case_path), check=True)
print("output.txt preview:")
print((case_path / "output.txt").read_text())

# Parse with fzo
result_fzo = fz.fzo(str(case_path), MODEL)
print("\\nfzo result:")
print(result_fzo)
"""))

    cells.append(md("## 10 · `fzr` — full parametric run"))

    cells.append(code("""\
CALC = f"sh://python3 {SIM.resolve()}"

df = fz.fzr(
    str(TMPL),
    {"P": [0.5, 1.0, 1.5, 2.0, 2.5],
     "V": [10.0, 20.0, 30.0],
     "n": [1.0]},
    MODEL,
    results_dir=str(WORK / "results"),
    calculators=[CALC],
)
print(f"Shape: {df.shape}  (rows=cases, cols=inputs+outputs+metadata)")
print(df[["P", "V", "n", "temperature", "status"]].to_string(index=False))
"""))

    cells.append(md("## 11 · Visualise"))

    cells.append(code("""\
df["P"] = df["P"].astype(float)
df["V"] = df["V"].astype(float)
df["temperature"] = pd.to_numeric(df["temperature"], errors="coerce")

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

for p in sorted(df["P"].unique()):
    sub = df[df["P"] == p].sort_values("V")
    ax1.plot(sub["V"], sub["temperature"], "o-", label=f"P={p} atm")
ax1.set_xlabel("Volume (L)"); ax1.set_ylabel("Temperature (K)")
ax1.set_title("T = PV/nR  — effect of volume"); ax1.legend(); ax1.grid(alpha=.3)

for v in sorted(df["V"].unique()):
    sub = df[df["V"] == v].sort_values("P")
    ax2.plot(sub["P"], sub["temperature"], "s-", label=f"V={v} L")
ax2.set_xlabel("Pressure (atm)"); ax2.set_ylabel("Temperature (K)")
ax2.set_title("T = PV/nR  — effect of pressure"); ax2.legend(); ax2.grid(alpha=.3)

plt.tight_layout()
plt.savefig(str(WORK / "perfectgas.png"), dpi=100)
plt.show()
print("Plot saved to", WORK / "perfectgas.png")
"""))

    cells.append(md("## 12 · Sanity check — compare with analytical formula"))

    cells.append(code("""\
R = 0.08206
df["T_theory"] = df["P"] * df["V"] / (df["n"].astype(float) * R)
df["error_K"] = abs(df["temperature"] - df["T_theory"])
print(df[["P", "V", "temperature", "T_theory", "error_K"]].to_string(index=False))
print(f"\\nMax absolute error: {df['error_K'].max():.2e} K  ✓")
"""))

    nb.cells = cells
    return nb


# ===========================================================================
# NOTEBOOK 2 – Variable Syntax & Formulas
# ===========================================================================
def nb02():
    nb = nbf.v4.new_notebook()
    cells = []

    cells.append(md("""\
# FZ Variable Syntax & Formulas

fz supports a rich template language for input files:

| Feature | Syntax | Example |
|---------|--------|---------|
| Simple variable | `$name` | `$x` |
| Delimited variable | `${name}` | `${x}` |
| Variable with default | `${name~value}` | `${x~3.14}` |
| Formula | `@{expression}` | `@{x * 2 + 1}` |
| Context code line | `#@ code` | `#@ import math` |
| Static constant | `#@: NAME = value` | `#@: PI = 3.14159` |
| Legacy Java syntax | `?(name)` | `?(x)` |

This notebook exhaustively tests each feature.
"""))

    cells.append(code("""\
import json
from pathlib import Path
import fz

fz.set_log_level("WARNING")
WORK = Path("work_02_syntax")
WORK.mkdir(exist_ok=True)

MODEL = {
    "varprefix": "$",
    "formulaprefix": "@",
    "delim": "{}",
    "commentline": "#",
    "output": {},
}
"""))

    cells.append(code(READ_COMPILED_HELPER))

    cells.append(md("## 1 · Simple variables: `$name` and `${name}`"))

    cells.append(code("""\
tmpl = WORK / "simple.in"
tmpl.write_text(
    "radius = $r\\n"
    "diameter = ${d}\\n"
    "area_approx = 3.14159 * $r * $r\\n"
)
vars_ = fz.fzi(str(tmpl), MODEL)
print("Detected:", vars_)

out = WORK / "simple_out"
fz.fzc(str(tmpl), {"r": 5.0, "d": 10.0}, MODEL, output_dir=str(out))
print("\\nCompiled:")
print(read_compiled(out, "simple.in"))
"""))

    cells.append(md("## 2 · Default values: `${name~default}`"))

    cells.append(code("""\
tmpl = WORK / "defaults.in"
tmpl.write_text(
    "speed     = ${v~100.0}   # default 100 m/s\\n"
    "mass      = ${m~1.0}     # default 1 kg\\n"
    "frequency = ${f~50}      # default 50 Hz\\n"
)
vars_ = fz.fzi(str(tmpl), MODEL)
print("Variables with defaults:", vars_)

# Compile WITHOUT overriding — defaults are used
out_def = WORK / "defaults_out_default"
fz.fzc(str(tmpl), {}, MODEL, output_dir=str(out_def))
print("\\nCompiled with no overrides (uses defaults):")
print(read_compiled(out_def, "defaults.in"))

# Compile overriding some
out_ov = WORK / "defaults_out_override"
fz.fzc(str(tmpl), {"v": 200.0, "f": 60}, MODEL, output_dir=str(out_ov))
print("Compiled with v=200, f=60  (m stays at default 1.0):")
print(read_compiled(out_ov, "defaults.in"))
"""))

    cells.append(md("## 3 · Formula evaluation: `@{expression}`\n\n"
"Formulas are evaluated with the Python interpreter at compile time."))

    cells.append(code("""\
tmpl = WORK / "formulas.in"
tmpl.write_text(
    "# Basic formula\\n"
    "x = ${x~2.0}\\n"
    "y = ${y~3.0}\\n"
    "sum_sq  = @{$x**2 + $y**2}\\n"
    "product = @{$x * $y}\\n"
    "dist    = @{($x**2 + $y**2)**0.5}\\n"
)
vars_ = fz.fzi(str(tmpl), MODEL)
print("Variables:", vars_)

out = WORK / "formulas_out"
fz.fzc(str(tmpl), {"x": 3.0, "y": 4.0}, MODEL, output_dir=str(out))
print("\\nCompiled (expected: sum_sq=25, product=12, dist=5):")
print(read_compiled(out, "formulas.in"))
"""))

    cells.append(md("## 4 · Context code lines: `#@ code`\n\n"
"Lines starting with `#@` define helper functions or imports "
"available inside `@{}` formulas."))

    cells.append(code("""\
tmpl = WORK / "context.in"
tmpl.write_text(
    "#@ import math\\n"
    "#@ def celsius_to_kelvin(c):\\n"
    "#@     return c + 273.15\\n"
    "#@ def beam_deflection(F, L, E, I):\\n"
    "#@     return F * L**3 / (48 * E * I)\\n"
    "\\n"
    "T_celsius = ${T_celsius~20.0}\\n"
    "temperature_K = @{celsius_to_kelvin($T_celsius)}\\n"
    "force     = ${F~1000.0}\\n"
    "length    = ${L~2.0}\\n"
    "youngs    = ${E~200e9}\\n"
    "inertia   = ${I~8.333e-6}\\n"
    "deflection_mm = @{beam_deflection($F, $L, $E, $I) * 1000}\\n"
)
vars_ = fz.fzi(str(tmpl), MODEL)
print("Variables:", vars_)

out = WORK / "context_out"
fz.fzc(str(tmpl), {"T_celsius": 25.0, "F": 5000.0, "L": 3.0, "E": 200e9, "I": 8.333e-6},
       MODEL, output_dir=str(out))
print("\\nCompiled:")
print(read_compiled(out, "context.in"))
"""))

    cells.append(md("## 5 · Static constants: `#@: NAME = value`\n\n"
"Static constants are defined once and reused in formulas.  "
"They are **not** treated as input variables."))

    cells.append(code("""\
tmpl = WORK / "static.in"
tmpl.write_text(
    "#@: G = 9.81\\n"
    "#@: PI = 3.14159265\\n"
    "\\n"
    "# Pendulum period: T = 2*PI*sqrt(L/G)\\n"
    "L = ${L~1.0}\\n"
    "period = @{2 * PI * (L / G) ** 0.5}\\n"
    "\\n"
    "# Kinetic energy: Ek = 0.5*m*v^2\\n"
    "m = ${m~1.0}\\n"
    "v = ${v~10.0}\\n"
    "Ek = @{0.5 * m * v**2}\\n"
)
vars_ = fz.fzi(str(tmpl), MODEL)
print("Input variables (G and PI not listed — they are static constants):")
print(vars_)

out = WORK / "static_out"
fz.fzc(str(tmpl), {"L": 0.5, "m": 2.0, "v": 5.0}, MODEL, output_dir=str(out))
print("\\nCompiled:")
print(read_compiled(out, "static.in"))
"""))

    cells.append(md("## 6 · Legacy Java/Funz syntax: `?(name)`"))

    cells.append(code("""\
tmpl = WORK / "legacy.in"
tmpl.write_text(
    "# Legacy Funz Java variable syntax — fz auto-converts it\\n"
    "x = ?(x)\\n"
    "y = ?(y)\\n"
    "z = ?(z~0.0)\\n"
)
vars_ = fz.fzi(str(tmpl), MODEL)
print("Variables from legacy syntax:", vars_)

out = WORK / "legacy_out"
fz.fzc(str(tmpl), {"x": 1.0, "y": 2.0}, MODEL, output_dir=str(out))
print("\\nCompiled:")
print(read_compiled(out, "legacy.in"))
"""))

    cells.append(md("## 7 · Custom model key aliases\n\n"
"Model keys accept multiple aliases: `varprefix`/`varchar`/`var_prefix`/`var_char`."))

    cells.append(code("""\
for var_key in ("varprefix", "varchar", "var_prefix", "var_char"):
    m = {var_key: "$", "formulaprefix": "@", "delim": "{}", "commentline": "#", "output": {}}
    tmpl2 = WORK / f"alias_{var_key}.in"
    tmpl2.write_text("x = ${x~1.0}\\n")
    v = fz.fzi(str(tmpl2), m)
    print(f"  {var_key:15s} → {v}")
"""))

    cells.append(md("## 8 · Different delimiter styles"))

    cells.append(code("""\
configs = [
    ("()",  "x = $(x~1.0)"),
    ("{}",  "x = ${x~1.0}"),
    ("[]",  "x = $[x~1.0]"),
    ("<>",  "x = $<x~1.0>"),
]
for delim, line in configs:
    m = {"varprefix": "$", "delim": delim, "commentline": "#", "output": {}}
    f = WORK / f"delim_{delim[0]}.in"
    f.write_text(line + "\\n")
    v = fz.fzi(str(f), m)
    print(f"  delim={delim!r:5s}  template={line!r:25s}  → {v}")
"""))

    cells.append(md("## 9 · Complex formulas: chained context + multi-var"))

    cells.append(code("""\
tmpl = WORK / "complex.in"
tmpl.write_text(
    "#@: PI = 3.14159265358979\\n"
    "#@: G = 9.81\\n"
    "#@ def sphere_volume(r):\\n"
    "#@     return (4/3) * PI * r**3\\n"
    "#@ def projectile_range(v0, angle_deg):\\n"
    "#@     import math\\n"
    "#@     a = math.radians(angle_deg)\\n"
    "#@     return v0**2 * math.sin(2*a) / G\\n"
    "radius   = ${r~1.0}\\n"
    "v0       = ${v0~20.0}\\n"
    "angle    = ${angle~45.0}\\n"
    "volume   = @{sphere_volume($r)}\\n"
    "range_m  = @{projectile_range($v0, $angle)}\\n"
)
vars_ = fz.fzi(str(tmpl), MODEL)
print("Variables:", vars_)

out = WORK / "complex_out"
fz.fzc(str(tmpl), {"r": 2.5, "v0": 50.0, "angle": 30.0}, MODEL, output_dir=str(out))
print("\\nCompiled  (vol ≈ 65.45 m³; range ≈ 220.4 m):")
print(read_compiled(out, "complex.in"))
"""))

    cells.append(md("## 10 · `fzr` with formula-bearing templates"))

    cells.append(code("""\
SIM = WORK / "models" / "sim.py"
(WORK / "models").mkdir(exist_ok=True)
SIM.write_text('''#!/usr/bin/env python3
params = {}
with open("complex.in") as fh:
    for line in fh:
        line = line.split("#")[0].strip()
        if "=" in line and not line.startswith("@"):
            k, v = line.split("=", 1)
            try:
                params[k.strip()] = float(v.strip())
            except ValueError:
                pass
with open("output.txt", "w") as fh:
    for k, v in params.items():
        fh.write(f"{k} = {v}\\\\n")
''')

MODEL2 = {
    "varprefix": "$", "formulaprefix": "@", "delim": "{}",
    "commentline": "#",
    "output": {
        "volume":   "grep '^volume' output.txt | awk '{print $3}'",
        "range_m":  "grep '^range_m' output.txt | awk '{print $3}'",
    }
}

import pandas as pd
CALC = f"sh://python3 {SIM.resolve()}"
df = fz.fzr(
    str(tmpl),
    {"r": [1.0, 2.0, 3.0], "v0": [20.0, 40.0], "angle": [30.0, 45.0, 60.0]},
    MODEL2,
    results_dir=str(WORK / "results"),
    calculators=[CALC],
)
df["volume"]  = df["volume"].astype(float)
df["range_m"] = df["range_m"].astype(float)
print(df[["r", "v0", "angle", "volume", "range_m"]].to_string(index=False))
"""))

    nb.cells = cells
    return nb


# ===========================================================================
# NOTEBOOK 3 – Parametric Studies with fzr
# ===========================================================================
def nb03():
    nb = nbf.v4.new_notebook()
    cells = []

    cells.append(md("""\
# FZ Parametric Studies with `fzr`

In this notebook we run **parametric studies** on a simply-supported beam
deflection model:

> **δ = F L³ / (48 E I)**

Topics covered:
- Grid inputs (dict with lists) → automatic Cartesian product
- DataFrame inputs (explicit scenarios)
- Progress callbacks
- Parallel calculators (race-to-finish)
- Results analysis and visualisation
"""))

    cells.append(code("""\
import json, time
from pathlib import Path
import fz
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.cm as cm

fz.set_log_level("WARNING")
WORK = Path("work_03_parametric")
WORK.mkdir(exist_ok=True)
(WORK / "models").mkdir(exist_ok=True)
"""))

    cells.append(md("## 1 · Beam simulation script"))

    cells.append(code("""\
SIM = WORK / "models" / "beam.py"
SIM.write_text('''#!/usr/bin/env python3
\"\"\"Simply-supported beam: delta = F*L^3 / (48*E*I)\"\"\"
params = {}
with open("beam.in") as fh:
    for line in fh:
        line = line.split("#")[0].strip()
        if "=" in line:
            k, v = line.split("=", 1)
            params[k.strip()] = float(v.strip())

F = params["F"]
L = params["L"]
E = params["E"]
I = params["I"]

delta    = F * L**3 / (48 * E * I)
delta_mm = delta * 1000

with open("output.txt", "w") as fh:
    fh.write(f"deflection_m  = {delta:.8f}\\\\n")
    fh.write(f"deflection_mm = {delta_mm:.6f}\\\\n")
    fh.write("status = OK\\\\n")
''')
print("Simulator:", SIM)
"""))

    cells.append(md("## 2 · Template and model"))

    cells.append(code("""\
TMPL = WORK / "beam.in"
TMPL.write_text(
    "F = ${F~10000}      # applied load (N)\\n"
    "L = ${L~5.0}        # beam span (m)\\n"
    "E = ${E~200e9}      # Young's modulus (Pa)\\n"
    "I = ${I~8.333e-6}   # second moment of area (m^4)\\n"
)

MODEL = {
    "varprefix": "$", "formulaprefix": "@",
    "delim": "{}", "commentline": "#",
    "output": {
        "deflection_m":  "grep '^deflection_m '  output.txt | awk '{print $3}'",
        "deflection_mm": "grep '^deflection_mm ' output.txt | awk '{print $3}'",
    },
}
CALC = f"sh://python3 {SIM.resolve()}"
print("Template and model ready.")
"""))

    cells.append(md("## 3 · Grid inputs — Cartesian product"))

    cells.append(code("""\
df_grid = fz.fzr(
    str(TMPL),
    {
        "F": [5_000, 10_000, 20_000, 50_000],
        "L": [3.0, 5.0, 7.0],
        "E": [200e9],
        "I": [8.333e-6],
    },
    MODEL,
    results_dir=str(WORK / "results_grid"),
    calculators=[CALC],
)
df_grid["F"]  = df_grid["F"].astype(float)
df_grid["L"]  = df_grid["L"].astype(float)
df_grid["deflection_mm"] = pd.to_numeric(df_grid["deflection_mm"], errors="coerce")

print(f"Grid: {len(df_grid)} cases")
print(df_grid[["F", "L", "deflection_mm"]].to_string(index=False))
"""))

    cells.append(md("## 4 · DataFrame inputs — explicit scenarios\n\n"
"Pass a `pandas.DataFrame` to specify *exact* cases (no Cartesian product)."))

    cells.append(code("""\
scenarios = pd.DataFrame([
    {"F": 2_000,  "L": 4.0, "E": 11e9,  "I": 1.667e-6, "label": "timber_light"},
    {"F": 5_000,  "L": 6.0, "E": 11e9,  "I": 5.208e-6, "label": "timber_medium"},
    {"F": 10_000, "L": 8.0, "E": 11e9,  "I": 1.25e-5,  "label": "timber_heavy"},
    {"F": 10_000, "L": 5.0, "E": 200e9, "I": 8.333e-6, "label": "steel_HEB200"},
    {"F": 50_000, "L": 10.0,"E": 200e9, "I": 4.57e-4,  "label": "steel_HEB400"},
])
print("Scenarios:")
print(scenarios[["label", "F", "L"]].to_string(index=False))

df_scenarios = fz.fzr(
    str(TMPL),
    scenarios[["F", "L", "E", "I"]],
    MODEL,
    results_dir=str(WORK / "results_scenarios"),
    calculators=[CALC],
)
df_scenarios["deflection_mm"] = pd.to_numeric(df_scenarios["deflection_mm"], errors="coerce")
df_scenarios["label"] = scenarios["label"].values
print("\\nResults:")
print(df_scenarios[["label", "F", "L", "deflection_mm"]].to_string(index=False))
"""))

    cells.append(md("## 5 · Progress callbacks\n\n"
"fzr accepts a `callbacks` dict with hooks fired at different stages.  \n\n"
"Signatures:\n"
"- `on_start(total_cases, calculators)`\n"
"- `on_case_start(case_index, total_cases, var_combo)`\n"
"- `on_case_complete(case_index, total_cases, var_combo, status, result)`\n"
"- `on_progress(completed, total, eta_seconds)`\n"
"- `on_complete(total_cases, completed_cases, results)`"))

    cells.append(code("""\
from datetime import datetime

log = []

def on_start(total_cases, calculators):
    log.append(f"START  total={total_cases}  calcs={len(calculators)}")

def on_case_start(case_index, total_cases, var_combo):
    log.append(f"CASE_START  {case_index+1}/{total_cases}  {var_combo}")

def on_case_complete(case_index, total_cases, var_combo, status, result):
    log.append(f"CASE_DONE   {case_index+1}/{total_cases}  status={status}")

def on_progress(completed, total, eta_seconds):
    log.append(f"PROGRESS {completed}/{total}  eta={eta_seconds:.0f}s")

def on_complete(total_cases, completed_cases, results):
    log.append(f"COMPLETE  done={completed_cases}/{total_cases}")

fz.fzr(
    str(TMPL),
    {"F": [5_000, 10_000], "L": [3.0, 5.0], "E": [200e9], "I": [8.333e-6]},
    MODEL,
    results_dir=str(WORK / "results_callbacks"),
    calculators=[CALC],
    callbacks={
        "on_start":         on_start,
        "on_case_start":    on_case_start,
        "on_case_complete": on_case_complete,
        "on_progress":      on_progress,
        "on_complete":      on_complete,
    },
)
print("Callback log:")
for entry in log:
    print(" ", entry)
"""))

    cells.append(md("## 6 · Parallel calculators (race-to-finish)\n\n"
"Passing *multiple* calculators runs them **simultaneously** per case.  "
"The first to finish wins — useful on heterogeneous clusters."))

    cells.append(code("""\
SIM_SLOW = WORK / "models" / "beam_slow.sh"
SIM_SLOW.write_text(f'#!/bin/bash\\nsleep 1\\npython3 {SIM.resolve()} "$@"\\n')
SIM_SLOW.chmod(0o755)

t0 = time.time()
df_par = fz.fzr(
    str(TMPL),
    {"F": [5_000, 20_000], "L": [4.0, 6.0], "E": [200e9], "I": [8.333e-6]},
    MODEL,
    results_dir=str(WORK / "results_parallel"),
    calculators=[
        f"sh://bash {SIM_SLOW.resolve()}",   # slow (1 s extra)
        CALC,                                 # fast  (immediate)
    ],
)
elapsed = time.time() - t0
print(f"Parallel run: {elapsed:.1f}s for {len(df_par)} cases")
print(df_par[["F", "L", "deflection_mm", "calculator", "status"]].to_string(index=False))
"""))

    cells.append(md("## 7 · Visualisation"))

    cells.append(code("""\
fig, axes = plt.subplots(1, 2, figsize=(14, 5))

# Pivot for the heatmap
pivot = df_grid.pivot_table(values="deflection_mm", index="F", columns="L")
im = axes[0].imshow(pivot.values, aspect="auto", cmap="YlOrRd",
                    extent=[pivot.columns.min(), pivot.columns.max(),
                            float(pivot.index.min()), float(pivot.index.max())])
axes[0].set_xlabel("Span L (m)"); axes[0].set_ylabel("Load F (N)")
axes[0].set_title("Beam deflection (mm)"); plt.colorbar(im, ax=axes[0], label="mm")

colours = cm.Set2(range(len(df_scenarios)))
axes[1].barh(df_scenarios["label"], df_scenarios["deflection_mm"], color=colours)
axes[1].set_xlabel("Deflection (mm)")
axes[1].set_title("Beam deflection by scenario"); axes[1].grid(axis="x", alpha=.3)

plt.tight_layout()
plt.savefig(str(WORK / "beam_results.png"), dpi=100)
plt.show()
print("Plot saved.")
"""))

    nb.cells = cells
    return nb


# ===========================================================================
# NOTEBOOK 4 – Design of Experiments with fzd
# ===========================================================================
def nb04():
    nb = nbf.v4.new_notebook()
    cells = []

    cells.append(md("""\
# FZ Design of Experiments with `fzd`

`fzd` drives **iterative, adaptive sampling** via pluggable algorithms.
Each iteration asks the algorithm for new design points, runs the model,
and feeds results back until the algorithm converges.

| # | Problem | Algorithm | Purpose |
|---|---------|-----------|---------|
| A | Exploration of Himmelblau's surface | Random Sampling | Visualise the landscape |
| B | 1-D root-finding on a noisy curve | Brent | Locate zero crossing |
| C | 2-D optimisation of Rosenbrock function | BFGS | Find global minimum |
| D | Monte Carlo π estimation | Monte Carlo | Estimate an integral |
"""))

    cells.append(code("""\
import json, shutil
from pathlib import Path
import fz
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

fz.set_log_level("WARNING")

# Always start fresh so fzd cache never picks up stale results
WORK = Path("work_04_doe")
if WORK.exists():
    shutil.rmtree(WORK)
WORK.mkdir()
(WORK / "models").mkdir()

# Resolve algorithm paths
ALGO_BASE = Path("../algorithms")
def algo(name):
    candidates = [
        ALGO_BASE / f"{name}.py",
        Path(f"/home/richet/Sync/Open/Funz/github/fz/examples/algorithms/{name}.py"),
    ]
    for p in candidates:
        if p.exists():
            return str(p)
    raise FileNotFoundError(f"Algorithm {name} not found")
"""))

    cells.append(md("### Setup: simulators"))

    cells.append(code("""\
# ---- Himmelblau: f(x,y) = (x^2+y-11)^2 + (x+y^2-7)^2  (4 minima at 0) ----
SIM_H = WORK / "models" / "himmelblau.py"
SIM_H.write_text('''#!/usr/bin/env python3
params = {}
with open("h.in") as fh:
    for line in fh:
        line = line.split("#")[0].strip()
        if "=" in line:
            k, v = line.split("=", 1)
            params[k.strip()] = float(v.strip())
x, y = params["x"], params["y"]
f = (x**2 + y - 11)**2 + (x + y**2 - 7)**2
with open("output.txt", "w") as fh:
    fh.write(f"f = {f:.10f}\\\\n")
''')
TMPL_H = WORK / "h.in"
TMPL_H.write_text("x = ${x~0.0}\\ny = ${y~0.0}\\n")
MODEL_H = {"varprefix": "$", "delim": "{}", "commentline": "#",
           "output": {"f": "grep '^f = ' output.txt | awk '{print $3}'"}}
CALC_H = f"sh://python3 {SIM_H.resolve()}"

# ---- Rosenbrock: f(x,y) = (1-x)^2 + 100*(y-x^2)^2  (min at (1,1)=0) ----
SIM_R = WORK / "models" / "rosenbrock.py"
SIM_R.write_text('''#!/usr/bin/env python3
params = {}
with open("r.in") as fh:
    for line in fh:
        line = line.split("#")[0].strip()
        if "=" in line:
            k, v = line.split("=", 1)
            params[k.strip()] = float(v.strip())
x, y = params["x"], params["y"]
f = (1 - x)**2 + 100 * (y - x**2)**2
with open("output.txt", "w") as fh:
    fh.write(f"f = {f:.10f}\\\\n")
''')
TMPL_R = WORK / "r.in"
TMPL_R.write_text("x = ${x~0.0}\\ny = ${y~0.0}\\n")
MODEL_R = {"varprefix": "$", "delim": "{}", "commentline": "#",
           "output": {"f": "grep '^f = ' output.txt | awk '{print $3}'"}}
CALC_R = f"sh://python3 {SIM_R.resolve()}"

# ---- 1-D noisy curve: g(x) = x^3 - 4x + cos(x)  (root near x≈1.86) ----
SIM_1D = WORK / "models" / "curve1d.py"
SIM_1D.write_text('''#!/usr/bin/env python3
import math
params = {}
with open("c.in") as fh:
    for line in fh:
        line = line.split("#")[0].strip()
        if "=" in line:
            k, v = line.split("=", 1)
            params[k.strip()] = float(v.strip())
x = params["x"]
g = x**3 - 4*x + math.cos(x)
with open("output.txt", "w") as fh:
    fh.write(f"g = {g:.10f}\\\\n")
''')
TMPL_1D = WORK / "c.in"
TMPL_1D.write_text("x = ${x~0.0}\\n")
MODEL_1D = {"varprefix": "$", "delim": "{}", "commentline": "#",
            "output": {"g": "grep '^g = ' output.txt | awk '{print $3}'"}}
CALC_1D = f"sh://python3 {SIM_1D.resolve()}"

print("All simulators ready.")
"""))

    cells.append(md("### Setup: Monte Carlo π simulator"))

    cells.append(code("""\
SIM_MC = WORK / "models" / "montecarlo_pi.py"
SIM_MC.write_text('''#!/usr/bin/env python3
import random
params = {}
with open("mc.in") as fh:
    for line in fh:
        line = line.split("#")[0].strip()
        if "=" in line:
            k, v = line.split("=", 1)
            params[k.strip()] = float(v.strip())
n = int(params["n_samples"])
seed = int(params["seed"])
random.seed(seed)
inside = sum(1 for _ in range(n)
             if random.random()**2 + random.random()**2 <= 1.0)
pi_est = 4 * inside / n
error  = abs(pi_est - 3.14159265358979)
with open("output.txt", "w") as fh:
    fh.write(f"pi_estimate = {pi_est:.8f}\\\\n")
    fh.write(f"error = {error:.8f}\\\\n")
''')
TMPL_MC = WORK / "mc.in"
TMPL_MC.write_text("n_samples = ${n_samples~1000}\\nseed = ${seed~42}\\n")
MODEL_MC = {
    "varprefix": "$", "delim": "{}", "commentline": "#",
    "output": {
        "pi_estimate": "grep '^pi_estimate' output.txt | awk '{print $3}'",
        "error":       "grep '^error '     output.txt | awk '{print $3}'",
    },
}
CALC_MC = f"sh://python3 {SIM_MC.resolve()}"
print("Monte Carlo simulator ready.")
"""))

    cells.append(md("## A · Random sampling — explore Himmelblau's surface"))

    cells.append(code("""\
result_rs = fz.fzd(
    str(TMPL_H),
    {"x": "[-5.0;5.0]", "y": "[-5.0;5.0]"},
    MODEL_H,
    output_expression="f",
    algorithm=algo("randomsampling"),
    algorithm_options={"nvalues": 40, "seed": 0},
    calculators=[CALC_H],
    analysis_dir=str(WORK / "doe_random"),
)
df_rs = result_rs["XY"]
df_rs["f"] = df_rs["f"].astype(float)
print(f"Sampled {len(df_rs)} points.  f range: [{df_rs['f'].min():.2f}, {df_rs['f'].max():.2f}]")
print("Summary:", result_rs["summary"])
"""))

    cells.append(code("""\
xx, yy = np.meshgrid(np.linspace(-5, 5, 200), np.linspace(-5, 5, 200))
ff = (xx**2 + yy - 11)**2 + (xx + yy**2 - 7)**2

fig, ax = plt.subplots(figsize=(8, 6))
c = ax.contourf(xx, yy, ff, levels=40, cmap="viridis")
ax.scatter(df_rs["x"].astype(float), df_rs["y"].astype(float),
           c="white", s=30, edgecolors="black", lw=0.5,
           label=f"samples (n={len(df_rs)})")
plt.colorbar(c, label="f(x,y)")
ax.set_xlabel("x"); ax.set_ylabel("y")
ax.set_title("Himmelblau's function — random sampling exploration")
ax.legend(); plt.tight_layout()
plt.savefig(str(WORK / "random_sampling.png"), dpi=100)
plt.show()
print("Plot saved.")
"""))

    cells.append(md("## B · 1-D minimisation with Brent's method\n\n"
"The bundled `brent.py` is a **1-D optimiser** (minimiser) based on "
"parabolic interpolation + golden section.  "
"We minimise a smooth unimodal function to find its minimum."))

    cells.append(code("""\
# ---- 1-D smooth function with a clear minimum inside [0, 3] ----
# f(x) = (x - 1.6)^2 + 0.2*sin(5*x)   → minimum near x ≈ 1.6
SIM_1D.write_text('''#!/usr/bin/env python3
import math
params = {}
with open("c.in") as fh:
    for line in fh:
        line = line.split("#")[0].strip()
        if "=" in line:
            k, v = line.split("=", 1)
            params[k.strip()] = float(v.strip())
x = params["x"]
g = (x - 1.6)**2 + 0.2 * math.sin(5 * x)
with open("output.txt", "w") as fh:
    fh.write(f"g = {g:.10f}\\\\n")
''')

result_brent = fz.fzd(
    str(TMPL_1D),
    {"x": "[0.0;3.0]"},
    MODEL_1D,
    output_expression="g",        # minimise this
    algorithm=algo("brent"),
    algorithm_options={"tol": 1e-6, "max_iter": 50},
    calculators=[CALC_1D],
    analysis_dir=str(WORK / "doe_brent"),
)
df_brent = result_brent["XY"]
print(result_brent["summary"])
best_b = df_brent.loc[df_brent["g"].astype(float).idxmin()]
print(f"Minimum found:  x = {float(best_b['x']):.6f},  f = {float(best_b['g']):.8f}")
print(f"Analytical min: x ≈ 2.008, f ≈ 0.051  (verified with scipy)")
"""))

    cells.append(code("""\
import math
xs_plot = np.linspace(0, 3, 300)
gs_plot = [(x - 1.6)**2 + 0.2 * math.sin(5 * x) for x in xs_plot]

fig, ax = plt.subplots(figsize=(9, 5))
ax.plot(xs_plot, gs_plot, "k-", lw=2, label="f(x) = (x−1.6)² + 0.2·sin(5x)")
ax.scatter(df_brent["x"].astype(float), df_brent["g"].astype(float),
           c=range(len(df_brent)), cmap="plasma", s=60, zorder=5,
           label=f"Brent evaluations (n={len(df_brent)})")
ax.scatter([float(best_b["x"])], [float(best_b["g"])],
           c="red", s=150, marker="*", zorder=10,
           label=f"Best: x={float(best_b['x']):.4f}")
ax.set_xlabel("x"); ax.set_ylabel("f(x)")
ax.set_title("Brent 1-D minimisation")
ax.legend(); ax.grid(alpha=.3)
plt.tight_layout()
plt.savefig(str(WORK / "brent_result.png"), dpi=100)
plt.show()
"""))

    cells.append(md("## C · 2-D optimisation with BFGS"))

    cells.append(code("""\
result_bfgs = fz.fzd(
    str(TMPL_R),
    {"x": "[-2.0;2.0]", "y": "[-1.0;3.0]"},
    MODEL_R,
    output_expression="f",
    algorithm=algo("bfgs"),
    algorithm_options={"max_iter": 100, "tol": 1e-6},
    calculators=[CALC_R],
    analysis_dir=str(WORK / "doe_bfgs"),
)
df_bfgs = result_bfgs["XY"]
df_bfgs["f"] = df_bfgs["f"].astype(float)
best = df_bfgs.loc[df_bfgs["f"].idxmin()]
print(result_bfgs["summary"])
print(f"Best: x={float(best['x']):.6f}, y={float(best['y']):.6f}, f={best['f']:.8f}")
print(f"Theoretical minimum: x=1, y=1, f=0")
"""))

    cells.append(code("""\
xx, yy = np.meshgrid(np.linspace(-2, 2, 300), np.linspace(-1, 3, 300))
ff = (1 - xx)**2 + 100 * (yy - xx**2)**2

fig, ax = plt.subplots(figsize=(8, 6))
c = ax.contourf(xx, yy, np.log1p(ff), levels=50, cmap="hot_r")
ax.plot(df_bfgs["x"].astype(float), df_bfgs["y"].astype(float),
        "w.-", lw=1.5, ms=6, label="BFGS path")
ax.scatter([1], [1], c="lime", s=200, marker="*", zorder=10, label="True min (1,1)")
ax.scatter([float(best["x"])], [float(best["y"])], c="cyan", s=100, marker="D",
           zorder=10, label=f"Found ({float(best['x']):.3f},{float(best['y']):.3f})")
plt.colorbar(c, label="log(1+f)")
ax.set_xlabel("x"); ax.set_ylabel("y")
ax.set_title("Rosenbrock function — BFGS optimisation")
ax.legend(); plt.tight_layout()
plt.savefig(str(WORK / "bfgs_result.png"), dpi=100)
plt.show()
"""))

    cells.append(md("## D · Monte Carlo π estimation\n\n"
"Sweep `seed` and `n_samples` to see how estimate variance scales with 1/√n."))

    cells.append(code("""\
df_mc = fz.fzr(
    str(TMPL_MC),
    {"n_samples": [100, 1_000, 10_000, 100_000],
     "seed": list(range(10))},
    MODEL_MC,
    results_dir=str(WORK / "results_mc"),
    calculators=[CALC_MC],
)
df_mc["n_samples"]   = df_mc["n_samples"].astype(int)
df_mc["pi_estimate"] = pd.to_numeric(df_mc["pi_estimate"], errors="coerce")
df_mc["error"]       = pd.to_numeric(df_mc["error"],       errors="coerce")

stats = df_mc.groupby("n_samples")["pi_estimate"].agg(["mean", "std", "min", "max"])
stats.columns = ["mean_π", "std_π", "min_π", "max_π"]
print("Monte Carlo π estimation statistics:")
print(stats.to_string())
"""))

    cells.append(code("""\
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))

ns = sorted(df_mc["n_samples"].unique())
positions = list(range(len(ns)))
for i, n in enumerate(ns):
    vals = df_mc[df_mc["n_samples"] == n]["pi_estimate"].dropna()
    ax1.boxplot(vals, positions=[i], widths=0.6, patch_artist=True,
                boxprops=dict(facecolor=plt.cm.Blues(0.4+0.15*i)))
ax1.axhline(np.pi, color="red", ls="--", label=f"True π = {np.pi:.5f}")
ax1.set_xticks(positions); ax1.set_xticklabels([str(n) for n in ns])
ax1.set_xlabel("n_samples"); ax1.set_ylabel("π estimate")
ax1.set_title("π estimate distribution"); ax1.legend(); ax1.grid(alpha=.3)

ax2.loglog(stats.index, stats["std_π"], "o-b", label="σ(π estimate)")
ax2.loglog(stats.index, 1/np.sqrt(stats.index), "r--", label="1/√n (theory)")
ax2.set_xlabel("n_samples"); ax2.set_ylabel("Std deviation")
ax2.set_title("Monte Carlo convergence rate"); ax2.legend(); ax2.grid(alpha=.3, which="both")

plt.tight_layout()
plt.savefig(str(WORK / "montecarlo_pi.png"), dpi=100)
plt.show()
"""))

    cells.append(md("## E · Comparing algorithms"))

    cells.append(code("""\
print("Algorithm comparison summary:")
print(f"  Random sampling  : {len(df_rs)} evaluations, "
      f"best f={df_rs['f'].min():.4f}")
print(f"  Brent 1-D minimiser: {len(df_brent)} evaluations, "
      f"f_min={df_brent['g'].astype(float).min():.6f}")
print(f"  BFGS optimiser   : {len(df_bfgs)} evaluations, "
      f"f_min={df_bfgs['f'].min():.2e}")
"""))

    nb.cells = cells
    return nb


# ===========================================================================
# NOTEBOOK 5 – Caching, Advanced I/O, & Administration
# ===========================================================================
def nb05():
    nb = nbf.v4.new_notebook()
    cells = []

    cells.append(md("""\
# FZ Advanced Features: Caching, I/O, and Administration

Topics covered:

1. **Cache calculator** — reuse previous results without re-running
2. **Numpy array inputs** — pass arrays from numpy/scipy DOE generators
3. **Multi-valued outputs** — multiple output variables in one run
4. **Logging & configuration** — verbosity, interpreter, `print_config`
5. **`fzl` with check** — validate models and calculators
6. **Install / uninstall** — manage model plugins
7. **`fzd` with `algorithm_options`** — fine-tune algorithm behaviour
8. **Coarse-to-fine workflow** — combine cache + adaptive DOE
"""))

    cells.append(code("""\
import json, time, shutil
from pathlib import Path
import fz
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# Start fresh so fzd cache never picks up stale results
WORK = Path("work_05_advanced")
if WORK.exists():
    shutil.rmtree(WORK)
WORK.mkdir()
(WORK / "models").mkdir()

fz.set_log_level("WARNING")
print("fz", fz.__version__)
"""))

    cells.append(md("## 1 · Cache calculator\n\n"
"The `cache://` calculator matches cases by MD5 hash of their compiled "
"input files. If a match exists, it returns the stored result instantly."))

    cells.append(code("""\
SIM_SLOW = WORK / "models" / "slow_sin.py"
SIM_SLOW.write_text('''#!/usr/bin/env python3
import time, math
params = {}
with open("in.txt") as fh:
    for line in fh:
        line = line.split("#")[0].strip()
        if "=" in line:
            k, v = line.split("=", 1)
            params[k.strip()] = float(v.strip())
x = params["x"]
time.sleep(0.3)    # simulate computation time
y = math.sin(x) + 0.5 * math.sin(3*x)
with open("output.txt", "w") as fh:
    fh.write(f"y = {y:.10f}\\\\n")
''')

TMPL_S = WORK / "in.txt"
TMPL_S.write_text("x = ${x~0.0}\\n")
MODEL_S = {
    "varprefix": "$", "delim": "{}", "commentline": "#",
    "output": {"y": "grep '^y = ' output.txt | awk '{print $3}'"},
}
CACHE_DIR = str(WORK / "results_cache")
CALC_REAL  = f"sh://python3 {SIM_SLOW.resolve()}"
xs = list(np.linspace(0, 2*np.pi, 8))

# --- Cold run ---
t0 = time.time()
df1 = fz.fzr(str(TMPL_S), {"x": xs}, MODEL_S,
              results_dir=CACHE_DIR, calculators=[CALC_REAL])
cold = time.time() - t0
print(f"Cold run:  {cold:.2f}s  ({len(df1)} cases)")

# --- Warm run via cache:// ---
t0 = time.time()
df2 = fz.fzr(str(TMPL_S), {"x": xs}, MODEL_S,
              results_dir=str(WORK / "results_from_cache"),
              calculators=[f"cache://{CACHE_DIR}", CALC_REAL])
warm = time.time() - t0
print(f"Warm run:  {warm:.2f}s   speedup: {cold/max(warm,0.001):.1f}x")

df1["y"] = pd.to_numeric(df1["y"], errors="coerce")
df2["y"] = pd.to_numeric(df2["y"], errors="coerce")
diff = abs(df1["y"].sort_values().values - df2["y"].sort_values().values).max()
print(f"Max value diff (cold vs cached): {diff:.2e}  ✓")
"""))

    cells.append(md("## 2 · Numpy array inputs\n\n"
"fzr accepts `numpy.ndarray` values directly inside `input_variables`."))

    cells.append(code("""\
rng = np.random.default_rng(42)
xs_np = rng.uniform(0, 2*np.pi, size=20)   # numpy array

df_np = fz.fzr(
    str(TMPL_S),
    {"x": xs_np},
    MODEL_S,
    results_dir=str(WORK / "results_numpy"),
    calculators=[CALC_REAL],
)
df_np["x"] = df_np["x"].astype(float)
df_np["y"] = pd.to_numeric(df_np["y"], errors="coerce")
print(f"numpy input: {len(xs_np)} points  |  output shape: {df_np.shape}")
print(df_np[["x", "y"]].sort_values("x").to_string(index=False))
"""))

    cells.append(md("## 3 · Multiple output variables\n\n"
"A model can extract several outputs from one run.  "
"All become columns in the result DataFrame."))

    cells.append(code("""\
SIM_MULTI = WORK / "models" / "multi_out.py"
SIM_MULTI.write_text('''#!/usr/bin/env python3
import math
params = {}
with open("multi.in") as fh:
    for line in fh:
        line = line.split("#")[0].strip()
        if "=" in line:
            k, v = line.split("=", 1)
            params[k.strip()] = float(v.strip())
x = params["x"]
with open("output.txt", "w") as fh:
    fh.write(f"sin_x     = {math.sin(x):.8f}\\\\n")
    fh.write(f"cos_x     = {math.cos(x):.8f}\\\\n")
    fh.write(f"x_squared = {x**2:.8f}\\\\n")
    fh.write(f"abs_val   = {abs(x):.8f}\\\\n")
''')

TMPL_M = WORK / "multi.in"
TMPL_M.write_text("x = ${x~0.0}\\n")
MODEL_MULTI = {
    "varprefix": "$", "delim": "{}", "commentline": "#",
    "output": {
        "sin_x":     "grep '^sin_x'     output.txt | awk '{print $3}'",
        "cos_x":     "grep '^cos_x'     output.txt | awk '{print $3}'",
        "x_squared": "grep '^x_squared' output.txt | awk '{print $3}'",
        "abs_val":   "grep '^abs_val'   output.txt | awk '{print $3}'",
    },
}
CALC_M = f"sh://python3 {SIM_MULTI.resolve()}"

df_m = fz.fzr(
    str(TMPL_M),
    {"x": list(np.linspace(-np.pi, np.pi, 9))},
    MODEL_MULTI,
    results_dir=str(WORK / "results_multi"),
    calculators=[CALC_M],
)
for col in ["sin_x", "cos_x", "x_squared", "abs_val"]:
    df_m[col] = pd.to_numeric(df_m[col], errors="coerce")
df_m["x"] = df_m["x"].astype(float)
print("Output columns:", [c for c in df_m.columns if c not in ("path","calculator","status","error","command")])
print(df_m[["x", "sin_x", "cos_x", "x_squared"]].sort_values("x").to_string(index=False))
"""))

    cells.append(md("## 4 · Logging & configuration"))

    cells.append(code("""\
print("=== Default config ===")
fz.print_config()

print("\\n=== Log level cycle ===")
for level in ("QUIET", "ERROR", "WARNING", "INFO", "DEBUG"):
    fz.set_log_level(level)
    print(f"  set({level!r}) → get() = {fz.get_log_level()}")
fz.set_log_level("WARNING")  # reset

print("\\n=== Interpreter ===")
fz.set_interpreter("python")
print(f"  interpreter: {fz.get_interpreter()}")

print("\\n=== Config object attrs ===")
cfg = fz.get_config()
print([a for a in dir(cfg) if not a.startswith("_")])
"""))

    cells.append(md("## 5 · `fzl` with `check=True`\n\n"
"The `check` flag validates each model and calculator."))

    cells.append(code("""\
info = fz.fzl(check=True)
print("Models:")
for name, props in info["models"].items():
    status = props.get("check_status", "?")
    print(f"  {name:25s}  {status}")
print("\\nCalculators:")
for name, props in info["calculators"].items():
    status = props.get("check_status", "?")
    print(f"  {name:35s}  {status}")
"""))

    cells.append(md("## 6 · Install and uninstall a model plugin"))

    cells.append(code("""\
print("Installing fz-moret model (from GitHub)...")
try:
    result = fz.install_model("moret", global_install=False)
    print(f"  Installed: model_name={result['model_name']}")
    print(f"             install_path={result['install_path']}")
except Exception as e:
    print(f"  Note: {e}")

print("\\nModels after install:")
for name in fz.fzl()["models"]:
    print(f"  {name}")

print("\\nUninstalling Moret (local)...")
try:
    fz.uninstall_model("Moret", global_uninstall=False)
    print("  Done.")
except Exception as e:
    print(f"  {e}")

print("\\nModels after uninstall:")
for name in fz.fzl()["models"]:
    print(f"  {name}")
"""))

    cells.append(md("## 7 · `fzd` algorithm_options\n\n"
"Same algorithm, different `nvalues` → different sample sizes."))

    cells.append(code("""\
ALGO_RS_PATH = None
for p in [Path("../algorithms/randomsampling.py"),
          Path("/home/richet/Sync/Open/Funz/github/fz/examples/algorithms/randomsampling.py")]:
    if p.exists():
        ALGO_RS_PATH = str(p)
        break

results_table = []
for n in [10, 25, 50]:
    res = fz.fzd(
        str(TMPL_S),
        {"x": "[0;6.283]"},
        MODEL_S,
        output_expression="y",
        algorithm=ALGO_RS_PATH,
        algorithm_options={"nvalues": n, "seed": 99},
        calculators=[CALC_REAL],
        analysis_dir=str(WORK / f"doe_rs_{n}"),
    )
    df = res["XY"]
    y_vals = df["y"].astype(float)
    results_table.append({"nvalues": n, "n_pts": len(df),
                           "y_mean": y_vals.mean(), "y_std": y_vals.std()})
    print(f"  nvalues={n:3d}  → {len(df)} points, "
          f"y_mean={y_vals.mean():.4f}, y_std={y_vals.std():.4f}")
"""))

    cells.append(md("## 8 · Coarse-to-fine exploration + cache reuse"))

    cells.append(code("""\
# Step 1: coarse exploration
res_coarse = fz.fzd(
    str(TMPL_S), {"x": "[0;6.283]"}, MODEL_S,
    output_expression="y",
    algorithm=ALGO_RS_PATH,
    algorithm_options={"nvalues": 15, "seed": 1},
    calculators=[CALC_REAL],
    analysis_dir=str(WORK / "explore_coarse"),
)
df_coarse = res_coarse["XY"].copy()
df_coarse["x"] = df_coarse["x"].astype(float)
df_coarse["y"] = df_coarse["y"].astype(float)

# Step 2: refine around peak
x_peak = float(df_coarse.loc[df_coarse["y"].idxmax(), "x"])
x_lo   = max(0.0, x_peak - 0.5)
x_hi   = min(2*np.pi, x_peak + 0.5)
print(f"Coarse peak at x ≈ {x_peak:.3f} → refine in [{x_lo:.2f}, {x_hi:.2f}]")

res_fine = fz.fzd(
    str(TMPL_S), {"x": f"[{x_lo};{x_hi}]"}, MODEL_S,
    output_expression="y",
    algorithm=ALGO_RS_PATH,
    algorithm_options={"nvalues": 20, "seed": 2},
    # cache:// avoids re-running any already-computed cases
    calculators=[f"cache://{WORK / 'explore_coarse'}", CALC_REAL],
    analysis_dir=str(WORK / "explore_fine"),
)
df_fine = res_fine["XY"].copy()
df_fine["x"] = df_fine["x"].astype(float)
df_fine["y"] = df_fine["y"].astype(float)

xs_true = np.linspace(0, 2*np.pi, 500)
ys_true = np.sin(xs_true) + 0.5*np.sin(3*xs_true)

fig, ax = plt.subplots(figsize=(10, 5))
ax.plot(xs_true, ys_true, "k-", lw=2, label="true curve")
ax.scatter(df_coarse["x"], df_coarse["y"], c="steelblue", s=40,
           label="coarse samples", zorder=5)
ax.scatter(df_fine["x"],   df_fine["y"],   c="tomato", s=60, marker="^",
           label="fine samples", zorder=6)
ax.axvline(x_peak, color="green", ls="--", label=f"peak x≈{x_peak:.2f}")
ax.set_xlabel("x"); ax.set_ylabel("y"); ax.legend(); ax.grid(alpha=.3)
ax.set_title("Coarse-to-fine exploration with cache reuse")
plt.tight_layout()
plt.savefig(str(WORK / "coarse_to_fine.png"), dpi=100)
plt.show()
print("Plot saved.")
"""))

    nb.cells = cells
    return nb


# ===========================================================================
# Main
# ===========================================================================
if __name__ == "__main__":
    notebooks = [
        (nb01, "01_getting_started.ipynb"),
        (nb02, "02_variable_syntax_and_formulas.ipynb"),
        (nb03, "03_parametric_studies_fzr.ipynb"),
        (nb04, "04_design_of_experiments_fzd.ipynb"),
        (nb05, "05_caching_and_advanced.ipynb"),
    ]
    print("Generating notebooks...")
    for fn, name in notebooks:
        save(fn(), name)
    print("Done.")
