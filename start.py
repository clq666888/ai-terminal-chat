#!/usr/bin/env python3
import sys
import os
import platform
import subprocess

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

REQUIRED_PACKAGES = {
    "requests": "requests",
}


def check_python_version():
    if sys.version_info < (3, 7):
        print(f"❌ Python 版本过低: {sys.version}")
        print("   需要 Python 3.7 或更高版本")
        sys.exit(1)


def check_dependencies():
    missing = []
    for import_name, pip_name in REQUIRED_PACKAGES.items():
        try:
            __import__(import_name)
        except ImportError:
            missing.append((import_name, pip_name))

    if not missing:
        return

    print("⚠️ 缺少依赖库:")
    for import_name, pip_name in missing:
        print(f"   - {pip_name}")
    print()

    try:
        answer = input("是否一键安装？(y/n): ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print("\n已取消")
        sys.exit(1)

    if answer in ("y", "yes", "是"):
        pip_names = [pip_name for _, pip_name in missing]
        cmd = [sys.executable, "-m", "pip", "install"] + pip_names
        print(f"🔧 执行: {' '.join(cmd)}")
        result = subprocess.run(cmd)
        if result.returncode != 0:
            print("❌ 安装失败，请手动执行:")
            print(f"   pip install {' '.join(pip_names)}")
            sys.exit(1)
        print("✅ 安装完成\n")
    else:
        print("请手动安装后重试:")
        pip_names = [pip_name for _, pip_name in missing]
        print(f"   pip install {' '.join(pip_names)}")
        sys.exit(1)


def detect_platform():
    system = platform.system()
    if system in ("Linux", "Darwin"):
        return "linux"
    elif system == "Windows":
        return "windows"
    else:
        print(f"❌ 不支持的系统: {system}")
        sys.exit(1)


def main():
    check_python_version()
    check_dependencies()

    plat = detect_platform()
    target_dir = os.path.join(SCRIPT_DIR, plat)
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


if __name__ == "__main__":
    main()
