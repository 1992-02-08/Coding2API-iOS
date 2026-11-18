"""Run inside cibuildwheel's iOS cross interpreter before cryptography builds."""
from __future__ import annotations

import argparse
import subprocess
import sys
import sysconfig
from pathlib import Path


def write_config(output: Path) -> None:
    if sys.platform != "ios" or sys.implementation._multiarch != "arm64-iphoneos":
        raise ValueError("PyO3 configuration requires the arm64 iPhoneOS cross interpreter")
    if sys.version_info[:2] != (3, 13):
        raise ValueError("Expected the locked CPython 3.13 target")
    candidates = []
    for value in (sysconfig.get_config_var("PYTHONFRAMEWORKPREFIX"),
                  sysconfig.get_config_var("LIBDIR"), sysconfig.get_path("include")):
        if value:
            path = Path(value)
            candidates.extend(parent / "Python.framework" for parent in (path, *path.parents))
    frameworks = {path.resolve() for path in candidates if (path / "Python").is_file()}
    if len(frameworks) != 1:
        raise ValueError(f"Expected exactly one target Python.framework, found {frameworks}")
    framework = frameworks.pop()
    binary = framework / "Python"
    subprocess.run(["xcrun", "lipo", str(binary), "-verify_arch", "arm64"], check=True)
    result = subprocess.run(["xcrun", "vtool", "-show-build", str(binary)],
                            check=True, capture_output=True, text=True)
    if not any(line.split() == ["platform", "IOS"] for line in result.stdout.splitlines()):
        raise ValueError("Python.framework is not an iPhoneOS binary")
    output.write_text(
        "implementation=CPython\nversion=3.13\nshared=true\nabi3=true\n"
        "pointer_width=64\nsuppress_build_script_link_lines=true\n"
        f"extra_build_script_line=cargo:rustc-link-search=framework={framework.parent}\n"
        "extra_build_script_line=cargo:rustc-link-lib=framework=Python\n")
    print(f"PyO3 target framework: {framework}", flush=True)
    print(output.read_text(), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    write_config(parser.parse_args().output)
