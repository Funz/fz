# FZ Context for LLMs

This directory contains comprehensive documentation about the FZ framework, structured specifically for Large Language Model (LLM) consumption. These files help LLMs understand FZ syntax, features, and usage patterns to provide better code suggestions and assistance.

## Purpose

These context files are designed to:

- **Guide LLM code generation**: Provide clear examples and patterns for suggesting FZ usage
- **Explain FZ syntax**: Document variable substitution, formula evaluation, and model definition
- **Demonstrate features**: Show practical examples of parallel execution, caching, and remote execution
- **Reference common patterns**: Include ready-to-use examples for typical use cases

## Files Overview

### 1. `overview.md` - Framework Introduction
High-level overview of FZ including:
- What FZ is and when to use it
- The four core functions (fzi, fzc, fzo, fzr)
- Key concepts and typical workflows
- Common patterns for different scenarios

**Use when**: Getting started with FZ or explaining what it does

### 2. `syntax-guide.md` - Variable and Formula Syntax
Detailed syntax reference for:
- Variable substitution (`$var`, `${var}`, `${var~default}`)
- Formula evaluation (`@{expression}`)
- Context lines for Python and R
- Complete examples with different interpreters

**Use when**: Writing input templates or working with formulas

### 3. `core-functions.md` - API Reference
Comprehensive guide to the four main functions:
- `fzi()` - Parse input variables
- `fzc()` - Compile input files
- `fzo()` - Read output files
- `fzr()` - Run parametric calculations
- Function signatures, parameters, and return values
- Examples for each function

**Use when**: Using FZ API functions in Python code

### 4. `model-definition.md` - Model Configuration
Complete model definition guide covering:
- Model structure and all fields
- Input parsing configuration
- Output extraction commands
- Model aliases and organization
- Examples for different simulation types

**Use when**: Creating or modifying FZ models

### 5. `calculators.md` - Execution Backends
Guide to all calculator types:
- `sh://` - Local shell execution
- `ssh://` - Remote SSH execution
- `cache://` - Cached result reuse
- Calculator aliases and configuration
- Parallel execution and fallback chains

**Use when**: Configuring how calculations are executed

### 6. `formulas-and-interpreters.md` - Formula Evaluation
In-depth coverage of formula evaluation:
- Python interpreter (default)
- R interpreter for statistical computing
- Context lines and function definitions
- Complete examples with both interpreters
- Best practices for formula writing

**Use when**: Using formulas in input templates

### 7. `parallel-and-caching.md` - Performance Features
Guide to parallel execution and caching:
- Parallel execution strategies
- Load balancing and worker optimization
- Caching strategies for different scenarios
- Retry mechanisms
- Interrupt handling and resume
- Performance optimization tips

**Use when**: Optimizing performance or resuming interrupted runs

### 8. `quick-examples.md` - Common Patterns
Ready-to-use examples for:
- Quick start examples
- Common patterns by use case (sweeps, grids, sensitivity, Monte Carlo, etc.)
- CLI examples
- Troubleshooting examples
- Integration with pandas, matplotlib, Jupyter

**Use when**: Looking for example code for specific use cases

## How to Use This Documentation

### For LLM Integration

These files can be used as context for LLMs in several ways:

1. **Complete context**: Include all files for comprehensive understanding
2. **Selective context**: Include only relevant files based on the task
3. **Reference lookup**: Search for specific topics or examples

### Recommended Context by Task

| Task | Recommended Files |
|------|------------------|
| Getting started | overview.md, quick-examples.md |
| Writing input templates | syntax-guide.md, formulas-and-interpreters.md |
| Using FZ API | core-functions.md, quick-examples.md |
| Configuring models | model-definition.md, syntax-guide.md |
| Setting up execution | calculators.md, parallel-and-caching.md |
| Performance tuning | parallel-and-caching.md, calculators.md |
| Troubleshooting | quick-examples.md (troubleshooting section) |

### Example Usage in LLM Prompts

**Example 1: Basic parametric study**
```
Context: Read overview.md and quick-examples.md
Task: Help me create a simple parametric study that varies temperature from 0 to 100°C
```

**Example 2: Complex formulas**
```
Context: Read syntax-guide.md and formulas-and-interpreters.md
Task: I need to convert units and calculate derived parameters in my input file
```

**Example 3: Performance optimization**
```
Context: Read parallel-and-caching.md and calculators.md
Task: How do I speed up my parametric study with 1000 cases?
```

## File Organization

```
context/
├── README.md                           # This file
├── INDEX.md                            # Table of contents with sections
├── overview.md                         # High-level framework introduction
├── syntax-guide.md                     # Variable and formula syntax
├── core-functions.md                   # API reference (fzi, fzc, fzo, fzr)
├── model-definition.md                 # Model configuration guide
├── calculators.md                      # Calculator types and configuration
├── formulas-and-interpreters.md        # Formula evaluation (Python/R)
├── parallel-and-caching.md            # Parallel execution and caching
└── quick-examples.md                   # Common patterns and examples
```

## Updating This Documentation

When FZ features change or new patterns emerge, update the relevant files:

1. **New features**: Add to appropriate file(s) with examples
2. **Syntax changes**: Update syntax-guide.md and affected files
3. **New patterns**: Add to quick-examples.md
4. **API changes**: Update core-functions.md

Keep examples:
- **Concise**: Focus on the essential pattern
- **Complete**: Include all necessary imports and setup
- **Tested**: Verify examples work with current FZ version
- **Commented**: Add explanations where helpful

## Contributing

To improve this documentation:

1. Identify gaps or unclear explanations
2. Add practical examples from real usage
3. Include common mistakes and how to avoid them
4. Keep language clear and examples self-contained
5. Update INDEX.md if adding new major sections

## Version

These context files are for **FZ version 0.9.0+**

Last updated: 2025-01-XX
