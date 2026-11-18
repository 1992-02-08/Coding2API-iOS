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


OPENSSL_VERSION = "3.5.4"
OPENSSL_SHA256 = "967311f84955316969bdb1d8d4b983718ef42338639c621ec4c34fddef355e99"


def build_openssl(work: Path) -> Path:
    """Build verified OpenSSL static libraries for physical arm64 iPhones."""
    archive = work / "openssl.tar.gz"
    urllib.request.urlretrieve(
        f"https://github.com/openssl/openssl/releases/download/openssl-{OPENSSL_VERSION}/"
        f"openssl-{OPENSSL_VERSION}.tar.gz", archive)
    if hashlib.sha256(archive.read_bytes()).hexdigest() != OPENSSL_SHA256:
        raise ValueError("OpenSSL source hash mismatch")
    with tarfile.open(archive) as stream:
        stream.extractall(work, filter="data")
    source = work / f"openssl-{OPENSSL_VERSION}"
    prefix = work / "openssl-iphoneos"
    # These commands run on the cloud Mac, never against Homebrew's macOS SSL.
    env = dict(os.environ, IPHONEOS_DEPLOYMENT_TARGET="16.0")
    env.pop("SDKROOT", None)
    subprocess.run(["perl", "Configure", "ios64-xcrun", "no-shared",
                    "no-tests", "-miphoneos-version-min=16.0",
                    f"--prefix={prefix}", "--libdir=lib"],
                   cwd=source, env=env, check=True)
    subprocess.run(["make", f"-j{os.cpu_count() or 2}"],
                   cwd=source, env=env, check=True)
    subprocess.run(["make", "install_sw"], cwd=source, env=env, check=True)
    for name in ("libssl.a", "libcrypto.a"):
        subprocess.run(["xcrun", "lipo", str(prefix / "lib" / name),
                        "-verify_arch", "arm64"], check=True)
    return prefix


def prepare_crypto_codegen(source: Path, work: Path, cffi_version: str) -> Path:
    """Use host CFFI only to emit C; keep target header and ABI queries intact."""
    host = work / "host-codegen"
    subprocess.run([sys.executable, "-m", "venv", str(host)], check=True)
    python = host / "bin/python"
    subprocess.run([str(python), "-m", "pip", "install", "--only-binary=:all:",
                    f"cffi=={cffi_version}"], check=True)
    subprocess.run([str(python), "-c", "from cffi import FFI; FFI()"], check=True)
    script = source / "src/rust/cryptography-cffi/build.rs"
    text = script.read_text()
    original = "let output = Command::new(&python)"
    if text.count(original) != 1:
        raise ValueError("cryptography codegen hook changed; review upstream build.rs")
    # Only the build_openssl.py invocation uses host Python. Later include-dir
    # queries must continue using the cross interpreter configured by maturin.
    script.write_text(text.replace(original, (
        'let output = Command::new(env::var("CODING2API_CODEGEN_PYTHON")'
        '.expect("host codegen Python is required"))')))
    return python


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
            if name == "cryptography":
                cffi = next(p for p in packages if p["name"] == "cffi")
                codegen = prepare_crypto_codegen(roots[0], work, cffi["version"])
                openssl = build_openssl(work)
                env.update(CODING2API_CODEGEN_PYTHON=str(codegen),
                           OPENSSL_DIR=str(openssl), OPENSSL_STATIC="1",
                           OPENSSL_NO_VENDOR="1",
                           CIBW_ENVIRONMENT_IOS=(
                               f'CODING2API_CODEGEN_PYTHON="{codegen}" '
                               f'OPENSSL_DIR="{openssl}" OPENSSL_STATIC=1 '
                               'OPENSSL_NO_VENDOR=1 IPHONEOS_DEPLOYMENT_TARGET=16.0'))
            # Missing PyO3/target support must fail, never omit the extension.
            subprocess.run([sys.executable, "-m", "cibuildwheel", str(roots[0]),
                            "--platform", "ios", "--output-dir", str(output)],
                           env=env, check=True)


if __name__ == "__main__":
    main()
