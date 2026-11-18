"""Generate a standalone Briefcase staging project on macOS; never alter upstream sources."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import tomllib
from pathlib import Path


def prepare():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", required=True, help="Reverse DNS prefix; app ID ends in .coding2api")
    parser.add_argument("--wheels", type=Path, required=True, help="Directory of compatible iOS wheels")
    args = parser.parse_args()
    if sys.version_info[:2] != (3, 13):
        parser.error("use CPython 3.13 to match the audited iOS wheel ABI")
    root = Path(__file__).resolve().parents[1]
    if (len(args.bundle.split(".")) < 2
            or not args.bundle.isascii()
            or any(not p or not p.replace("-", "").isalnum()
                   for p in args.bundle.split("."))):
        parser.error("bundle must be a reverse DNS prefix")
    if not args.wheels.is_dir():
        parser.error("wheel directory does not exist")
    manifest_path = args.wheels / "SHA256.json"
    if not manifest_path.is_file():
        parser.error("run ios/resolve_wheels.py successfully first; SHA256.json is required")
    manifest = json.loads(manifest_path.read_text())
    wheels = sorted(args.wheels.glob("*.whl"))
    if not wheels or {p.name for p in wheels} != set(manifest):
        parser.error("wheel inventory differs from SHA256.json")
    for wheel in wheels:
        if hashlib.sha256(wheel.read_bytes()).hexdigest() != manifest[wheel.name]:
            parser.error(f"wheel hash mismatch: {wheel.name}")
        if not (wheel.name.endswith("-none-any.whl")
                or ("-ios_" in wheel.name and wheel.name.endswith("_arm64_iphoneos.whl"))):
            parser.error(f"not a device wheel: {wheel.name}")
    if not (root / "web/dist/index.html").is_file():
        parser.error("build the complete web UI first: cd web && pnpm install --frozen-lockfile && pnpm build")
    stage = root / "ios/staging"
    if stage.exists():
        parser.error("ios/staging exists; inspect and remove it manually before regenerating")
    stage.mkdir()
    source = stage / "app"
    source.mkdir()
    shutil.copytree(root / "src", source / "src", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    shutil.copytree(root / "ios/app/coding2api_ios", source / "coding2api")
    shutil.copytree(root / "web/dist", source / "web/dist")
    shutil.copy2(root / "LICENSE", stage / "LICENSE")
    shutil.copy2(root / "NOTICE", source / "NOTICE")
    metadata = tomllib.loads((root / "pyproject.toml").read_text())["project"]
    # Install the exact audited inventory; no resolver may fetch newer backend packages.
    requirements = [str(wheel.resolve()) for wheel in wheels]
    q = json.dumps
    config = f'''[tool.briefcase]
project_name = "Coding2API"
bundle = {q(args.bundle)}
version = {q(metadata["version"])}
url = "https://github.com/RobbsLuo/Coding2API"
license = "MIT"
license_files = ["LICENSE"]
author = "Coding2API contributors"

[tool.briefcase.app.coding2api]
formal_name = "Coding2API"
description = "Complete local Coding2API backend and management UI"
sources = ["app/coding2api", "app/src", "app/web"]
requires = {q(requirements)}

[tool.briefcase.app.coding2api.iOS]
min_os_version = "16.0"
requirement_installer_args = ["--no-index", "--only-binary=:all:", "--find-links", {q(str(args.wheels.resolve()))}]
info.NSAppTransportSecurity.NSAllowsLocalNetworking = true
'''
    (stage / "pyproject.toml").write_text(config, encoding="utf-8")
    print(f"Prepared {stage}. Application ID: {args.bundle}.coding2api")
    print("Wheel inventory verified; keep requirements.txt and SHA256.json with the build evidence.")


if __name__ == "__main__":
    prepare()
