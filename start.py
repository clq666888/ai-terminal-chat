#!/usr/bin/env python3
import sys
import os
import platform

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

system = platform.system()

if system == "Linux" or system == "Darwin":
    target_dir = os.path.join(SCRIPT_DIR, "linux")
elif system == "Windows":
    target_dir = os.path.join(SCRIPT_DIR, "windows")
else:
    print(f"❌ 不支持的系统: {system}")
    sys.exit(1)

entry = os.path.join(target_dir, "api_chat.py")
if not os.path.isfile(entry):
    print(f"❌ 找不到入口文件: {entry}")
    sys.exit(1)

os.chdir(target_dir)
if target_dir not in sys.path:
    sys.path.insert(0, target_dir)
sys.argv[0] = entry

with open(entry, encoding="utf-8") as f:
    code = f.read()
exec(compile(code, entry, "exec"), {"__file__": entry, "__name__": "__main__"})
