"""Download the locked backend and pinned Toga wheels; fail on absent iOS binaries."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[1]
    output = root / "ios/wheels"
    output.mkdir(exist_ok=False)
    requirements = output / "requirements.txt"
    subprocess.run([
        "uv", "export", "--frozen", "--no-dev", "--no-emit-project", "--no-hashes",
        "--output-file", str(requirements),
    ], cwd=root, check=True)
    with requirements.open("a") as stream:
        stream.write("\ntoga-iOS==0.5.7\n")
    # pip's explicit --platform does not expand older iOS deployment targets.
    platforms = [f"ios_{major}_{minor}_arm64_iphoneos"
                 for major in range(16, 12, -1) for minor in range(7) if (major, minor) <= (16, 0)]
    platform_args = [arg for platform in platforms for arg in ("--platform", platform)]
    subprocess.run([
        sys.executable, "-m", "pip", "download", "--only-binary=:all:",
        *platform_args, "--python-version", "313",
        "--implementation", "cp", "--abi", "cp313", "--abi", "abi3",
        "--dest", str(output), "--find-links", str(root / "ios/native-wheels"),
        "--requirement", str(requirements),
    ], check=True)
    manifest = {}
    for wheel in sorted(output.glob("*.whl")):
        # A generic pure Python wheel or a physical-device wheel, never macOS/simulator.
        if not (wheel.name.endswith("-none-any.whl")
                or ("-ios_" in wheel.name and wheel.name.endswith("_arm64_iphoneos.whl"))):
            raise ValueError(f"Incompatible wheel: {wheel.name}")
        manifest[wheel.name] = hashlib.sha256(wheel.read_bytes()).hexdigest()
    if not manifest:
        raise ValueError("No wheels downloaded")
    (output / "SHA256.json").write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    main()
