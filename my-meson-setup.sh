#!/bin/bash

# This script is meant to build lavapipe with the toolchain generated from amc.py.
# To generate the toolchain, first run my-amc.sh before running this script.
PYTHONPATH=$HOME/work/main-emu-next-dev/third_party/meson
QEMU_NEXT_ROOT=$HOME/work/main-emu-next-dev
MESA_ROOT=$QEMU_NEXT_ROOT/third_party/mesa3d
TOOLCHAIN_DIR=$MESA_ROOT/amc-build/toolchain
NATIVE_FILE=$TOOLCHAIN_DIR/aosp-cl.ini
MESON_EXE=$QEMU_NEXT_ROOT/third_party/meson/meson.py
MESON_BUILD_DIR=$QEMU_NEXT_ROOT/mesa-amc-meson-build

function run() {
    echo "CMD>> $@"
    $@
}

# Setup meson build
run python3 -m venv .venv
run source .venv/bin/activate
run pip install jinja2 mako
# Linux configuration
run python3 $MESON_EXE setup $MESON_BUILD_DIR --native-file $NATIVE_FILE -Dvulkan-drivers=swrast -Dgallium-drivers=llvmpipe -Dopengl=false -Degl=disabled -Dgles1=disabled -Dgles2=disabled -Dvideo-codecs=[] -Dzstd=disabled -Dshared-llvm=disabled -Dplatforms=x11,wayland
echo "Done running meson setup. Build directory is at $MESON_BUILD_DIR"
