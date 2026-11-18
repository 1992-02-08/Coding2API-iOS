"""Validate application identifiers before staging any files."""
import importlib.util
from pathlib import Path

import pytest


spec = importlib.util.spec_from_file_location(
    "prepare_ios", Path(__file__).parents[1] / "prepare.py")
prepare_ios = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prepare_ios)


@pytest.mark.parametrize("bundle", ["com.github.1992-02-08", "org.example"])
def test_valid_bundle_reaches_wheel_validation(bundle, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(prepare_ios.sys, "version_info", (3, 13))
    monkeypatch.setattr(prepare_ios.sys, "argv", [
        "prepare.py", "--bundle", bundle, "--wheels", str(tmp_path / "missing")])
    with pytest.raises(SystemExit) as error:
        prepare_ios.prepare()
    assert error.value.code == 2
    assert "wheel directory does not exist" in capsys.readouterr().err


@pytest.mark.parametrize("bundle", ["com..app", "single", "com.bad_name", "com.应用", "com.-"])
def test_invalid_bundle_rejected(bundle, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(prepare_ios.sys, "version_info", (3, 13))
    monkeypatch.setattr(prepare_ios.sys, "argv", [
        "prepare.py", "--bundle", bundle, "--wheels", str(tmp_path)])
    with pytest.raises(SystemExit) as error:
        prepare_ios.prepare()
    assert error.value.code == 2
    assert "bundle must be a reverse DNS prefix" in capsys.readouterr().err
