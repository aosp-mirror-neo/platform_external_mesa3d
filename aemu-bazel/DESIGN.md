# Design Document: `libvulkan_lvp` (Lavapipe) Build System

## Current Status

| Build Method | Linux (x64) | Windows (x64) | macOS (ARM/x64) |
| :--- | :--- | :--- | :--- |
| **Meson + AMC (Shims)** | ✅ Functional | 🚧 Planned | 🚧 Planned |
| **Native Bazel (Generated)** | 🚧 Files Generated | ❌ Not Started | ❌ Not Started |

## 1. Overview
This document describes the build architecture for `libvulkan_lvp` (Mesa's Lavapipe Vulkan software rasterizer) within the Android Emulator codebase. The system uses **AMC (Android Meson Configurator)** to bridge the gap between Mesa's native **Meson** build system and the Emulator's **Bazel** build environment.

For quick instructions on how to run the build, please refer to the [README.aemu.md](../README.aemu.md) file located in the `third_party/mesa3d` root.

The goal is to produce a self-contained Vulkan ICD (Installable Client Driver) consisting of:
1.  `libvulkan_lvp.so/dll/dylib`: The driver binary.
2.  `lvp_icd.json`: The manifest file that tells the Vulkan Loader where to find the binary.

## 2. Key Components

*   **Meson:** The upstream build system used by Mesa 3D. It is excellent at complex C++ builds but doesn't natively understand Bazel's sandboxed environment.
*   **Bazel:** The primary build system for the Android Emulator. It manages all third-party dependencies (like `zlib`, `expat`, `libdrm`).
*   **amc.py (Android Meson Configurator):** A specialized tool located in `hardware/google/aemu/tools/toolchain/src/amc.py`. It performs two critical tasks:
    *   **Dependency Mapping:** It looks at Bazel targets and generates "Shims" (fake `pkg-config` files). This tells Meson: "When you look for `zlib`, use these headers and libraries from the Bazel cache."
    *   **Toolchain Generation:** It generates a Meson "cross-file" that points Meson to the correct compilers and tools provided by Bazel.
*   **aemu-mesa3d-build-config.jsonc:** The configuration file that defines which Bazel libraries map to which Meson dependencies.

## 3. Build Workflow (`amc_meson_build.py`)

When you run the build script, the following happens:

1.  **Setup Phase (`amc.py setup`):**
    *   AMC reads `aemu-mesa3d-build-config.jsonc`.
    *   It locates the Bazel targets for dependencies (e.g., `@zlib//:zlib`).
    *   It creates a `toolchain/` directory containing `pkg-config` files (`.pc`).
2.  **Meson Configuration:**
    *   AMC invokes `meson setup` using the generated cross-file. Meson now "sees" the Bazel dependencies as if they were installed on the system.
3.  **Compilation:**
    *   The script runs `ninja` to compile the code and `ninja install` to gather the results into a local `out-amc/build/release` folder.
4.  **Post-Processing:**
    *   The script modifies the `lvp_icd.json` file to use a relative path (`./libvulkan_lvp.so`) so the driver remains portable.

## 4. Developer Tools & Shortcuts (`mise`)

For convenience, a `mise.toml` file is provided in this directory. If you have [mise](https://mise.jdx.dev/) installed, you can use it to automate common tasks.

**Pro Tip:** To allow VS Code to use the environment defined in this file, symlink it to the root of the emulator project:
`ln -sf third_party/mesa3d/aemu-bazel/mise.toml mise.local.toml`

### Available Task Categories:
*   **Build**: `mise run build-lavapipe-amc-meson` — Performs the complete build and installs results to the local prebuilts directory.
*   **Validation**: `mise run run-vulkaninfo-lavapipe` — Runs `vulkaninfo` against the freshly built library to ensure the ICD is valid.
*   **Maintenance**: `mise run copy-lavapipe-deps-prebuilts` — Manually co-locates required shared libraries (like `libxcb-aemu.so`) and fixes their `RUNPATH`.
*   **Experimental**: Tasks like `gen-bazel-files-lavapipe` for generating the native Bazel build files.
*   **General Bazel**: `mise run bazel-clean` — Wipes the workspace cache.

## 5. Packaging and Portability (Post-Build)

For the Linux build to be truly self-contained and portable (e.g., to run on different distributions without pre-installed LLVM), several shared libraries must be gathered from the Bazel environment and placed alongside the driver.

### Required Dependencies (Linux):
- `libxcb-aemu.so`: Our custom XCB build from Bazel.
- `libLLVM.so`: The JIT compiler provided by our hermetic toolchain.
- `libedit.so.0`, `libxml2.so.2`, `libncurses.so.6`: Indirect dependencies required by LLVM.

### Current Status: 🚧 Not Yet Automated
This gathering step is **not yet implemented** in the `amc_meson_build.py` script. Currently, these files must be manually located in the Bazel execution root and copied to the final destination (e.g., `prebuilts/android-emulator-build/common/vulkan/linux-x86_64/icds/`).

Additionally, once these libraries are co-located, the `RUNPATH` of `libvulkan_lvp.so` must be updated (using `patchelf`) to include `$ORIGIN` so it can find its dependencies at runtime.

## 5. Build Artifacts: The `out-amc` Directory

After running the build script, an `out-amc` directory is created. This directory contains everything needed to bridge Bazel and Meson.

### Directory Structure
```text
out-amc/
├── toolchain/           # The AMC-generated toolchain environment
│   ├── pc-config/       # Generated .pc files (Shims) for dependencies
│   │   ├── zlib.pc
│   │   ├── expat.pc
│   │   └── ...
│   ├── aosp-cl.ini      # Meson native file defining the toolchain
│   ├── cc, c++, meson   # Symlinks/wrappers to Bazel-provided tools
│   └── ...
└── build/               # The Meson build directory
    ├── release/         # Final installation directory (The "Result")
    │   ├── lib/         # Contains libvulkan_lvp.so
    │   └── share/       # Contains lvp_icd.json
    ├── build.ninja      # Generated by Meson
    ├── meson-logs/      # Detailed logs of the Meson configuration phase
    └── bazel-logs/      # Logs showing how AMC queried Bazel for targets
```

### Key Components Explained:
*   **`toolchain/pc-config/`**: This is the heart of the dependency mapping. AMC generates a `.pc` file for every Bazel dependency listed in the config. These files contain the absolute paths to the headers and libraries within the Bazel execution root.
*   **`toolchain/aosp-cl.ini`**: A Meson "native file" that tells Meson which compilers to use and sets the `PKG_CONFIG_PATH` to point to the `pc-config` directory above.
*   **`build/release/`**: This is where the build results are "installed". When extending to new platforms, this is the folder you will inspect to find the resulting `.dll` or `.dylib`.

## 5. Deep Dive: Common Questions

### Where does the compiler come from?
We do **not** use the system compiler (e.g., `/usr/bin/gcc`). Instead, AMC queries Bazel to find the paths to our hermetic toolchain (located in `prebuilts/clang/...`). This ensures that the build is identical across all developer machines and CI bots.

### What is a "Shim" and why do we need them?
Meson usually finds libraries using a tool called `pkg-config`. However, Bazel doesn't install libraries globally. AMC solves this by generating "Shim" `.pc` files inside `out-amc/toolchain/pc-config`. When Meson asks for `zlib`, our shim tells it: "Use the headers in `/some/long/bazel/path` and the library in `/another/bazel/path`."

### How is LLVM handled?
LLVM is the most critical dependency for Lavapipe as it acts as the Just-In-Time (JIT) compiler for the software rasterizer. Meson does **not** use `pkg-config` for LLVM; instead, it looks for a tool called `llvm-config`.

In our current setup:
1.  **Origin:** We use a prebuilt LLVM toolchain fetched from Android Build (`go/ab/14054515`). This is located in `prebuilts/android-emulator-build/common/vulkan/linux-x86_64/lavapipe-bazel-deps/llvm-prebuilt`.
2.  **Bazel Wrapper:** We define `llvm-config` in the `binaries` section of `aemu-mesa3d-build-config.jsonc`. This points to a Bazel `py_binary` target that wraps the prebuilt tool.
3.  **AMC Integration:** AMC ensures this `llvm-config` is in the `PATH` when Meson runs. When Meson executes `llvm-config --cflags` or `--libs`, our wrapper returns the correct paths pointing into the Bazel prebuilt directory.

**⚠️ Warning:** Using prebuilts is a **short-term solution** to bootstrap the build. The long-term architectural goal is to build LLVM directly from source within Bazel to ensure full hermeticity and allow for optimizations/patches specifically for the emulator.

### How do I find the Bazel target for a library?
If you need to add a dependency like `libpng`, you need its Bazel "Label".
1.  Search the `WORKSPACE` file at the root of the emulator project.
2.  Use the `bazel query` command:
    ```bash
    ./prebuilts/bazel/linux-x86_64/bazel query //third_party/... | grep png
    ```
3.  Common third-party targets are usually named `@libname//:targetname`.

### How do I add a dependency that Meson requires?
1.  Open `aemu-mesa3d-build-config.jsonc`.
2.  Add an entry under `dependencies`.
3.  Set `bazel_target` to the label you found.
4.  Set `Libs` to the flag needed to link it (e.g., `-lpng` for Linux/Mac or `libpng.lib` for Windows).

### Local Bazel Registry & Forking Modules
In this project, we don't always use the standard libraries from the [Bazel Central Registry (BCR)](https://bcr.bazel.build). Often, we need to "fork" a module to apply patches or fix build issues specific to the emulator.

#### How it works:
Our Bazel configuration (in `build/bazel/base.bazelrc`) is set up to look at our local registry **before** the official BCR:
```bazelrc
common --registry=file:///%workspace%/build/bazel/registry
common --registry=https://bcr.bazel.build
```

#### Why we fork:
We fork modules (like `libdrm`, `libxcb`, `zlib`) to:
*   Add missing headers to the `cc_library` exports.
*   Apply patches for Windows/macOS compatibility.
*   Ensure the version is locked to exactly what we've tested.

#### How to identify a forked module:
Check the `MODULE.bazel` file at the root. If a dependency has a version ending in `.aemu` (e.g., `zlib = "1.3.1.bcr.5.aemu"`), it is coming from our local registry in `build/bazel/registry/modules`.

#### The Forking Process:
If you need to modify a third-party library for Windows or Mac:
1.  **Locate the module** in `build/bazel/registry/modules/<name>`.
2.  **Create a new version folder** (e.g., copy `1.2.3` to `1.2.3.aemu`).
3.  **Modify the Overlay**: Forked modules use an "overlay" system. You modify the `BUILD.bazel` file inside the `overlay/` directory of your new version.
4.  **Update Hashes**: Bazel is strict about security. If you change a file in the overlay, you **must** update its SHA-256 hash in the `source.json` file for that version.
5.  **Point to the new version**: Update the main `MODULE.bazel` at the project root to use your `.aemu` version.

## 6. How to Extend to Windows and macOS

To add support for a new platform, you must modify the `platforms` section in `aemu-mesa3d-build-config.jsonc`.

### Step 1: Define the Platform
Add a new block for `windows-x64` or `darwin-arm64`.

```jsonc
"platforms": {
  "windows-x64": {
    "meson_options": {
      "-Dcpp_args": "...", // Windows specific compiler flags
      "-Dplatforms": "windows"
    },
    "binaries": {
        // Paths to Windows-specific build tools
        "python3": "@lavapipe_bazel_deps_windows//:python3",
        "llvm-config": "//prebuilts/.../windows-x86_64/...:llvm_config"
    },
    "dependencies": {
       // Platform-specific dependency mapping
    }
  }
}
```

### Step 2: Map Dependencies
Every library Mesa needs (Zlib, Expat, etc.) must be mapped to its Bazel equivalent for that platform.

*   **`bazel_target`**: The actual Bazel label (e.g., `@zlib//:zlib`).
*   **`shim`**: The metadata used to generate the `.pc` file.
    *   `Libs`: The link flags (e.g., `-lz` for Linux, `zlib.lib` for Windows).
    *   `include_target`: (Optional) If the headers are in a different Bazel target.

### Step 3: Handle Platform Binaries
Mesa requires certain tools during the build (like `llvm-config` and `glslangValidator`). You must ensure these are defined in the `binaries` section for the target platform so AMC can find them in the Bazel tree.

## 7. Troubleshooting
*   **"Dependency not found":** Check that the name in `dependencies` matches exactly what Meson is looking for in its `meson.build` files (e.g., `dependency('zlib')`).
*   **Missing Headers:** Ensure the `bazel_target` includes the necessary header files.
*   **Linker Errors:** Verify the `Libs` string in the `shim` section matches the actual library name produced by Bazel.

## 8. Future Goal: Native Bazel Build

Currently, we use Meson as an intermediate step to build Lavapipe. However, we have integrated Bazel file generation into `amc_meson_build.py` via the `--gen-bazel` flag.

### What is it?
This script represents our "North Star" for the build system. It uses `amc.py` in `bazel` mode to **generate** Bazel `BUILD` files directly from the Mesa source tree. It takes the upstream Meson logic and "transpiles" it into Bazel rules.

### Why do we want this?
*   **Full Hermeticity**: Bazel can manage the entire dependency graph and compilation environment more strictly than Meson can when running inside a Bazel-managed script.
*   **Caching**: Native Bazel rules allow for fine-grained action caching, making incremental builds much faster across the team.
*   **No Build-time Dependencies**: Once the `BUILD` files are generated, we no longer need Meson or Ninja installed on the build machine.

### Current Status: 🚧 Files Generated
This path is now functional for file generation on Linux, but full verification of the Bazel build is still pending.

For now, when extending support to Windows or macOS, you should focus on the **Meson-based workflow** (`amc_meson_build.py`) described in the sections above. Once the generated Bazel files are stable for Linux, we will begin the transition for other platforms.
