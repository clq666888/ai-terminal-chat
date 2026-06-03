#!/usr/bin/env python3
import os
import sys
import platform
import subprocess

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def main():
    system = platform.system()
    if system == "Windows":
        script = os.path.join(BASE_DIR, "windows_start.bat")
        if not os.path.exists(script):
            print("[错误] 未找到 windows_start.bat")
            sys.exit(1)
        print("[启动] 检测到 Windows，调用 windows_start.bat ...")
        sys.exit(subprocess.call([script] + sys.argv[1:], shell=True))
    else:
        script = os.path.join(BASE_DIR, "linux_start.sh")
        if not os.path.exists(script):
            print("[错误] 未找到 linux_start.sh")
            sys.exit(1)
        print(f"[启动] 检测到 {system}，调用 linux_start.sh ...")
        try:
            os.chmod(script, 0o755)
        except Exception:
            pass
        sys.exit(subprocess.call(["bash", script] + sys.argv[1:]))


if __name__ == "__main__":
    main()
