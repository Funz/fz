"""
Shared URI helpers: credential redaction for calculator URIs.

Moved out of ``fz/manifest.py`` (P0-3) so every part of fz that might write a
calculator URI to disk or to a log (history.txt, info.txt, manifest.json, the
results DataFrame's ``calculator`` column, ...) can redact the password from
an ``ssh://user:pw@host`` (or ``slurm://user:pw@host``) URI without importing
the manifest module.
"""

import re
import threading

_PASSWORD_RE = re.compile(r"(://[^/:@\s]*:)[^@/\s]*@")


def redact_uri(uri) -> str:
    """Hide credentials in a calculator URI (``ssh://user:pw@host`` -> ``ssh://user:***@host``).

    Safe to call on values that are not URIs, or that carry no credentials:
    they are returned unchanged (coerced to ``str``).
    """
    return _PASSWORD_RE.sub(r"\1***@", str(uri))


_warned_hosts_lock = threading.Lock()
_warned_messages = set()


def warn_password_in_uri_once(host: str, warn_fn, message: str = "") -> None:
    """Call ``warn_fn()`` the first time a given *message* for *host* is seen.

    Connections are made once per case (i.e. many times per campaign for a
    parameter study); without this the "password provided in URI" warning
    would otherwise be repeated on every single connection attempt. Keyed on
    ``(host, message)`` rather than just ``host`` so distinct warnings for the
    same host (e.g. "password in URI" and "no username provided") each still
    get shown once, instead of the second one being silently dropped forever
    because the host was already marked as warned by the first.
    """
    key = (host, message)
    with _warned_hosts_lock:
        if key in _warned_messages:
            return
        _warned_messages.add(key)
    warn_fn()


def reset_password_warnings() -> None:
    """Clear the once-per-host warning dedup state (mainly for tests)."""
    with _warned_hosts_lock:
        _warned_messages.clear()
