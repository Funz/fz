# Documentation

## Main Documentation

- **README.md** (this file) - Complete user guide with examples
- **NEWS.md** - Release notes and changelog (version 0.9.1 and later)
- **doc/funz-protocol.md** - Funz protocol and UDP discovery documentation
- **doc/shell-path.md** - FZ_SHELL_PATH configuration details

## Context Documentation

Modular documentation in the `doc/` directory:

- **doc/INDEX.md** - Documentation overview and navigation
- **doc/overview.md** - High-level FZ concepts and design
- **doc/core-functions.md** - API reference for fzi, fzc, fzo, fzr, fzl, fzd
- **doc/installing-models.md** - Installing models and algorithms (`fz install`)
- **doc/calculators.md** - Calculator types, URIs, and configuration
- **doc/model-definition.md** - Model structure, aliases, and output parsing
- **doc/formulas-and-interpreters.md** - Formula evaluation (Python/R)
- **doc/syntax-guide.md** - Input template syntax reference
- **doc/parallel-and-caching.md** - Performance optimization strategies
- **doc/quick-examples.md** - Common usage patterns and snippets

## Examples

Practical examples in the `examples/` directory:

- **examples/examples.md** - Overview of all examples
- **examples/fzd_example.md** - Iterative design of experiments (fzd) examples
- **examples/dataframe_input.md** - DataFrame input for non-factorial designs
- **examples/vector_outputs_example.md** - Vector/array-valued outputs with fzr and fzo
- **examples/algorithm_options_example.md** - Algorithm options format guide
- **examples/r_interpreter_example.md** - R interpreter setup and usage
- **examples/shell_path_example.md** - FZ_SHELL_PATH configuration examples
- **examples/java_funz_syntax_example.py** - Legacy Funz syntax compatibility
- **examples/fzi_formulas_example.py** - Formula evaluation examples
- **examples/fzi_static_objects_example.py** - Static object handling

## Test Examples

Working examples in test files:

- `tests/test_examples_*.py` - Comprehensive integration tests
- `tests/test_parallel_simple.py`, `tests/test_complete_parallel_execution.py` - Parallel execution examples
- `tests/test_interrupt_handling.py` - Interrupt handling demonstrations
- `tests/test_funz_protocol.py` - Funz server protocol examples
- `tests/test_slurm_runner.py` - SLURM workload manager examples
