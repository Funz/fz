# FZ Context Documentation - Index

Quick reference index for finding specific topics in the FZ context documentation.

## Table of Contents

- [Getting Started](#getting-started)
- [Variable Substitution](#variable-substitution)
- [Formula Evaluation](#formula-evaluation)
- [Core Functions](#core-functions)
- [Models](#models)
- [Calculators](#calculators)
- [Parallel Execution](#parallel-execution)
- [Caching](#caching)
- [Examples by Use Case](#examples-by-use-case)
- [CLI Usage](#cli-usage)
- [Troubleshooting](#troubleshooting)

## Getting Started

| Topic | File | Section |
|-------|------|---------|
| What is FZ? | overview.md | "What is FZ?" |
| When to use FZ | overview.md | "When to Use FZ" |
| Quick example | overview.md | "Quick Example" |
| Four core functions | overview.md | "Four Core Functions" |
| Typical workflow | overview.md | "Typical Workflow" |
| Installation | *(see README.md)* | - |

## Variable Substitution

| Topic | File | Section |
|-------|------|---------|
| Basic variable syntax | syntax-guide.md | "Variable Substitution" → "Basic Syntax" |
| Variable naming rules | syntax-guide.md | "Variable Naming Rules" |
| Default values | syntax-guide.md | "Default Values" |
| Delimiters | syntax-guide.md | "Basic Syntax" |
| Common mistakes | syntax-guide.md | "Common Mistakes" |
| Complete examples | syntax-guide.md | "Complete Examples" |

## Formula Evaluation

| Topic | File | Section |
|-------|------|---------|
| Python formulas | formulas-and-interpreters.md | "Basic Formula Syntax" → "Python Formulas" |
| R formulas | formulas-and-interpreters.md | "Basic Formula Syntax" → "R Formulas" |
| Context lines | formulas-and-interpreters.md | "Context Lines" |
| Python context examples | formulas-and-interpreters.md | "Context Lines" → "Python Context" |
| R context examples | formulas-and-interpreters.md | "Context Lines" → "R Context" |
| Python vs R comparison | formulas-and-interpreters.md | "Python vs R Comparison" |
| Setting interpreter | formulas-and-interpreters.md | "Setting Interpreter" |
| Installing R support | formulas-and-interpreters.md | "Installing R Support" |
| Advanced patterns | formulas-and-interpreters.md | "Advanced Patterns" |

## Core Functions

| Topic | File | Section |
|-------|------|---------|
| fzi (parse input) | core-functions.md | "fzi - Parse Input Variables" |
| fzc (compile) | core-functions.md | "fzc - Compile Input Files" |
| fzo (read output) | core-functions.md | "fzo - Read Output Files" |
| fzr (run calculations) | core-functions.md | "fzr - Run Parametric Calculations" |
| Function signatures | core-functions.md | Each function section → "Function Signature" |
| Return values | core-functions.md | Each function section |
| Function comparison | core-functions.md | "Function Comparison" |
| Typical workflows | core-functions.md | "Typical Workflows" |

## Models

| Topic | File | Section |
|-------|------|---------|
| Model structure | model-definition.md | "Basic Model Structure" |
| Model fields explained | model-definition.md | "Model Fields" |
| varprefix | model-definition.md | "Model Fields" → "varprefix" |
| formulaprefix | model-definition.md | "Model Fields" → "formulaprefix" |
| delim | model-definition.md | "Model Fields" → "delim" |
| commentline | model-definition.md | "Model Fields" → "commentline" |
| interpreter | model-definition.md | "Model Fields" → "interpreter" |
| output | model-definition.md | "Model Fields" → "output" |
| Complete model examples | model-definition.md | "Complete Examples" |
| Model aliases | model-definition.md | "Model Aliases" |
| Output extraction | model-definition.md | "Advanced Output Extraction" |
| Best practices | model-definition.md | "Best Practices" |

## Calculators

| Topic | File | Section |
|-------|------|---------|
| Calculator URI format | calculators.md | "Calculator URI Format" |
| Local shell (sh://) | calculators.md | "Local Shell Calculator" |
| Remote SSH (ssh://) | calculators.md | "Remote SSH Calculator" |
| SLURM (slurm://) | calculators.md | "SLURM Workload Manager" |
| Funz server (funz://) | calculators.md | "Funz Server Calculator" |
| Cache (cache://) | calculators.md | "Cache Calculator" |
| Parallel execution | calculators.md | "Multiple Calculators" → "Parallel Execution" |
| Fallback chain | calculators.md | "Multiple Calculators" → "Fallback Chain" |
| Calculator aliases | calculators.md | "Calculator Aliases" |
| SSH authentication | calculators.md | "Remote SSH Calculator" → "Authentication" |
| Best practices | calculators.md | "Best Practices" |

## Parallel Execution

| Topic | File | Section |
|-------|------|---------|
| How parallelization works | parallel-and-caching.md | "Parallel Execution" → "How Parallelization Works" |
| Basic parallel execution | parallel-and-caching.md | "Basic Parallel Execution" |
| Load balancing | parallel-and-caching.md | "Load Balancing" |
| Controlling parallelism | parallel-and-caching.md | "Controlling Parallelism" |
| Optimal worker count | parallel-and-caching.md | "Optimal Number of Workers" |
| Retry mechanism | parallel-and-caching.md | "Retry Mechanism" |
| Interrupt handling | parallel-and-caching.md | "Interrupt Handling" |
| Performance optimization | parallel-and-caching.md | "Performance Optimization" |
| Monitoring progress | parallel-and-caching.md | "Monitoring Progress" |

## Caching

| Topic | File | Section |
|-------|------|---------|
| Cache basics | parallel-and-caching.md | "Caching Strategies" → "Cache Basics" |
| Resume interrupted runs | parallel-and-caching.md | "Strategy 1: Resume Interrupted Runs" |
| Expand parameter space | parallel-and-caching.md | "Strategy 2: Expand Parameter Space" |
| Compare methods | parallel-and-caching.md | "Strategy 3: Compare Multiple Methods" |
| Multi-tier caching | parallel-and-caching.md | "Strategy 4: Multi-tier Caching" |
| Cache matching | calculators.md | "Cache Calculator" → "How it Works" |
| Combining parallel and cache | parallel-and-caching.md | "Combining Parallel and Cache" |

## Examples by Use Case

| Topic | File | Section |
|-------|------|---------|
| Minimal example | quick-examples.md | "Example 1: Minimal Parametric Study" |
| With formulas | quick-examples.md | "Example 2: With Formulas" |
| Parallel execution | quick-examples.md | "Example 3: Parallel Execution" |
| Remote SSH | quick-examples.md | "Example 4: Remote SSH Execution" |
| Cache and resume | quick-examples.md | "Example 5: Cache and Resume" |
| Temperature sweep | quick-examples.md | "Pattern 1: Temperature Sweep" |
| Grid search | quick-examples.md | "Pattern 2: Grid Search (2D Parameter Space)" |
| Sensitivity analysis | quick-examples.md | "Pattern 3: Sensitivity Analysis" |
| Monte Carlo | quick-examples.md | "Pattern 4: Monte Carlo Simulation" |
| Design of experiments | quick-examples.md | "Pattern 5: Design of Experiments (DOE)" |
| Convergence study | quick-examples.md | "Pattern 6: Convergence Study" |
| Method comparison | quick-examples.md | "Pattern 7: Multi-Method Comparison" |
| Optimization loop | quick-examples.md | "Pattern 8: Optimization Loop" |

## CLI Usage

| Topic | File | Section |
|-------|------|---------|
| fzi CLI | quick-examples.md | "CLI Quick Examples" → "Example 1" |
| fzc CLI | quick-examples.md | "CLI Quick Examples" → "Example 2" |
| fzr CLI | quick-examples.md | "CLI Quick Examples" → "Example 3" |
| fzo CLI | quick-examples.md | "CLI Quick Examples" → "Example 4" |
| CLI reference | *(see README.md)* | "CLI Usage" |

## Troubleshooting

| Topic | File | Section |
|-------|------|---------|
| Debug single case | quick-examples.md | "Troubleshooting Examples" → "Debug Single Case" |
| Test calculator manually | quick-examples.md | "Troubleshooting Examples" → "Test Calculator Manually" |
| Verify cache matching | quick-examples.md | "Troubleshooting Examples" → "Verify Cache Matching" |
| Common issues | *(see README.md)* | "Troubleshooting" |
| Debug mode | *(see README.md)* | "Troubleshooting" → "Debug Mode" |

## Integration Examples

| Topic | File | Section |
|-------|------|---------|
| With pandas | quick-examples.md | "Integration Examples" → "Integration with Pandas" |
| With matplotlib | quick-examples.md | "Integration Examples" → "Integration with Matplotlib" |
| With Jupyter | quick-examples.md | "Integration Examples" → "Integration with Jupyter Notebooks" |
| Project structure | quick-examples.md | "Best Practice Examples" → "Organized Project Structure" |

## Quick Lookup: Common Tasks

### "I want to..."

| Task | Start Here |
|------|-----------|
| Get started with FZ | overview.md |
| Write an input template | syntax-guide.md |
| Use formulas to calculate values | formulas-and-interpreters.md |
| Parse input variables | core-functions.md → "fzi" |
| Run a parametric study | core-functions.md → "fzr" |
| Create a model | model-definition.md |
| Run calculations remotely | calculators.md → "Remote SSH Calculator" |
| Speed up my calculations | parallel-and-caching.md |
| Resume an interrupted run | parallel-and-caching.md → "Resume Interrupted Runs" |
| Find example code | quick-examples.md |
| Use R instead of Python | formulas-and-interpreters.md → "R Formulas" |
| Extract results from output | model-definition.md → "output" |
| Set up parallel execution | parallel-and-caching.md → "Basic Parallel Execution" |
| Use caching | calculators.md → "Cache Calculator" |
| Debug my calculation | quick-examples.md → "Troubleshooting Examples" |

## Configuration & Advanced Topics

| Topic | File | Section |
|-------|------|---------|
| FZ_SHELL_PATH overview | shell-path.md | "Overview" |
| Shell path setup | shell-path.md | "Usage" |
| Windows path configuration | shell-path.md | "Common Configurations" → "Windows with MSYS2" |
| Shell path troubleshooting | shell-path.md | "Troubleshooting" |
| Funz protocol overview | funz-protocol.md | "Overview" |
| UDP discovery | funz-protocol.md | "UDP Discovery" |
| Funz TCP protocol | funz-protocol.md | "TCP Protocol" |
| Funz server setup | funz-protocol.md | "Server Setup" |

## Keywords Index

Quick keyword search:

- **Variables**: syntax-guide.md
- **Formulas**: syntax-guide.md, formulas-and-interpreters.md
- **Python**: formulas-and-interpreters.md
- **R**: formulas-and-interpreters.md
- **Model**: model-definition.md
- **Calculator**: calculators.md
- **Parallel**: parallel-and-caching.md
- **Cache**: parallel-and-caching.md, calculators.md
- **SSH**: calculators.md → "Remote SSH Calculator"
- **SLURM**: calculators.md → "SLURM Workload Manager"
- **Funz**: calculators.md → "Funz Server Calculator", funz-protocol.md
- **UDP**: funz-protocol.md → "UDP Discovery"
- **Shell path**: shell-path.md
- **FZ_SHELL_PATH**: shell-path.md
- **Examples**: quick-examples.md
- **CLI**: quick-examples.md → "CLI Quick Examples"
- **DataFrame**: core-functions.md → "fzr", "fzo"
- **Interrupt**: parallel-and-caching.md → "Interrupt Handling"
- **Retry**: parallel-and-caching.md → "Retry Mechanism"
- **Performance**: parallel-and-caching.md → "Performance Optimization"
