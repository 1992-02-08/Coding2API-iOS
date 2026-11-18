"""Checks for the cloud-only OpenSSL build without requiring Xcode locally."""
import hashlib
import importlib.util
import io
import tarfile
from pathlib import Path

import pytest


spec = importlib.util.spec_from_file_location(
    "build_native", Path(__file__).parents[1] / "build_native.py")
native = importlib.util.module_from_spec(spec)
spec.loader.exec_module(native)


def test_openssl_rejects_corrupt_source(tmp_path, monkeypatch):
    def download(url, destination):
        Path(destination).write_bytes(b"corrupt source")

    monkeypatch.setattr(native.urllib.request, "urlretrieve", download)
    monkeypatch.setattr(native.subprocess, "run", lambda *a, **k: pytest.fail(
        "Unverified source must never run"))
    with pytest.raises(ValueError, match="OpenSSL source hash mismatch"):
        native.build_openssl(tmp_path)


def test_openssl_uses_device_target_and_static_libraries(tmp_path, monkeypatch):
    archive = io.BytesIO()
    with tarfile.open(fileobj=archive, mode="w:gz") as stream:
        entry = tarfile.TarInfo(f"openssl-{native.OPENSSL_VERSION}")
        entry.type = tarfile.DIRTYPE
        stream.addfile(entry)
    payload = archive.getvalue()

    def download(url, destination):
        assert f"openssl-{native.OPENSSL_VERSION}.tar.gz" in url
        Path(destination).write_bytes(payload)

    calls = []
    monkeypatch.setattr(native.urllib.request, "urlretrieve", download)
    monkeypatch.setattr(native, "OPENSSL_SHA256", hashlib.sha256(payload).hexdigest())
    monkeypatch.setenv("SDKROOT", "/wrong/desktop/sdk")
    monkeypatch.setattr(native.subprocess, "run", lambda args, **kw: calls.append((args, kw)))
    prefix = native.build_openssl(tmp_path)
    configure, options = calls[0]
    assert configure[:4] == ["perl", "Configure", "ios64-xcrun", "no-shared"]
    assert "-miphoneos-version-min=16.0" in configure
    assert "--libdir=lib" in configure
    assert options["env"]["IPHONEOS_DEPLOYMENT_TARGET"] == "16.0"
    assert "SDKROOT" not in options["env"]
    assert all(options["check"] for _, options in calls)
    assert [args for args, _ in calls[-2:]] == [
        ["xcrun", "lipo", str(prefix / "lib" / name), "-verify_arch", "arm64"]
        for name in ("libssl.a", "libcrypto.a")
    ]
