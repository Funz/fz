"""
Campaign traceability for fz: a ``manifest.json`` written in each results
directory by ``fzr()`` (versions, model, calculators, hosts, dates, per-case
hashes), and an optional RO-Crate (``ro-crate-metadata.json``) built from it.
"""

import hashlib
import json
import platform
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlsplit

MANIFEST_NAME = "manifest.json"
RO_CRATE_NAME = "ro-crate-metadata.json"
MANIFEST_SCHEMA = "fz-manifest/1"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def redact_uri(uri: str) -> str:
    """Hide credentials in a calculator URI (``ssh://user:pw@host`` -> ``ssh://user:***@host``)."""
    return re.sub(r"(://[^/:@\s]*:)[^@/\s]*@", r"\1***@", str(uri))


def uri_host(uri: str) -> Optional[str]:
    """Host of an ``ssh://``/``slurm://``/``funz://`` calculator URI, else None."""
    parts = urlsplit(str(uri))
    if parts.scheme in ("ssh", "slurm", "funz"):
        return parts.hostname or "localhost"
    return None


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _package_version(name: str) -> Optional[str]:
    try:
        from importlib import metadata
        return metadata.version(name)
    except Exception:
        return None


def build_manifest(
    results_dir: Path,
    *,
    model: Any,
    calculators: List[str],
    input_path: Path,
    input_variables: Any,
    results: Any,
    start_time: str,
    end_time: str,
    interrupted: bool = False,
) -> Dict[str, Any]:
    """Assemble the manifest dict of a finished ``fzr`` campaign."""
    from ._version import __version__ as fz_version

    results_dir = Path(results_dir)
    model_json = json.dumps(model, sort_keys=True, default=str)

    cases = []
    try:
        records = results.to_dict("records")
    except Exception:
        records = []
    for rec in records:
        rel = rec.get("path")
        case = {
            "path": rel,
            "status": rec.get("status"),
            "calculator": redact_uri(rec.get("calculator") or ""),
            "inputs": {k: v for k, v in rec.items()
                       if k in (getattr(input_variables, "columns", None)
                                or list(input_variables or {}))},
        }
        hash_file = results_dir / str(rel) / ".fz_hash" if rel else None
        if hash_file is not None and hash_file.is_file():
            case["fz_hash_sha256"] = _sha256(hash_file)
        cases.append(case)

    statuses = [c["status"] for c in cases]
    hosts = sorted({h for h in (uri_host(c) for c in calculators) if h})
    return {
        "schema": MANIFEST_SCHEMA,
        "fz_version": fz_version,
        "python_version": sys.version.split()[0],
        "platform": platform.platform(),
        "dependencies": {n: _package_version(n) for n in ("pandas", "numpy", "paramiko")},
        "start_time": start_time,
        "end_time": end_time,
        "interrupted": interrupted,
        "input_path": str(input_path),
        "model": model,
        "model_sha256": hashlib.sha256(model_json.encode()).hexdigest(),
        "calculators": [redact_uri(c) for c in calculators],
        "hosts": hosts,
        "n_cases": len(cases),
        "n_done": sum(1 for s in statuses if s == "done"),
        "cases": cases,
    }


def write_manifest(results_dir: Path, manifest: Dict[str, Any]) -> Path:
    path = Path(results_dir) / MANIFEST_NAME
    path.write_text(json.dumps(manifest, indent=2, default=str) + "\n", encoding="utf-8")
    return path


def write_ro_crate(results_dir: Path, manifest: Dict[str, Any]) -> Path:
    """Write a minimal RO-Crate 1.1 (``ro-crate-metadata.json``) describing the campaign."""
    results_dir = Path(results_dir)
    graph: List[Dict[str, Any]] = [
        {
            "@id": RO_CRATE_NAME,
            "@type": "CreativeWork",
            "conformsTo": {"@id": "https://w3id.org/ro/crate/1.1"},
            "about": {"@id": "./"},
        },
        {
            "@id": "./",
            "@type": "Dataset",
            "name": f"fz campaign {manifest['start_time']}",
            "datePublished": manifest["end_time"],
            "hasPart": [{"@id": MANIFEST_NAME}],
            "mentions": [{"@id": "#run"}],
        },
        {
            "@id": MANIFEST_NAME,
            "@type": "File",
            "name": "fz campaign manifest",
            "encodingFormat": "application/json",
            "sha256": _sha256(results_dir / MANIFEST_NAME),
        },
        {
            "@id": "#fz",
            "@type": "SoftwareApplication",
            "name": "fz",
            "version": manifest["fz_version"],
            "url": "https://github.com/Funz/fz",
        },
        {
            "@id": "#run",
            "@type": "CreateAction",
            "name": "fzr parametric run",
            "startTime": manifest["start_time"],
            "endTime": manifest["end_time"],
            "instrument": {"@id": "#fz"},
            "result": {"@id": "./"},
            "description": "Calculators: " + ", ".join(manifest["calculators"]),
        },
    ]
    path = results_dir / RO_CRATE_NAME
    path.write_text(
        json.dumps({"@context": "https://w3id.org/ro/crate/1.1/context", "@graph": graph}, indent=2) + "\n",
        encoding="utf-8",
    )
    return path
