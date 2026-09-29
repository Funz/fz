"""
P0-3 regression tests: case-name / remote-command injection and credential
leakage (security audit, 2026-09-27).

Covers:
  - Variable values used as "path" case names can no longer escape the
    results directory or inject shell metacharacters into on-disk names
    (fz.helpers._case_subdir_name / _get_result_directory / _get_case_directories).
  - The remote SSH log-writing heredoc can no longer be truncated by an
    "EOF" line in the calculation's own stdout (fz.runners.ssh).
  - A password embedded in an ssh:// calculator URI never reaches the
    results DataFrame, history.txt, info.txt, or the logs.
"""

import os
import getpass
import platform
import subprocess
import time
from pathlib import Path

import pytest

import fz
from fz.helpers import _case_subdir_name, _assert_dir_within
from fz.history import write_info_file
from fz.uri import redact_uri

try:
    import paramiko
    PARAMIKO_AVAILABLE = True
except ImportError:
    PARAMIKO_AVAILABLE = False

# conftest.SSH_AVAILABLE only checks that *some* SSH server answers on
# localhost:22 (it accepts a plain "auth failed" as "available" - see its
# docstring), not that our own generated/ssh-add-ed key can actually
# authenticate. On GitHub-hosted macOS/Windows runners a system SSH server
# does answer on port 22 (unlike the "Setup SSH server (Linux only)" step
# in ci.yml, which only provisions one on Linux) but our key-based auth
# fails there in practice (e.g. Windows OpenSSH Server ignores a plain
# admin user's ~/.ssh/authorized_keys entirely in favor of
# administrators_authorized_keys). The dedicated SSH test files
# (test_ssh_localhost.py etc.) are excluded from non-Linux CI jobs for the
# same reason; the two SSH-dependent tests below mirror that restriction.
IS_LINUX = platform.system() == "Linux"

from conftest import SSH_AVAILABLE


DANGEROUS_VALUES = ["../../evil", "a b", "a;touch PWNED", "$(touch PWNED)"]


def _is_within(child: Path, base: Path) -> bool:
    """Python 3.8-compatible equivalent of Path.is_relative_to (added in 3.9)."""
    try:
        child.relative_to(base)
        return True
    except ValueError:
        return False


def _find_pwned(root: Path):
    """Return any file named PWNED found anywhere under (and above) root."""
    hits = []
    # Look under the test's own tmp tree (root and a few parents, staying
    # inside the repo's tmp/ sandbox that conftest.py already isolates us to).
    for base in {root, root.parent, root.parent.parent}:
        if not base.exists():
            continue
        for p in base.rglob("PWNED"):
            hits.append(p)
    return hits


def _make_simple_model_files():
    with open("input.txt", "w") as f:
        f.write("x = ${x}\n")
    with open("calc.sh", "w", newline="\n") as f:
        f.write("#!/bin/bash\necho ok > output.txt\n")
    os.chmod("calc.sh", 0o755)
    return {
        "varprefix": "$",
        "delim": "{}",
        "output": {"result": "cat output.txt"},
    }


# ---------------------------------------------------------------------------
# a) Safe case names (sh://, no SSH required)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("dangerous", DANGEROUS_VALUES)
def test_case_name_no_escape_or_injection_local(dangerous, tmp_path):
    """A dangerous variable value must never create anything outside results/,
    and must never let a shell command run (no PWNED file anywhere)."""
    model = _make_simple_model_files()
    results_dir = Path("results").resolve()

    result = fz.fzr(
        "input.txt",
        {"x": [dangerous]},
        model,
        calculators="sh://bash calc.sh",
        results_dir="results",
    )

    # No file named PWNED was created anywhere reachable (command injection
    # would have created one for "a;touch PWNED" / "$(touch PWNED)").
    assert not _find_pwned(Path.cwd())

    # Every case directory fz actually created lives under results_dir.
    for p in results_dir.rglob("*"):
        assert _is_within(p.resolve(), results_dir), (
            f"{p} escaped the results directory for value {dangerous!r}"
        )

    # The parent of the temp working directory tree used for the case (.fz/tmp)
    # must not contain anything outside itself either.
    fz_tmp = Path(".fz/tmp").resolve()
    if fz_tmp.exists():
        for p in fz_tmp.rglob("*"):
            assert _is_within(p.resolve(), fz_tmp)

    assert result is not None


def test_case_subdir_name_encodes_unsafe_characters():
    """Unit test of the encoding itself (fz.helpers._case_subdir_name, 'path' scheme)."""
    # Path separators can no longer create extra path segments - the value
    # "../../evil" is still visible (harmless: it's part of one component,
    # not a real ".." path segment since there is no "/" left to split on).
    name = _case_subdir_name({"x": "../../evil"}, 0, 1, "path")
    assert "/" not in name and "\\" not in name

    # A value that is only "." or ".." must not collapse the encoded segment
    # to a bare "." or ".." (which would be a no-op / parent-dir reference).
    name_dot = _case_subdir_name({"x": ".."}, 0, 1, "path")
    assert name_dot not in (".", "..")

    # Space and a shell metacharacter survive but the directory name is still
    # a single, safe path component (no separators).
    name_meta = _case_subdir_name({"x": "a;touch PWNED"}, 0, 1, "path")
    assert "/" not in name_meta and "\\" not in name_meta

    # The original value is unambiguous key=value text - not required to be
    # reversible from the name itself (info.txt/cases.csv keep the original).
    assert name_meta.startswith("x=")


def test_case_subdir_name_stable_for_safe_values():
    """Values with no unsafe characters keep the pre-P0-3 human-readable name."""
    assert _case_subdir_name({"x": 1, "y": 2}, 0, 1, "path") == "x=1,y=2"


def test_fzo_reconstructs_original_value_from_encoded_case_name(tmp_path):
    """fzo()'s best-effort fallback parser (fz/core.py, reconstructing variable
    columns from a "path"-scheme case directory name) must percent-decode each
    component, or it returns the mangled on-disk form instead of the original
    value for anything _case_subdir_name had to encode."""
    model = _make_simple_model_files()

    result = fz.fzr(
        "input.txt",
        {"x": ["a/b"]},
        model,
        calculators="sh://bash calc.sh",
        results_dir="results",
    )

    values = list(result["x"])
    assert values == ["a/b"], (
        f"Expected the original value 'a/b' back from fzo(), got {values!r} "
        "(the percent-encoded on-disk directory name leaking through un-decoded "
        "would show up as 'a%2Fb')"
    )


def test_assert_dir_within_rejects_escape(tmp_path):
    base = tmp_path / "results"
    base.mkdir()
    inside = base / "case_0"
    outside = tmp_path / "elsewhere"

    _assert_dir_within(inside, base)  # no raise

    with pytest.raises(ValueError):
        _assert_dir_within(outside, base)


# ---------------------------------------------------------------------------
# e) Credential redaction (no SSH server required - the connection can fail)
# ---------------------------------------------------------------------------

def test_redact_uri_helper():
    assert redact_uri("ssh://bob:s3cr3t@host/cmd") == "ssh://bob:***@host/cmd"
    assert redact_uri("sh://bash -c 'echo hi'") == "sh://bash -c 'echo hi'"
    assert redact_uri("ssh://host/cmd") == "ssh://host/cmd"


def test_history_and_info_files_never_contain_password(tmp_path):
    directory = tmp_path
    write_info_file(
        directory,
        state="failed",
        calculator="ssh://bob:s3cr3t@host/cmd",
        error="connection refused",
    )
    content = (directory / "info.txt").read_text()
    assert "s3cr3t" not in content
    assert "***" in content

    from fz.history import CaseHistory
    h = CaseHistory("case")
    h.append("Trying calculator: ssh://bob:s3cr3t@host/cmd")
    h.write(directory)
    history_content = (directory / "history.txt").read_text()
    assert "s3cr3t" not in history_content


@pytest.mark.skipif(not PARAMIKO_AVAILABLE, reason="paramiko not installed")
def test_ssh_password_not_leaked_on_unreachable_host(capsys):
    """An unreachable ssh://user:secret@host must never leak the password
    into the results DataFrame, history.txt, info.txt, or the logs."""
    from fz.logging import set_log_level
    from fz import config as fz_config

    os.environ["FZ_MAX_RETRIES"] = "1"
    fz_config.reload_config()
    set_log_level("DEBUG")
    try:
        model = _make_simple_model_files()
        secret = "s3cr3tPASSWORD"
        # Port 1 on localhost: nothing listens there, connection is refused
        # immediately (no DNS/timeout delay), so the test stays fast.
        calc_uri = f"ssh://baduser:{secret}@127.0.0.1:1/bash calc.sh"

        result = fz.fzr(
            "input.txt",
            {"x": [1]},
            model,
            calculators=calc_uri,
            results_dir="results",
        )

        captured = capsys.readouterr()
        assert secret not in captured.err
        assert secret not in captured.out

        assert secret not in str(result)
        try:
            assert secret not in result.to_string()
        except AttributeError:
            pass

        results_dir = Path("results")
        for name in ("history.txt", "info.txt"):
            for p in results_dir.rglob(name):
                assert secret not in p.read_text()
    finally:
        os.environ.pop("FZ_MAX_RETRIES", None)
        fz_config.reload_config()
        set_log_level("ERROR")


# ---------------------------------------------------------------------------
# b/c/d) SSH-dependent tests: remote injection guards + heredoc-truncation fix
# ---------------------------------------------------------------------------

def _setup_ssh_key(test_dir: Path, marker: str):
    """Minimal key-based SSH-to-localhost setup, mirroring test_ssh_localhost.py."""
    ssh_dir = test_dir / ".ssh"
    ssh_dir.mkdir(mode=0o700, exist_ok=True)
    key_path = ssh_dir / "test_key"
    pub_key_path = ssh_dir / "test_key.pub"

    subprocess.run(
        ["ssh-keygen", "-t", "rsa", "-b", "2048", "-f", str(key_path), "-N", "", "-C", marker],
        capture_output=True, text=True, check=True,
    )
    key_path.chmod(0o600)
    pub_key_path.chmod(0o644)

    home_ssh_dir = Path.home() / ".ssh"
    home_ssh_dir.mkdir(mode=0o700, exist_ok=True)
    authorized_keys_path = home_ssh_dir / "authorized_keys"
    pub_key_content = pub_key_path.read_text().strip()
    key_marker = f"# FZ-P0-3-TEST-KEY-MARKER-{os.getpid()}"
    original = authorized_keys_path.read_text() if authorized_keys_path.exists() else None

    with open(authorized_keys_path, "a") as f:
        f.write(f"{key_marker}\n{pub_key_content}\n")
    authorized_keys_path.chmod(0o600)

    subprocess.run(["ssh-add", str(key_path)], capture_output=True, text=True)
    time.sleep(0.3)

    return key_path, authorized_keys_path, original, key_marker


def _cleanup_authorized_keys(authorized_keys_path, original, key_marker, key_path=None):
    # Remove the key from the agent too, not just authorized_keys: an agent
    # that keeps accumulating identities across every SSH test in a long CI
    # session (this file alone adds up to five) eventually offers more than
    # sshd's MaxAuthTries before the right one, breaking *later*,
    # unrelated SSH tests in the same job with "Too many authentication
    # failures" - not a failure of this test itself, so best-effort only.
    if key_path is not None:
        subprocess.run(["ssh-add", "-d", str(key_path)], capture_output=True, text=True)
    try:
        if authorized_keys_path.exists():
            lines = authorized_keys_path.read_text().splitlines()
            filtered = []
            skip_next = False
            for line in lines:
                if line.strip() == key_marker:
                    skip_next = True
                    continue
                if skip_next:
                    skip_next = False
                    continue
                filtered.append(line)
            authorized_keys_path.write_text("\n".join(filtered) + ("\n" if filtered else ""))
    except Exception:
        pass


@pytest.mark.requires_ssh
@pytest.mark.requires_paramiko
@pytest.mark.skipif(not IS_LINUX, reason="key-based localhost SSH auth is unreliable on non-Linux CI runners (see IS_LINUX comment above)")
@pytest.mark.skipif(not SSH_AVAILABLE, reason="SSH server not available on localhost")
@pytest.mark.skipif(not PARAMIKO_AVAILABLE, reason="paramiko library not installed")
@pytest.mark.parametrize("dangerous", DANGEROUS_VALUES)
def test_ssh_case_name_no_remote_injection(dangerous):
    test_dir = Path.cwd()
    key_path, authorized_keys_path, original, key_marker = _setup_ssh_key(
        test_dir, "fz-p0-3-injection-test"
    )
    try:
        model = _make_simple_model_files()
        user = getpass.getuser()
        calc_uri = f"ssh://{user}@localhost/bash {(test_dir / 'calc.sh').resolve()}"

        fz.fzr(
            "input.txt",
            {"x": [dangerous]},
            model,
            calculators=calc_uri,
            results_dir="results",
        )

        # No PWNED anywhere locally or in the remote user's home (same host).
        assert not _find_pwned(Path.cwd())
        assert not list(Path.home().glob("PWNED"))
        assert not list((Path.home() / ".fz" / "tmp").glob("**/PWNED")) if (Path.home() / ".fz" / "tmp").exists() else True

        results_dir = Path("results").resolve()
        for p in results_dir.rglob("*"):
            assert _is_within(p.resolve(), results_dir)
    finally:
        _cleanup_authorized_keys(authorized_keys_path, original, key_marker, key_path)


@pytest.mark.requires_ssh
@pytest.mark.requires_paramiko
@pytest.mark.skipif(not IS_LINUX, reason="key-based localhost SSH auth is unreliable on non-Linux CI runners (see IS_LINUX comment above)")
@pytest.mark.skipif(not SSH_AVAILABLE, reason="SSH server not available on localhost")
@pytest.mark.skipif(not PARAMIKO_AVAILABLE, reason="paramiko library not installed")
def test_ssh_output_with_eof_line_not_truncated():
    """A calculation whose stdout contains a line that is exactly 'EOF' must
    be captured in full - the old remote heredoc would truncate here and
    hand the remaining lines to the remote shell as commands."""
    test_dir = Path.cwd()
    key_path, authorized_keys_path, original, key_marker = _setup_ssh_key(
        test_dir, "fz-p0-3-eof-test"
    )
    try:
        with open("input.txt", "w") as f:
            f.write("x = ${x}\n")
        calc_script = test_dir / "calc_eof.sh"
        calc_script.write_text(
            "#!/bin/bash\n"
            "echo 'before'\n"
            "echo 'EOF'\n"
            "echo 'after; touch PWNED_AFTER_EOF'\n"
            "echo done > output.txt\n"
        )
        calc_script.chmod(0o755)

        model = {
            "varprefix": "$",
            "delim": "{}",
            "output": {"result": "cat output.txt"},
        }
        user = getpass.getuser()
        calc_uri = f"ssh://{user}@localhost/bash {calc_script.resolve()}"

        result = fz.fzr(
            "input.txt",
            {"x": [1]},
            model,
            calculators=calc_uri,
            results_dir="results",
        )

        out_files = list(Path("results").rglob("out.txt"))
        assert out_files, "out.txt was not written"
        out_content = out_files[0].read_text()
        assert "before" in out_content
        assert "EOF" in out_content
        assert "after; touch PWNED_AFTER_EOF" in out_content

        # The "after; touch PWNED_AFTER_EOF" line must have stayed *data*
        # (never executed as a remote command).
        assert not list(Path.home().glob("PWNED_AFTER_EOF"))
        assert not _find_pwned(Path.cwd())
    finally:
        _cleanup_authorized_keys(authorized_keys_path, original, key_marker, key_path)
