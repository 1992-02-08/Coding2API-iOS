"""Reject host/simulator linkage and generate explicit framework directives."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

spec = importlib.util.spec_from_file_location(
    "configure_pyo3", Path(__file__).parents[1] / "configure_pyo3.py")
config = importlib.util.module_from_spec(spec)
spec.loader.exec_module(config)


def target(monkeypatch):
    monkeypatch.setattr(config, "sys", SimpleNamespace(
        platform="ios", version_info=(3, 13),
        implementation=SimpleNamespace(_multiarch="arm64-iphoneos")))


def test_framework_config_uses_target_slice(tmp_path, monkeypatch):
    target(monkeypatch)
    framework = tmp_path / "Python.xcframework/ios-arm64/Python.framework"
    framework.mkdir(parents=True)
    (framework / "Python").touch()
    monkeypatch.setattr(config.sysconfig, "get_config_var", lambda key: (
        ".cpython-313-arm64-iphoneos.so" if key == "EXT_SUFFIX" else str(framework.parent)))
    monkeypatch.setattr(config.sysconfig, "get_path", lambda key: str(framework / "Headers"))
    calls = []

    def run(args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(stdout="    platform IOS\n")

    monkeypatch.setattr(config.subprocess, "run", run)
    output = tmp_path / "pyo3.txt"
    config.write_config(output)
    text = output.read_text()
    assert "suppress_build_script_link_lines=true\n" in text
    assert f"cargo:rustc-link-search=framework={framework.parent}\n" in text
    assert "cargo:rustc-link-lib=framework=Python\n" in text
    assert "ext_suffix=.cpython-313-arm64-iphoneos.so\n" in text
    assert "python3.13" not in text
    assert all(kwargs["check"] for _, kwargs in calls)
    assert calls[0][0][-2:] == ["-verify_arch", "arm64"]
    assert calls[1][0][1:3] == ["vtool", "-show-build"]

    monkeypatch.setattr(config.subprocess, "run", lambda *a, **k: SimpleNamespace(
        stdout="    platform IOSSIMULATOR\n"))
    output.unlink()
    with pytest.raises(ValueError, match="not an iPhoneOS binary"):
        config.write_config(output)
    assert not output.exists()


def test_reject_missing_framework(tmp_path, monkeypatch):
    target(monkeypatch)
    monkeypatch.setattr(config.sysconfig, "get_config_var", lambda key: (
        ".cpython-313-arm64-iphoneos.so" if key == "EXT_SUFFIX" else None))
    monkeypatch.setattr(config.sysconfig, "get_path", lambda key: str(tmp_path))
    with pytest.raises(ValueError, match="exactly one"):
        config.write_config(tmp_path / "pyo3.txt")


@pytest.mark.parametrize("suffix", [None, "", ".cpython-313-darwin.so",
                                         ".cpython-313-arm64-iphonesimulator.so"])
def test_reject_wrong_extension_suffix(tmp_path, monkeypatch, suffix):
    target(monkeypatch)
    monkeypatch.setattr(config.sysconfig, "get_config_var", lambda key: suffix)
    output = tmp_path / "pyo3.txt"
    with pytest.raises(ValueError, match="extension suffix"):
        config.write_config(output)
    assert not output.exists()


@pytest.mark.parametrize("platform,multiarch,version", [
    ("darwin", "arm64-iphoneos", (3, 13)),
    ("ios", "arm64-iphonesimulator", (3, 13)),
    ("ios", "arm64-iphoneos", (3, 14)),
])
def test_reject_wrong_interpreter(tmp_path, monkeypatch, platform, multiarch, version):
    monkeypatch.setattr(config, "sys", SimpleNamespace(
        platform=platform, version_info=version,
        implementation=SimpleNamespace(_multiarch=multiarch)))
    with pytest.raises(ValueError):
        config.write_config(tmp_path / "pyo3.txt")
