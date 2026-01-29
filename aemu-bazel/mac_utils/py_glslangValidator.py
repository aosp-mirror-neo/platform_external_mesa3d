#!/usr/bin/env python3
import os
import sys
import subprocess

from pathlib import Path

def main():
    # Set paths relative to this script
    script_dir = Path(__file__).resolve().parent
    # Workspace root is 4 levels up
    workspace_root = script_dir.parents[3]

    tool_path = os.path.join(workspace_root, "prebuilts/android-emulator-build/common/vulkan/darwin-aarch64/glslangValidator")

    if not os.path.exists(tool_path):
        print(f"Error: Cannot find glslangValidator at {tool_path}", file=sys.stderr)
        sys.exit(1)

    os.execv(tool_path, [tool_path] + sys.argv[1:])

if __name__ == "__main__":
    main()
