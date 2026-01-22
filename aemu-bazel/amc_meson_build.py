#!/usr/bin/env python3
import argparse
import os
import shutil
import subprocess
import sys
import json
from pathlib import Path

VK_ICD_LIBPATH = "./libvulkan_lvp.so"

def main():
    parser = argparse.ArgumentParser(description="Build Meson project using AMC toolchain.")
    parser.add_argument("--build-config", required=True, help="Path to the build config file.")
    parser.add_argument("--install-dir", help="Optional directory to copy build artifacts to.")
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

    if args.install_dir:
        install_dir = Path(args.install_dir).resolve()
        if not install_dir.exists():
            print(f"Error: Install directory '{install_dir}' not found.")
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

    # Post-process the ICD JSON file in the build output to use a relative path
    # This ensures the modified version is copied if install_dir is provided.
    icd_src_path = output_dir / "build" / "release" / "share" / "vulkan" / "icd.d" / "lvp_icd.x86_64.json"
    if icd_src_path.exists():
        print(f"--- Post-processing {icd_src_path} ---")
        try:
            with open(icd_src_path, "r") as f:
                icd_data = json.load(f)

            print(f"Updating library_path from '{icd_data.get('ICD', {}).get('library_path')}' to '{VK_ICD_LIBPATH}'")
            icd_data["ICD"]["library_path"] = VK_ICD_LIBPATH

            with open(icd_src_path, "w") as f:
                json.dump(icd_data, f, indent=4)
            print(f"Successfully updated {icd_src_path}")
        except Exception as e:
            print(f"Error post-processing {icd_src_path}: {e}")

    if args.install_dir:
        install_dir = Path(args.install_dir).resolve()
        install_dir.mkdir(parents=True, exist_ok=True)
        print(f"--- Copying artifacts to {install_dir} ---")

        # Files to copy and their destination names (optional)
        artifacts = [
            (output_dir / "build" / "release" / "share" / "vulkan" / "icd.d" / "lvp_icd.x86_64.json", "lvp_icd.json"),
            (output_dir / "build" / "release" / "lib" / "x86_64-linux-gnu" / "libvulkan_lvp.so", "libvulkan_lvp.so")
        ]

        for artifact_path, dest_name in artifacts:
            if artifact_path.exists():
                dest_path = install_dir / dest_name
                print(f"Copying {artifact_path} to {dest_path}")
                shutil.copy2(artifact_path, dest_path)
            else:
                print(f"Warning: Artifact {artifact_path} not found.")

if __name__ == "__main__":
    main()
