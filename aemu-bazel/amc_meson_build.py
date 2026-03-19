#!/usr/bin/env python3
import argparse
import os
import shutil
import subprocess
import sys
import json
import platform
from pathlib import Path

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

    # Determine platform specific paths
    system = platform.system().lower()
    machine = platform.machine().lower()

    if system == "darwin":
        icd_filename_arch = "aarch64" if machine == "arm64" else "x86_64" # mac reports arm64
        shared_lib_ext = ".dylib"
        lib_subdir = ""
    else:
        # Linux assumption from original script
        icd_filename_arch = "x86_64"
        shared_lib_ext = ".so"
        lib_subdir = "x86_64-linux-gnu"

    icd_basename = f"lvp_icd.{icd_filename_arch}.json"
    icd_src_path = output_dir / "build" / "release" / "share" / "vulkan" / "icd.d" / icd_basename

    # Fallback if specific arch not found (maybe just lvp_icd.json?)
    if not icd_src_path.exists():
         # check for other likely names if needed, but logs showed lvp_icd.aarch64.json
         pass

    if icd_src_path.exists():
        print(f"--- Post-processing {icd_src_path} ---")
        try:
            with open(icd_src_path, "r") as f:
                icd_data = json.load(f)

            # Check if this needs to vary by platform (dylib vs so)
            target_lib_name = f"libvulkan_lvp{shared_lib_ext}"
            # Original script forced ./libvulkan_lvp.so, let's respect that structure but use correct extension
            target_lib_path = f"./{target_lib_name}"

            print(f"Updating library_path from '{icd_data.get('ICD', {}).get('library_path')}' to '{target_lib_path}'")
            icd_data["ICD"]["library_path"] = target_lib_path

            with open(icd_src_path, "w") as f:
                json.dump(icd_data, f, indent=4)
            print(f"Successfully updated {icd_src_path}")
        except Exception as e:
            print(f"Error post-processing {icd_src_path}: {e}")

    # Copy artifacts if install_dir is specified
    if args.install_dir:
        install_dir = Path(args.install_dir).resolve()
        install_dir.mkdir(parents=True, exist_ok=True)
        print(f"--- Copying artifacts to {install_dir} ---")

        # Determine source lib directory
        base_lib_dir = output_dir / "build" / "release"
        if lib_subdir == "bin":
             lib_src_dir = base_lib_dir / "bin"
             # Windows DLLs might not be in a subdir if using some layouts, but strict check above suggests bin.
        else:
             lib_src_dir = base_lib_dir / "lib"
             if lib_subdir:
                lib_src_dir = lib_src_dir / lib_subdir

        # Define artifacts to copy
        artifacts_to_copy = []

        # Vulkan artifacts
        artifacts_to_copy.append((icd_src_path, "lvp_icd.json"))
        artifacts_to_copy.append((lib_src_dir / f"libvulkan_lvp{shared_lib_ext}", f"libvulkan_lvp{shared_lib_ext}"))

        # OpenGL / GLES / EGL / GBM libraries
        gl_libs = ["libGL", "libEGL", "libGLESv2", "libGLESv1_CM", "libgbm"]
        for lib in gl_libs:
             so_name = f"{lib}{shared_lib_ext}"
             artifacts_to_copy.append((lib_src_dir / so_name, so_name))

        # Libgallium (glob)
        # Find files matching libgallium*.so*
        if lib_src_dir.exists():
            for gallium_lib in lib_src_dir.glob(f"libgallium*{shared_lib_ext}*"):
                 # Only copy regular files
                 if gallium_lib.is_file():
                    artifacts_to_copy.append((gallium_lib, gallium_lib.name))

        # DRI drivers
        dri_src_dir = lib_src_dir / "dri"
        if dri_src_dir.exists():
            (install_dir / "dri").mkdir(parents=True, exist_ok=True)
            dri_drivers = ["swrast_dri.so", "kms_swrast_dri.so", "libdril_dri.so", "virtio_gpu_dri.so"]
            for driver in dri_drivers:
                if (dri_src_dir / driver).exists():
                    artifacts_to_copy.append((dri_src_dir / driver, f"dri/{driver}"))

        # GBM backends (gbm/dri_gbm.so)
        gbm_backend_src_dir = lib_src_dir / "gbm"
        if gbm_backend_src_dir.exists():
             (install_dir / "gbm").mkdir(parents=True, exist_ok=True)
             if (gbm_backend_src_dir / "dri_gbm.so").exists():
                 artifacts_to_copy.append((gbm_backend_src_dir / "dri_gbm.so", "gbm/dri_gbm.so"))

        for src_path, dest_rel_path in artifacts_to_copy:
            if src_path.exists():
                dest_path = install_dir / dest_rel_path
                # Ensure parent dir exists
                dest_path.parent.mkdir(parents=True, exist_ok=True)
                print(f"Copying {src_path} to {dest_path}")
                shutil.copy2(src_path, dest_path, follow_symlinks=True)
            else:
                # Only warn if it was an explicitly listed artifact (not generic logic)
                # But since we check exists() before append for dynamic ones, this warning is fine for static list.
                print(f"Warning: Artifact {src_path} not found.")

if __name__ == "__main__":
    main()
