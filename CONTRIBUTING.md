# Contributing to FZ

Thank you for your interest in contributing to FZ! This document provides guidelines and instructions for contributing.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Making Changes](#making-changes)
- [Testing](#testing)
- [Code Style](#code-style)
- [Pull Request Process](#pull-request-process)
- [Reporting Bugs](#reporting-bugs)
- [Feature Requests](#feature-requests)

## Code of Conduct

By participating in this project, you agree to maintain a respectful and inclusive environment for all contributors.

## Getting Started

1. Fork the repository on GitHub
2. Clone your fork locally:
   ```bash
   git clone https://github.com/YOUR_USERNAME/fz.git
   cd fz
   ```
3. Add the upstream repository:
   ```bash
   git remote add upstream https://github.com/Funz/fz.git
   ```

## Development Setup

### Prerequisites

- Python 3.9 or higher
- Git
- `bc` command (for running tests on Linux/macOS)

### Install Development Dependencies

```bash
# Create a virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install fz in editable mode with development dependencies
pip install -e ".[dev]"
pip install pandas  # Optional but recommended

# Install system dependencies (Linux/macOS)
# Ubuntu/Debian:
sudo apt-get install bc

# macOS:
brew install bc
```

### Verify Installation

```bash
# Run tests to ensure everything is working
pytest tests/ -v

# Check that fz is importable
python -c "import fz; print(f'FZ version: {fz.__version__}')"
```

## Making Changes

### Branching Strategy

- `main` - Stable releases
- `develop` - Development branch (if used)
- `feature/your-feature-name` - Feature branches
- `fix/your-fix-name` - Bug fix branches

### Creating a Feature Branch

```bash
# Update your local main branch
git checkout main
git pull upstream main

# Create a feature branch
git checkout -b feature/your-feature-name
```

### Making Commits

- Write clear, concise commit messages
- Use present tense ("Add feature" not "Added feature")
- Reference issue numbers when applicable

```bash
git add .
git commit -m "Add support for XYZ calculator

- Implement XYZ protocol
- Add tests for XYZ
- Update documentation

Fixes #123"
```

## Testing

### Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_parallel.py -v

# Run with coverage
pytest tests/ --cov=fz --cov-report=html --cov-report=term

# Run tests matching a pattern
pytest tests/ -k "parallel" -v
```

### Writing Tests

All new features should include tests. Place tests in the `tests/` directory.

Example test structure:

```python
import fz
import tempfile
from pathlib import Path

def test_your_feature():
    """Test description"""
    # Arrange
    with tempfile.TemporaryDirectory() as tmpdir:
        input_file = Path(tmpdir) / "input.txt"
        input_file.write_text("Parameter: $param\n")

        model = {
            "varprefix": "$",
            "output": {"result": "cat output.txt"}
        }

        # Act
        results = fz.fzr(
            str(input_file),
            {"param": [1, 2, 3]},
            model,
            calculators="sh://bash script.sh",
            resultsdir=str(Path(tmpdir) / "results")
        )

        # Assert
        assert len(results) == 3
        assert all(results['status'] == 'done')
```

### Test Requirements

- All tests must pass on Linux, macOS, and Windows
- Tests should be isolated and not depend on external resources
- Use temporary directories for file operations
- Clean up resources after tests

## Code Style

### Python Style Guide

We follow PEP 8 with some modifications:

- Maximum line length: 127 characters
- Use descriptive variable names
- Add docstrings to all public functions and classes

### Formatting

```bash
# Format code with black (optional)
black fz/ tests/

# Check code style with flake8
flake8 fz/ --max-line-length=127
```

### Docstring Format

Use Google-style docstrings:

```python
def example_function(param1: str, param2: int) -> Dict[str, Any]:
    """
    Brief description of function.

    Longer description if needed, explaining the purpose,
    behavior, and any important details.

    Args:
        param1: Description of param1
        param2: Description of param2

    Returns:
        Description of return value

    Raises:
        ValueError: When param2 is negative

    Example:
        >>> result = example_function("test", 42)
        >>> print(result)
        {'key': 'value'}
    """
    # Implementation
    pass
```

## Pull Request Process

### Before Submitting

1. **Update your branch** with the latest upstream changes:
   ```bash
   git fetch upstream
   git rebase upstream/main
   ```

2. **Run all tests**:
   ```bash
   pytest tests/ -v
   ```

3. **Check code style**:
   ```bash
   flake8 fz/ --max-line-length=127
   ```

4. **Update documentation** if needed:
   - Update README.md for new features
   - Add docstrings to new functions
   - Update CHANGELOG.md (if exists)

### Submitting a Pull Request

1. Push your branch to your fork:
   ```bash
   git push origin feature/your-feature-name
   ```

2. Go to the [FZ repository](https://github.com/Funz/fz) on GitHub

3. Click "New Pull Request"

4. Select your branch and provide:
   - **Title**: Clear, concise description
   - **Description**:
     - What changes were made
     - Why the changes were made
     - Any related issues
     - Testing performed
     - Screenshots (if applicable)

5. Request review from maintainers

### Pull Request Template

```markdown
## Description
Brief description of changes

## Related Issues
Fixes #123

## Changes Made
- Change 1
- Change 2
- Change 3

## Testing Performed
- [ ] All existing tests pass
- [ ] Added tests for new functionality
- [ ] Tested on Linux
- [ ] Tested on macOS
- [ ] Tested on Windows

## Documentation
- [ ] Updated README.md
- [ ] Added/updated docstrings
- [ ] Updated examples

## Checklist
- [ ] Code follows project style guidelines
- [ ] Self-review completed
- [ ] Comments added for complex code
- [ ] No new warnings generated
```

### Review Process

- Maintainers will review your PR within a few days
- Address any feedback or requested changes
- Once approved, maintainers will merge your PR

## Reporting Bugs

### Before Reporting

1. Check [existing issues](https://github.com/Funz/fz/issues)
2. Verify the bug exists in the latest version
3. Collect relevant information

### Bug Report Template

```markdown
**Description**
Clear description of the bug

**To Reproduce**
Steps to reproduce:
1. Step 1
2. Step 2
3. See error

**Expected Behavior**
What you expected to happen

**Actual Behavior**
What actually happened

**Environment**
- OS: [e.g., Ubuntu 22.04, Windows 11, macOS 13]
- Python version: [e.g., 3.11.5]
- FZ version: [e.g., 0.8.0]
- Installation method: [pip, source]

**Code Sample**
```python
# Minimal code to reproduce
import fz
# ...
```

**Error Output**
```
Full error traceback
```

**Additional Context**
Any other relevant information
```

## Feature Requests

We welcome feature requests! Please:

1. Check if the feature already exists or is planned
2. Clearly describe the feature and its use case
3. Explain why it would be useful to other users
4. Provide examples if possible

### Feature Request Template

```markdown
**Feature Description**
Clear description of the feature

**Use Case**
Why this feature would be useful

**Proposed Solution**
How you envision this working

**Alternatives Considered**
Other approaches you've thought about

**Additional Context**
Examples, mockups, references, etc.
```

## Development Guidelines

### Architecture Overview

```
fz/
├── core.py       # Main API functions (fzi, fzc, fzo, fzr)
├── interpreter.py     # Variable parsing and formula evaluation
├── runners.py    # Calculation execution (local, SSH)
├── helpers.py    # Parallel execution and retry logic
├── io.py         # File I/O, caching, hashing
├── logging.py    # Logging configuration
└── config.py     # Configuration management
```

### Adding New Features

1. **Core functions** (`fzi`, `fzc`, `fzo`, `fzr`) should remain stable
2. **New calculator types**: Add to `runners.py`
3. **New interpreters**: Add to `interpreter.py`
4. **New features**: Consider backward compatibility

### Performance Considerations

- Use generators for large datasets
- Avoid loading entire files into memory
- Profile code for performance bottlenecks
- Optimize hot paths

### Security Considerations

- Validate all user inputs
- Sanitize shell commands
- Warn about insecure operations (e.g., SSH passwords)
- Never commit credentials or sensitive data

## Questions?

If you have questions, feel free to:
- Open an issue with the "question" label
- Contact maintainers at yann.richet@asnr.fr

## License

By contributing, you agree that your contributions will be licensed under the BSD 3-Clause License.

---

Thank you for contributing to FZ! 🚀
