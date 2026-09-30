# Installing Models and Algorithms

> **Contents**: the reference description comes first; the tutorial-style text that used to live in the README follows in the "Guide" sections below.




fz can install ready-made **models** (simulation-code wrappers) and **fzd algorithms**
(design-of-experiments / optimization strategies) from GitHub or local zip files, so you
don't have to author them by hand. This is the first thing to try when wrapping a known
code: an official wrapper may give you the parameterization syntax and output parsers for
free.

## CLI

```bash
# Install a model into the current project (./.fz/models/)
fz install model perfectgas
fz install model https://github.com/Funz/fz-modelica
fz install model ./fz-mycode.zip

# Install globally (~/.fz/models/) so every project can use it
fz install model perfectgas --global

# Install an fzd algorithm (into ./.fz/algorithms/ or, with --global, ~/.fz/algorithms/)
fz install algorithm brent
fz install algorithm https://github.com/Funz/fz-montecarlo

# Remove an installed resource (by name)
fz uninstall model perfectgas
fz uninstall algorithm brent
fz uninstall model perfectgas --global

# See what is installed (models and calculators), optionally validating each
fz list
fz list --check
```

`fz install` requires fz 1.0+.

## Python API

```python
import fz

fz.install_model("perfectgas")                 # → ./.fz/models/
fz.install_model("perfectgas", global_install=True)   # → ~/.fz/models/
fz.install_algorithm("brent")
fz.uninstall_model("perfectgas")
fz.uninstall_algorithm("brent")

fz.list_installed_models()       # dict of installed models
fz.list_installed_algorithms()   # dict of installed algorithms
```

## Source resolution

The `source` argument accepts three forms (resolved by `normalize_github_url`):

| Form | Example | Resolves to |
|------|---------|-------------|
| Short name | `perfectgas` | `https://github.com/Funz/fz-perfectgas` (the `fz-` prefix and `Funz` org are assumed) |
| Full GitHub URL | `https://github.com/you/fz-mycode` | that repository's `main` archive |
| Local zip / path | `./fz-mycode.zip` | the local file, unpacked directly |

By convention an installable repository is named `fz-<code>` and ships a `.fz/` directory:

```
fz-mycode/
└── .fz/
    ├── models/MyCode.json          # the model definition (id, varprefix, output parsers)
    ├── calculators/*.json|*.sh     # optional calculator aliases wired to the model
    └── algorithms/*.py|*.R         # for algorithm repositories
```

On install, fz copies every model JSON of the repository (`.fz/models/*.json`; a
repository may ship several related models) into `.fz/models/` (or `~/.fz/models/` with
`--global`) and any accompanying `.fz/` subdirectories (calculators, algorithms, …)
alongside it.

## Install location and discovery

- **Project-local** (default): `./.fz/` — visible only inside the current project.
- **Global** (`--global`): `~/.fz/` — visible from every project for the current user.

Installed models are then referenced by id (`--model MyCode`), and installed calculator
aliases are auto-discovered, so a single-case run needs no `--calculators` argument. See
[Calculators](calculators.md) for calculator aliases and [Model definition](model-definition.md)
for the model JSON structure, and [Core functions](core-functions.md) for `fzl` / `fz list`.

---

## Guide: Installing Plugins



FZ supports installing models and algorithms as plugins from GitHub repositories, local zip files, or URLs.

### Installing Algorithm Plugins

Algorithm plugins enable design of experiments and optimization workflows. Install algorithms from GitHub repositories in the `fz-<algorithm>` format:

#### From GitHub Repository Name

```bash
# Install from Funz organization (convention: fz-<algorithm>)
fz install algorithm montecarlo

# This installs from: https://github.com/Funz/fz-montecarlo
```

```python
# Python API
import fz

# Install locally (.fz/algorithms/)
fz.install_algorithm("montecarlo")

# Install globally (~/.fz/algorithms/)
fz.install_algorithm("montecarlo", global_install=True)
```

#### From GitHub URL

```bash
# Install from full URL
fz install algorithm https://github.com/YourOrg/fz-custom-algo
```

```python
fz.install_algorithm("https://github.com/YourOrg/fz-custom-algo")
```

#### From Local Zip File

```bash
# Install from downloaded zip
fz install algorithm ./fz-myalgo.zip
```

```python
fz.install_algorithm("./fz-myalgo.zip")
```

#### Using Installed Algorithms

Once installed, algorithms can be referenced by name:

```python
import fz

# Use installed algorithm plugin
results = fz.fzd(
    input_path="input.txt",
    input_variables={"x": "[0;10]", "y": "[-5;5]"},
    model="mymodel",
    output_expression="result",
    algorithm="montecarlo",  # Plugin name (no path or extension)
    calculators=["sh://bash calc.sh"],
    algorithm_options={"batch_sample_size": 20}
)
```

### Installing Model Plugins

Model plugins define input parsing and output extraction patterns. Install models from GitHub:

#### From GitHub Repository Name

```bash
# Install from Funz organization (convention: fz-<model>)
fz install model moret

# This installs from: https://github.com/Funz/fz-moret
```

```python
# Python API
import fz

# Install locally (.fz/models/)
fz.install("moret")

# Install globally (~/.fz/models/)
fz.install("moret", global_install=True)
```

#### From GitHub URL or Local Zip

```bash
fz install model https://github.com/Funz/fz-moret
fz install model ./fz-moret.zip
```

### Listing Installed Plugins

```bash
# List installed algorithms
fz list algorithms

# List only global algorithms
fz list algorithms --global

# List installed models
fz list models

# List only global models
fz list models --global
```

```python
# Python API
import fz

# List algorithms
algorithms = fz.list_algorithms()
for name, info in algorithms.items():
    print(f"{name} ({info['type']}) - {info['file']}")

# List models
models = fz.list_models()
for name, model in models.items():
    print(f"{name}: {model.get('id', 'N/A')}")
```

### Uninstalling Plugins

```bash
# Uninstall algorithm
fz uninstall algorithm montecarlo

# Uninstall from global location
fz uninstall algorithm montecarlo --global

# Uninstall model
fz uninstall model moret
```

```python
# Python API
import fz

# Uninstall algorithm
fz.uninstall_algorithm("montecarlo")

# Uninstall model
fz.uninstall("moret")
```

### Plugin Priority

When the same plugin exists in multiple locations, FZ uses the following priority:

1. **Project-level** (`.fz/algorithms/` or `.fz/models/`) - Highest priority
2. **Global** (`~/.fz/algorithms/` or `~/.fz/models/`) - Fallback

This allows project-specific customization while maintaining a personal library of reusable plugins.

### Creating Algorithm Plugins

To create your own algorithm plugin repository (for sharing or distribution):

1. **Create repository** named `fz-<algorithm>` (e.g., `fz-montecarlo`)

2. **Add algorithm file** as `<algorithm>.py` or `<algorithm>.R` in repository root or `.fz/algorithms/`:

```python
# montecarlo.py
class MonteCarlo:
    def __init__(self, **options):
        self.n_samples = options.get("n_samples", 100)

    def get_initial_design(self, input_vars, output_vars):
        import random
        samples = []
        for _ in range(self.n_samples):
            sample = {}
            for var, (min_val, max_val) in input_vars.items():
                sample[var] = random.uniform(min_val, max_val)
            samples.append(sample)
        return samples

    def get_next_design(self, X, Y):
        return []  # One-shot sampling

    def get_analysis(self, X, Y):
        valid_Y = [y for y in Y if y is not None]
        mean = sum(valid_Y) / len(valid_Y) if valid_Y else 0
        return {"text": f"Mean: {mean:.2f}", "data": {"mean": mean}}
```

3. **Push to GitHub** and share repository URL

4. **Install** using `fz install algorithm <name>` or `fz install algorithm <url>`

See `examples/algorithms/demo_plugin_system.py` and `examples/algorithm_options_example.md` for the algorithm plugin system.
