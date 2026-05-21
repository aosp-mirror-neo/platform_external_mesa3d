# Building mesa3d in AEMU

This directory contains the `mesa3d` source code and scripts to build it within the Android Emulator (AEMU) environment. There are two primary build paths available.

## Prerequisites

*   An Android Open Source Project (AOSP) checkout.
*   The `amc.py` toolchain script available at `$AOSP_ROOT/hardware/google/aemu/tools/toolchain/src/amc.py`.
*   A hermetic Python environment for Meson dependencies, defined in `prebuilts/android-emulator-build/common/vulkan/linux-x86_64/lavapipe-bazel-deps`.

---

## Path 1: Direct Meson Build with AMC Toolchain (Local Iteration)

This path allows you to build `mesa3d` (e.g., Lavapipe) using the Meson build system directly, while still utilizing the hermetic AOSP toolchains and Bazel-managed dependencies. This is the recommended way for rapid local iteration and debugging.

### Build Command
Execute the following from the `third_party/mesa3d` root:

```bash
cd aemu-bazel
python3 amc_meson_build.py \
    --build-config aemu-mesa3d-build-config.jsonc ..
```

### What it does:
1.  **Cleanup**: Removes any existing `aemu-bazel/out-amc` directory.
2.  **Setup**: Invokes `amc.py` to generate AOSP-compatible toolchain wrappers and pkg-config files for Bazel dependencies.
3.  **Configure**: Runs `meson setup` using the generated environment.
4.  **Compile & Install**: Runs `ninja` to build and install artifacts into `aemu-bazel/out-amc`.

---

## Path 2: Generating Bazel Build Files (Integration)

This path uses `amc_meson_build.py` with the `--gen-bazel` flag to convert the Meson project into Bazel `BUILD` files, allowing `mesa3d` to be integrated directly into the larger Bazel build graph.

### Generation Command
Execute the following from the `third_party/mesa3d` root:

```bash
cd aemu-bazel
python3 amc_meson_build.py \
    --build-config aemu-mesa3d-build-config.jsonc \
    --shim aemu-mesa3d-shim.jsonc \
    --gen-bazel ..
```

### Next Steps (Post-Generation):
After running the command, you would typically unzip the results and place the generated `BUILD.bazel` file:
```bash
unzip out-amc/bazel*.zip
mv platform/BUILD.linux-x86_64 ../BUILD.bazel
```

---

## Note on the Python Environment

The build configuration leverages a standalone Bazel module for Python dependencies. This ensures that modules like `jinja2` and `mako`, which are required by the Mesa build scripts, are consistent and do not conflict with host system packages.

If you need to update Python requirements, see the `README.md` in `prebuilts/android-emulator-build/common/vulkan/linux-x86_64/lavapipe-bazel-deps`.