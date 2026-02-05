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

    tool_path = os.path.join(workspace_root, "prebuilts/clang/host/darwin-x86/clang-r584948b/bin/llvm-config")

    if not os.path.exists(tool_path):
        print(f"Error: Cannot find llvm-config at {tool_path}", file=sys.stderr)
        sys.exit(1)

    try:
        result = subprocess.run([tool_path] + sys.argv[1:], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        print(result.stdout, end='')
    except subprocess.CalledProcessError as e:
        print(e.stderr, file=sys.stderr, end='')
        sys.exit(e.returncode)

if __name__ == "__main__":
    main()
