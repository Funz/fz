"""P0-3 gap: the interrupt-time remote kill command must not interpolate
URI/command text as shell syntax (pgrep pattern is a single literal argument)."""
import shlex

import pytest

from fz.runners.ssh import build_kill_cmd

PAYLOADS = ["gpu", "x';touch PWNED;'", "a b", "$(touch PWNED)", "`touch PWNED`", "srun.*p;rm -rf ~"]


@pytest.mark.parametrize("pattern", PAYLOADS)
def test_pattern_is_one_literal_pgrep_argument(pattern):
    cmd = build_kill_cmd(pattern)
    assert cmd.startswith("pkill -P $(pgrep -f ")
    inner = cmd[len("pkill -P $(pgrep -f "):-1]   # text between "pgrep -f " and ")"
    assert shlex.split(inner) == [pattern]
    assert cmd.endswith(")")


def test_slurm_and_ssh_use_the_helper():
    import inspect
    from fz.runners import ssh, slurm
    assert "build_kill_cmd(" in inspect.getsource(ssh)
    assert "build_kill_cmd(" in inspect.getsource(slurm)
    for mod in (ssh, slurm):
        assert "pgrep -f '" not in inspect.getsource(mod)
