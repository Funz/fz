"""Tests for the MCP server policy layer (fz/mcp_server.py)."""
import pytest

from fz import mcp_server
from fz.mcp_server import FzTools, McpSecurityError

MODEL = {"varprefix": "$", "delim": "()", "output": {"out": "cat out.txt"}}


@pytest.fixture
def tools(tmp_path):
    return FzTools(root=str(tmp_path), trusted=True)


def test_untrusted_fails_closed_without_core_support(tmp_path, monkeypatch):
    monkeypatch.setattr(mcp_server, "_core_supports_trusted", lambda: False)
    with pytest.raises(McpSecurityError, match="FZ_MCP_TRUSTED"):
        FzTools(root=str(tmp_path), trusted=False)


def test_untrusted_env_default(tmp_path, monkeypatch):
    monkeypatch.delenv("FZ_MCP_TRUSTED", raising=False)
    monkeypatch.setattr(mcp_server, "_core_supports_trusted", lambda: True)
    assert FzTools(root=str(tmp_path)).trusted is False
    monkeypatch.setenv("FZ_MCP_TRUSTED", "1")
    assert FzTools(root=str(tmp_path)).trusted is True


@pytest.fixture
def untrusted(tmp_path, monkeypatch):
    monkeypatch.setattr(mcp_server, "_core_supports_trusted", lambda: True)
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


def test_untrusted_passes_trusted_false(untrusted):
    assert untrusted._kw() == {"trusted": False}


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
