#!/usr/bin/env python3
import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(description="Build Meson project using AMC toolchain.")
    parser.add_argument("--build-config", required=True, help="Path to the build config file.")
    parser.add_argument("meson_project_dir", help="Directory of the Meson project.")
    
    args = parser.parse_args()

    build_config_path = Path(args.build_config).resolve()
    meson_project_dir = Path(args.meson_project_dir).resolve()

    if not build_config_path.exists():
        print(f"Error: Build config file '{build_config_path}' not found.")
        sys.exit(1)

    if not meson_project_dir.exists():
        print(f"Error: Directory '{meson_project_dir}' not found.")
        sys.exit(1)

    # Set paths relative to this script
    script_dir = Path(__file__).resolve().parent
    # AOSP_ROOT is 3 levels up from third_party/mesa3d/aemu-bazel
    aosp_root = script_dir.parents[2]
    output_dir = script_dir / "out-amc"

    if not aosp_root.exists():
        print(f"Error: AOSP_ROOT directory not found at {aosp_root}")
        sys.exit(1)

    amc_py_path = aosp_root / "hardware" / "google" / "aemu" / "tools" / "toolchain" / "src" / "amc.py"

    if not amc_py_path.exists():
        print(f"Error: amc.py not found at {amc_py_path}")
        sys.exit(1)

    # Step 1: Generate the AMC Toolchain and Setup Meson
    print("--- Cleaning up output directory ---")
    if output_dir.exists():
        print(f"Removing existing output directory: {output_dir}")
        shutil.rmtree(output_dir)

    print("--- Running amc.py setup ---")
    # We run from meson_project_dir to match the behavior of 'cd "$MESON_PROJECT_DIR"' in the shell script
    try:
        subprocess.check_call(
            [sys.executable, str(amc_py_path), "-v", "setup", "--aosp", str(aosp_root), "--config", str(build_config_path), str(output_dir)],
            cwd=meson_project_dir
        )
    except subprocess.CalledProcessError as e:
        print(f"Error running amc.py: {e}")
        sys.exit(1)

    print("--- Verifying amc.py setup output ---")
    build_dir = output_dir / "build"
    toolchain_dir = output_dir / "toolchain"

    if not build_dir.is_dir():
        print(f"Error: '{build_dir}' directory not found after setup.")
        sys.exit(1)

    if not toolchain_dir.is_dir():
        print(f"Error: '{toolchain_dir}' directory not found after setup.")
        sys.exit(1)
    
    print("--- Verification successful ---")

    # Step 2: Compile the Project with Ninja
    print("--- Compiling with ninja ---")
    
    # Update PATH to include toolchain dir
    env = os.environ.copy()
    env["PATH"] = str(toolchain_dir) + os.pathsep + env["PATH"]
    
    print(f"MY_PATH=[{env['PATH']}]")

    # Determine ninja executable name
    ninja_exe_name = "ninja.exe" if os.name == "nt" else "ninja"
    ninja_exe_path = toolchain_dir / ninja_exe_name

    # The shell script runs `./ninja` from inside `toolchain_dir`.
    # We replicate this behavior.
    
    try:
        # Build
        subprocess.check_call(
            [str(ninja_exe_path), "-C", "../build"],
            cwd=toolchain_dir,
            env=env
        )
        # Install
        subprocess.check_call(
            [str(ninja_exe_path), "-C", "../build", "install"],
            cwd=toolchain_dir,
            env=env
        )
    except subprocess.CalledProcessError as e:
        print(f"Error running ninja: {e}")
        sys.exit(1)

    print("--- Build complete ---")
    print(f"Output directory: {output_dir}")

if __name__ == "__main__":
    main()
