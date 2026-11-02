#!/bin/bash

# ==============================================================================
# Copyright (C) 2026 The Android Open Source Project
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://apache.org
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ==============================================================================

# 1. Set the default preferred directory
MESON_DIRECTORY="$HOME/meson"

# 2. If it IS NOT there, create a temp directory and clone into it
if [ ! -d "$MESON_DIRECTORY" ]; then
    MESON_DIRECTORY=$(mktemp -d)
    echo "Creating and cloning into temporary directory: $MESON_DIRECTORY"
    git clone -b meson2hermetic https://github.com/magma-gpu/mesonbuild.git "$MESON_DIRECTORY"
fi

# 3. Dynamically point to whichever directory is currently active
python3 "$MESON_DIRECTORY/meson.py" convert --config=src/gfxstream/hermetic/android/aosp_mesa3d.toml \
                                 --platforms=src/gfxstream/hermetic/android/platforms.toml \
                                 --dependencies=src/gfxstream/hermetic/android/dependencies.toml
