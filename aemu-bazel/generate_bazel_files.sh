#!/bin/bash

set -e

# Get the absolute path of the script's directory
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)

# Deduce AOSP_ROOT based on script location
AOSP_ROOT=$(realpath "$SCRIPT_DIR/../../..")

# Define absolute paths for config files
CONFIG_FILE="$SCRIPT_DIR/aemu-mesa3d-build-config.jsonc"
SHIM_FILE="$SCRIPT_DIR/aemu-mesa3d-shim.jsonc"

# The directory where the python script should be run from
REPO_ROOT=$(realpath "$SCRIPT_DIR/..")

# The path to the python script
AMC_PYTHON="$AOSP_ROOT/hardware/google/aemu/tools/toolchain/src/amc.py"
BAZEL_AMC="//hardware/google/aemu/tools/toolchain:amc"

# The output build path. This directory will contain the zip file containing
# the BUILD file and config.h
AMC_BUILD_PATH="$SCRIPT_DIR/amc-build"

# Change to the repository root to run the script
cd "$REPO_ROOT"

# mesa needs to use python3, so let's make it find the same one amc.py is using.
# TODO: We need to run a python file first to make bazel setup the python3 directories.
# For now, to workaround, I do:
# > ../../bazel-bin/./hardware/google/aemu/tools/toolchain/amc.runfiles/rules_python++python+python_3_10_x86_64-unknown-linux-gnu/bin/python3 -m venv .venv
# > source .venv/bin/activate
# > python3 -m pip install mako PyYAML
source .venv/bin/activate

# Generate bazel build files with amc.py:
python3 "$AMC_PYTHON" -v bazel \
    --config "$CONFIG_FILE" \
    --aosp "$AOSP_ROOT" \
    --shim "$SHIM_FILE" \
    "$AMC_BUILD_PATH"
# bazel run $BAZEL_AMC -- -v bazel \
#     --config "$CONFIG_FILE" \
#     --aosp "$AOSP_ROOT" \
#     --shim "$SHIM_FILE" \
#     "$AMC_BUILD_PATH"

echo "Done! Unzip the zip file in $AMC_BUILD_PATH to the repo root " \
     "($REPO_ROOT) to get the bazel files"
