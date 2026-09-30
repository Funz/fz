# Features

<!-- counterpart-note -->
> Guide page (from the former README). Reference counterpart in `doc/`: [`overview.md`](../overview.md). When behaviour changes, update both.


## Core Capabilities

- **🔄 Parametric Studies**: Factorial designs (dict with Cartesian product) or non-factorial designs (DataFrame with specific cases)
- **⚡ Parallel Execution**: Run multiple cases concurrently across multiple calculators with automatic load balancing
- **💾 Smart Caching**: Reuse previous calculation results based on input file hashes to avoid redundant computations
- **🔁 Retry Mechanism**: Automatically retry failed calculations with alternative calculators
- **🌐 Remote Execution**: Execute calculations on remote servers via SSH with automatic file transfer
- **📊 DataFrame I/O**: Input and output using pandas DataFrames with automatic type casting and variable extraction
- **🛑 Interrupt Handling**: Gracefully stop long-running calculations with Ctrl+C while preserving partial results
- **🔍 Formula Evaluation**: Support for calculated parameters using Python or R expressions
- **📁 Directory Management**: Automatic organization of inputs, outputs, and logs for each case
- **🎯 Adaptive Algorithms**: Iterative design of experiments with intelligent sampling strategies (fzd)
- **⚠️ Error Reporting**: Protocol-specific error classification with descriptive messages recorded in results
- **🖥️ Cross-Platform**: Works on Linux, macOS, and Windows (MSYS2/Git Bash) with configurable shell paths

## Six Core Functions

1. **`fzi`** - Parse **I**nput files to identify variables
2. **`fzc`** - **C**ompile input files by substituting variable values
3. **`fzo`** - Parse **O**utput files from calculations
4. **`fzr`** - **R**un complete parametric calculations end-to-end
5. **`fzd`** - Run iterative **D**esign of experiments with adaptive algorithms
6. **`fzl`** - **L**ist and validate installed models and calculators
