# GitHub Configuration

This directory contains GitHub-specific configuration files for the FZ project.

## Workflows

### CI Workflow (`workflows/ci.yml`)

**Triggers**: Push and PR to `main`/`develop` branches

**Jobs**:
- **Test**: Run tests on multiple platforms and Python versions
  - OS: Ubuntu, Windows, macOS
  - Python: 3.9, 3.10, 3.11, 3.12, 3.13, 3.14-dev (Ubuntu only)
  - Coverage reporting (Ubuntu + Python 3.11)

- **Build Wheels**: Build wheels for all platforms
  - Creates `.whl` files for distribution
  - Uploads artifacts (30-day retention)

- **Build Source**: Build source distribution (`.tar.gz`)
  - Creates sdist for PyPI
  - Uploads artifacts (30-day retention)

- **Lint**: Code quality checks
  - Black formatting check
  - Flake8 linting

### Release Workflow (`workflows/release.yml`)

**Triggers**: GitHub release published or manual dispatch

**Jobs**:
- **Build Wheels**: Build wheels for each Python version (3.9-3.14) and platform
  - Matrix build across all combinations
  - 90-day artifact retention

- **Build Source**: Build source distribution

- **Publish to PyPI**: Automatically publish to PyPI on releases
  - Uses trusted publishing (OIDC)
  - Requires PyPI project configuration

- **Publish to GitHub**: Attach distributions to GitHub release
  - All wheels and sdist
  - Automatic on release

### Documentation Workflow (`workflows/docs.yml`)

**Triggers**: Push/PR to `main` branch

**Jobs**:
- **Build Documentation**: Placeholder for Sphinx docs
- **Validate Examples**: Check README examples work

## Issue Templates

### Bug Report (`ISSUE_TEMPLATE/bug_report.md`)

Template for reporting bugs with sections for:
- Description
- Reproduction steps
- Expected vs actual behavior
- Environment details
- Code samples and error output

### Feature Request (`ISSUE_TEMPLATE/feature_request.md`)

Template for proposing new features with sections for:
- Feature description
- Problem/use case
- Proposed solution
- Benefits and alternatives
- Implementation notes

## Pull Request Template (`PULL_REQUEST_TEMPLATE.md`)

Comprehensive PR template with checklists for:
- Description and related issues
- Type of change
- Testing performed (automated and manual)
- Documentation updates
- Code quality checks
- Breaking changes

## Setting Up CI/CD

### Prerequisites

1. **GitHub Repository Settings**:
   - Enable GitHub Actions
   - Configure branch protection for `main`
   - Set up required status checks

2. **PyPI Publishing** (for releases):
   - Create PyPI project: https://pypi.org/project/fz/
   - Configure trusted publishing in PyPI settings:
     - Owner: `Funz`
     - Repository: `fz`
     - Workflow: `release.yml`
     - Environment: `pypi`
   - Add PyPI environment in GitHub repo settings

3. **Codecov** (optional, for coverage):
   - Sign up at https://codecov.io
   - Add repository
   - Get upload token (or use GitHub App)

### Manual Testing Before Push

```bash
# Test the package builds
python -m build

# Run tests locally
pytest tests/ -v

# Check code style
flake8 fz/ --max-line-length=127
```

### Creating a Release

1. Update version in:
   - `setup.py`
   - `fz/__init__.py`
   - `README.md` badge

2. Update `CHANGELOG.md` (if exists)

3. Commit changes:
   ```bash
   git add .
   git commit -m "Release v0.8.0"
   git push
   ```

4. Create GitHub release:
   ```bash
   # Using GitHub CLI
   gh release create v0.8.0 --title "v0.8.0" --notes "Release notes here"

   # Or via GitHub web interface:
   # - Go to Releases > Draft a new release
   # - Tag: v0.8.0
   # - Title: v0.8.0
   # - Description: Release notes
   # - Publish release
   ```

5. Workflows will automatically:
   - Build wheels for all platforms/versions
   - Publish to PyPI (if configured)
   - Attach distributions to GitHub release

## Badge Status

Add these badges to your README.md:

```markdown
[![CI](https://github.com/Funz/fz/workflows/CI/badge.svg)](https://github.com/Funz/fz/actions/workflows/ci.yml)
[![Python Version](https://img.shields.io/pypi/pyversions/fz.svg)](https://pypi.org/project/fz/)
[![License](https://img.shields.io/badge/License-BSD%203--Clause-blue.svg)](https://opensource.org/licenses/BSD-3-Clause)
[![Version](https://img.shields.io/badge/version-0.8.0-blue.svg)](https://github.com/Funz/fz/releases)
```

## Troubleshooting

### Tests Failing on Windows

- Ensure `bc` alternative is used or tests are skipped
- Check file path separators (use `Path` from `pathlib`)
- Verify line endings (CRLF vs LF)

### PyPI Publishing Fails

- Check trusted publishing is configured correctly
- Verify `GITHUB_TOKEN` permissions
- Ensure version number is incremented
- Check PyPI project name matches `setup.py`

### Codecov Upload Fails

- Add `CODECOV_TOKEN` to repository secrets
- Or enable Codecov GitHub App

### Build Artifacts Not Found

- Check artifact names match in upload/download steps
- Verify workflow permissions
- Check artifact retention period

## Contact

For questions about CI/CD setup, contact the maintainers or open an issue.
