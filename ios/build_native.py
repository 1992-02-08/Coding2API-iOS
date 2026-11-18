"""Build locked Rust extensions on an Apple Silicon Mac with full Xcode.

This is an experimental recipe, not a claim that the upstream sources support iOS.
Cibuildwheel must provision CPython's iOS cross environment; no desktop wheel retagging.
"""
from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import tarfile
import tempfile
import tomllib
import urllib.request
from pathlib import Path


def main():
    if sys.platform != "darwin":
        raise SystemExit("Full macOS/Xcode required")
    root = Path(__file__).resolve().parents[1]
    packages = tomllib.loads((root / "uv.lock").read_text())["package"]
    output = root / "ios/native-wheels"
    output.mkdir(exist_ok=True)
    subprocess.run(["rustup", "target", "add", "aarch64-apple-ios"], check=True)
    for name in ("pydantic-core", "cryptography"):
        package = next(p for p in packages if p["name"] == name)
        source = package["sdist"]
        with tempfile.TemporaryDirectory(prefix="coding2api-ios-") as temporary:
            work = Path(temporary)
            archive = work / "source.tar.gz"
            urllib.request.urlretrieve(source["url"], archive)
            if "sha256:" + hashlib.sha256(archive.read_bytes()).hexdigest() != source["hash"]:
                raise ValueError(f"Source hash mismatch: {name}")
            with tarfile.open(archive) as stream:
                stream.extractall(work / "source", filter="data")
            roots = list((work / "source").iterdir())
            if len(roots) != 1:
                raise ValueError("Unexpected source archive layout")
            env = dict(os.environ, CIBW_BUILD="cp313-ios_arm64_iphoneos",
                       CIBW_ARCHS_IOS="arm64_iphoneos",
                       CIBW_XBUILD_TOOLS_IOS="cargo rustc rustup",
                       IPHONEOS_DEPLOYMENT_TARGET="16.0")
            # cibuildwheel's package-specific upstream hooks are retained. Missing
            # OpenSSL/PyO3 target support must fail, not silently omit the extension.
            subprocess.run([sys.executable, "-m", "cibuildwheel", str(roots[0]),
                            "--platform", "ios", "--output-dir", str(output)],
                           env=env, check=True)


if __name__ == "__main__":
    main()
