"""Tests for the MCP server policy layer (fz/mcp_server.py)."""
import inspect

import pytest

from fz import core, mcp_server
from fz.mcp_server import FzTools, McpSecurityError

MODEL = {"varprefix": "$", "delim": "()", "output": {"out": "cat out.txt"}}


@pytest.fixture
def tools(tmp_path):
    return FzTools(root=str(tmp_path), trusted=True)


def test_trusted_env_default(tmp_path, monkeypatch):
    monkeypatch.delenv("FZ_MCP_TRUSTED", raising=False)
    assert FzTools(root=str(tmp_path)).trusted is True
    monkeypatch.setenv("FZ_MCP_TRUSTED", "0")
    assert FzTools(root=str(tmp_path)).trusted is False


def test_untrusted_mode_does_not_require_core_trusted_param(tmp_path):
    """Untrusted mode restricts inputs to installed aliases at the MCP layer;
    it must not depend on (or fail without) an fz core 'trusted' parameter,
    which fz does not have and will not add (see README.md -> Threat Model)."""
    assert "trusted" not in inspect.signature(core.fzr).parameters
    FzTools(root=str(tmp_path), trusted=False)  # must not raise


@pytest.fixture
def untrusted(tmp_path):
    return FzTools(root=str(tmp_path), trusted=False)


def test_untrusted_rejects_inline_model(untrusted):
    with pytest.raises(McpSecurityError, match="alias"):
        untrusted.fzi("in.txt", MODEL)


@pytest.mark.parametrize("calc", ["sh://rm -rf x", "ssh://h/cmd", {"uri": "sh://x"}, ["local", "sh://x"]])
def test_untrusted_rejects_calculator_uris(untrusted, calc):
    with pytest.raises(McpSecurityError, match="calculators"):
        untrusted._calculators(calc)


def test_untrusted_accepts_alias_calculators(untrusted):
    assert untrusted._calculators(["local", "cluster"]) == ["local", "cluster"]


@pytest.mark.parametrize("bad", ["../etc/passwd", "/etc/passwd", "sub/../../x"])
def test_paths_confined_to_root(tools, bad):
    with pytest.raises(McpSecurityError, match="outside"):
        tools._path(bad)
    with pytest.raises(McpSecurityError, match="outside"):
        tools._glob_path(bad)


def test_glob_path_allows_patterns_inside_root(tools, tmp_path):
    assert tools._glob_path("results/*") == str(tmp_path / "results" / "*")


def test_fzi_fzc_roundtrip(tools, tmp_path):
    (tmp_path / "in.txt").write_text("x = $(a)\n")
    assert "a" in tools.fzi("in.txt", MODEL)
    out = tools.fzc("in.txt", {"a": 3}, MODEL, "compiled")
    assert out["output_dir"] == str(tmp_path / "compiled")
    assert "x = 3" in next((tmp_path / "compiled").rglob("in.txt")).read_text()


def test_fzr_returns_json_safe(tools, tmp_path):
    import json

    (tmp_path / "in.txt").write_text("$(a)\n")
    model = dict(MODEL, output={"out": "cat in.txt"})
    res = tools.fzr("in.txt", {"a": [1, 2]}, model, "sh://cat in.txt > out.txt", "res")
    json.dumps(res)
    assert len(res["a"]) == 2


def test_server_registers_five_tools(tmp_path):
    pytest.importorskip("mcp")
    import asyncio

    server = mcp_server.build_server(FzTools(root=str(tmp_path), trusted=True))
    names = {t.name for t in asyncio.run(server.list_tools())}
    assert names == {"fzi", "fzc", "fzr", "fzo", "fzl"}


def test_tool_annotations_present(tmp_path):
    """fzc/fzr are destructive+open-world; fzi/fzo/fzl are read-only (P0-7)."""
    pytest.importorskip("mcp")
    import asyncio

    server = mcp_server.build_server(FzTools(root=str(tmp_path), trusted=True))
    tools_by_name = {t.name: t for t in asyncio.run(server.list_tools())}

    for name in ("fzc", "fzr"):
        ann = tools_by_name[name].annotations
        assert ann is not None
        assert ann.destructive_hint is True
        assert ann.open_world_hint is True

    for name in ("fzi", "fzo", "fzl"):
        ann = tools_by_name[name].annotations
        assert ann is not None
        assert ann.read_only_hint is True


def test_resolve_transport_defaults_to_stdio(monkeypatch):
    monkeypatch.delenv("FZ_MCP_TRANSPORT", raising=False)
    assert mcp_server._resolve_transport() == "stdio"


def test_resolve_transport_refuses_network_without_opt_in(monkeypatch):
    monkeypatch.setenv("FZ_MCP_TRANSPORT", "sse")
    monkeypatch.delenv("FZ_MCP_ALLOW_NETWORK_TRANSPORT", raising=False)
    with pytest.raises(SystemExit, match="FZ_MCP_ALLOW_NETWORK_TRANSPORT"):
        mcp_server._resolve_transport()


def test_resolve_transport_allows_network_with_opt_in(monkeypatch, capsys):
    monkeypatch.setenv("FZ_MCP_TRANSPORT", "streamable-http")
    monkeypatch.setenv("FZ_MCP_ALLOW_NETWORK_TRANSPORT", "1")
    assert mcp_server._resolve_transport() == "streamable-http"
    assert "WARNING" in capsys.readouterr().err


def test_resolve_transport_rejects_unknown_value(monkeypatch):
    monkeypatch.setenv("FZ_MCP_TRANSPORT", "carrier-pigeon")
    with pytest.raises(SystemExit, match="unknown FZ_MCP_TRANSPORT"):
        mcp_server._resolve_transport()
