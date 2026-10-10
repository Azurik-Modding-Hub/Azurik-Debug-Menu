"""CLI tests never open the native GUI or write any actual game files."""
import json
from pathlib import Path
import sys

import pytest

import patcher


def invoke(monkeypatch, args):
    monkeypatch.setattr(sys, "argv", ["patcher.py", *args])
    return patcher.main()


def test_cli_version_does_not_open_gui_or_write_files(monkeypatch, capsys):
    monkeypatch.setattr(patcher, "gui", lambda: pytest.fail("Version must not open GUI"))
    with pytest.raises(SystemExit) as result:
        invoke(monkeypatch, ["--version"])
    assert result.value.code == 0
    assert capsys.readouterr().out.strip() == patcher.VERSION


@pytest.mark.parametrize("option", ["--input", "--output"])
def test_cli_requires_both_paths_before_patching(monkeypatch, capsys, option):
    monkeypatch.setattr(patcher, "gui", lambda: pytest.fail("Invalid CLI must not open GUI"))
    monkeypatch.setattr(patcher, "build_iso", lambda *_: pytest.fail("No output without both paths"))
    monkeypatch.setattr(patcher, "build_xbe", lambda *_: pytest.fail("No output without both paths"))
    with pytest.raises(SystemExit) as result:
        invoke(monkeypatch, [option, "synthetic.iso"])
    assert result.value.code == 2
    assert "required together" in capsys.readouterr().err


@pytest.mark.parametrize("suffix", [".iso", ".xiso", ".XBE"])
def test_cli_dispatches_to_correct_builder_and_prints_json(monkeypatch, capsys, suffix):
    calls = []

    def build(source, destination):
        calls.append((source, destination))
        return {"synthetic": True}

    expected = "build_xbe" if suffix.lower() == ".xbe" else "build_iso"
    unexpected = "build_iso" if expected == "build_xbe" else "build_xbe"
    monkeypatch.setattr(patcher, expected, build)
    monkeypatch.setattr(patcher, unexpected, lambda *_: pytest.fail("Wrong builder"))
    invoke(monkeypatch, ["--input", "synthetic" + suffix, "--output", "new" + suffix])
    assert calls == [(Path("synthetic" + suffix), Path("new" + suffix))]
    assert json.loads(capsys.readouterr().out) == {"output": "new" + suffix, "report": {"synthetic": True}}


@pytest.mark.parametrize("error", [ValueError("invalid image"), OSError("output denied")])
def test_cli_reports_safe_errors_without_traceback(monkeypatch, capsys, error):
    def fail(*_):
        raise error
    monkeypatch.setattr(patcher, "build_iso", fail)
    with pytest.raises(SystemExit) as result:
        invoke(monkeypatch, ["--input", "synthetic.iso", "--output", "new.iso"])
    assert result.value.code == 1
    captured = capsys.readouterr()
    assert str(error) in captured.err and "Traceback" not in captured.err and not captured.out


def test_no_cli_arguments_dispatches_gui_only(monkeypatch):
    calls = []
    monkeypatch.setattr(patcher, "gui", lambda: calls.append("gui"))
    monkeypatch.setattr(patcher, "build_iso", lambda *_: pytest.fail("No automatic game modifications"))
    invoke(monkeypatch, [])
    assert calls == ["gui"]


def test_cli_rejects_foreign_xbe_without_changing_input_or_creating_output(tmp_path, monkeypatch, capsys):
    source, destination = tmp_path / "foreign.xbe", tmp_path / "new.xbe"
    original = b"XBEH" + b"synthetic unsupported executable" * 80
    source.write_bytes(original)
    with pytest.raises(SystemExit) as result:
        invoke(monkeypatch, ["--input", str(source), "--output", str(destination)])
    assert result.value.code == 1
    assert source.read_bytes() == original
    assert not destination.exists() and not destination.with_suffix(".xbe.report.json").exists()
    captured = capsys.readouterr()
    assert "Unsupported executable" in captured.err and not captured.out
