#!/usr/bin/env python3
"""
Check the distributions built by `python -m build` (used by ci.yml and release.yml).

Usage:
    python scripts/check_dist.py [DIST_DIR] [--tag TAG]

- exactly one wheel, pure Python (py3-none-any): fz has no compiled code, so a
  platform-specific wheel means the packaging changed;
- exactly one sdist;
- `twine check --strict` on both;
- with --tag (release tag, a leading "v" is allowed), the tag must equal the
  built version, i.e. fz.__version__ (fz/__init__.py).

Prints the built version on stdout; errors use the GitHub Actions ::error:: format.
"""
import argparse
import subprocess
import sys
from pathlib import Path


def fail(msg: str) -> int:
    print(f"::error::{msg}", file=sys.stderr)
    return 1


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("dist_dir", nargs="?", default="dist")
    parser.add_argument("--tag", default="", help="release tag to compare with the version")
    args = parser.parse_args(argv)

    dist = Path(args.dist_dir)
    wheels = sorted(dist.glob("*.whl"))
    sdists = sorted(dist.glob("*.tar.gz"))
    if len(wheels) != 1:
        return fail(f"expected exactly one wheel in {dist}, found {len(wheels)}")
    if len(sdists) != 1:
        return fail(f"expected exactly one sdist in {dist}, found {len(sdists)}")
    wheel = wheels[0]
    if not wheel.name.endswith("-py3-none-any.whl"):
        return fail(f"wheel is not pure Python (py3-none-any): {wheel.name}")

    check = subprocess.run(
        [sys.executable, "-m", "twine", "check", "--strict", str(wheel), str(sdists[0])]
    )
    if check.returncode != 0:
        return fail("twine check failed")

    version = wheel.name.split("-")[1]
    tag = args.tag[1:] if args.tag.startswith("v") else args.tag
    if args.tag and tag != version:
        return fail(
            f"release tag '{args.tag}' does not match fz.__version__ '{version}' (fz/__init__.py)"
        )
    print(version)
    return 0


if __name__ == "__main__":
    sys.exit(main())
