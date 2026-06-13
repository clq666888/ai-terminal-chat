#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PolyAI Chat 一体化启动器（跨平台，单文件）

点开即用：自动检测系统、检测必要依赖、询问并一键安装、启动网页端并打开浏览器。

用法:
    python start.py            启动（默认，可双击运行）
    python start.py stop       关闭
    python start.py restart    重启
    python start.py status     查看运行状态
    python start.py log        查看最近日志
    python start.py install    仅检测并安装依赖
"""
import os
import sys
import time
import platform
import subprocess
import webbrowser

# 强制无缓冲 + 行缓冲，避免 Windows PowerShell + py 启动器组合下
# 输出被缓冲、程序退出后整块丢失（用户看不到任何提示）的问题。
os.environ.setdefault("PYTHONUNBUFFERED", "1")
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", line_buffering=True)
    except Exception:
        try:
            _stream.reconfigure(encoding="utf-8")
        except Exception:
            pass


def _print(*args, **kwargs):
    kwargs.setdefault("flush", True)
    print(*args, **kwargs)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WEB_DIR = os.path.join(BASE_DIR, "web")
APP_FILE = os.path.join(WEB_DIR, "app.py")
PID_FILE = os.path.join(WEB_DIR, ".polyai.pid")
LOG_FILE = os.path.join(WEB_DIR, ".polyai.log")
PORT = 8080
URL = f"http://localhost:{PORT}"

IS_WINDOWS = platform.system() == "Windows"

# 必要 Python 包: (pip 名, import 名)
REQUIRED_PKGS = [("flask", "flask"), ("requests", "requests")]
# 可选 Python 包（文件解析功能需要）
OPTIONAL_PKGS = [("PyPDF2", "PyPDF2"), ("python-docx", "docx"), ("openpyxl", "openpyxl")]


def _ask(prompt, default_yes=True):
    suffix = "[Y/n]" if default_yes else "[y/N]"
    try:
        ans = input(f"{prompt} {suffix} ").strip().lower()
    except EOFError:
        ans = ""
    if not ans:
        return default_yes
    return ans in ("y", "yes")


def _module_available(import_name):
    try:
        kwargs = {"stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
        if IS_WINDOWS:
            kwargs["creationflags"] = 0x08000000  # CREATE_NO_WINDOW
        subprocess.check_call(
            [sys.executable, "-c", f"import {import_name}"],
            **kwargs,
        )
        return True
    except Exception:
        return False


def _pip_install(pkgs):
    _print(f"⏳ 正在安装: {' '.join(pkgs)}")
    cmds = [
        [sys.executable, "-m", "pip", "install", "--user", *pkgs],
        [sys.executable, "-m", "pip", "install", *pkgs],
    ]
    for cmd in cmds:
        try:
            if subprocess.call(cmd) == 0:
                _print("✅ 安装完成")
                return True
        except Exception:
            continue
    _print(f"❌ 安装失败，请手动执行: {sys.executable} -m pip install {' '.join(pkgs)}")
    return False


def _has_pip():
    try:
        kwargs = {"stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
        if IS_WINDOWS:
            kwargs["creationflags"] = 0x08000000  # CREATE_NO_WINDOW
        subprocess.check_call(
            [sys.executable, "-m", "pip", "--version"],
            **kwargs,
        )
        return True
    except Exception:
        return False


def check_dependencies():
    """返回 True 表示依赖就绪，可继续启动。"""
    if sys.version_info < (3, 8):
        _print(f"❌ 需要 Python 3.8+，当前为 {platform.python_version()}")
        return False

    if not _has_pip():
        _print("❌ 未检测到 pip，请先安装 pip 后重试")
        if IS_WINDOWS:
            _print("   下载 Python: https://www.python.org/downloads/（安装时勾选 Add Python to PATH）")
        else:
            _print("   安装示例: sudo apt-get install -y python3-pip")
        return False

    missing_req = [pip for pip, imp in REQUIRED_PKGS if not _module_available(imp)]
    if missing_req:
        _print("❌ 缺少必要 Python 包:")
        for p in missing_req:
            _print(f"   • {p}")
        _print()
        if _ask("是否一键安装?", default_yes=True):
            if not _pip_install(missing_req):
                return False
        else:
            _print(f"请手动安装: {sys.executable} -m pip install {' '.join(missing_req)}")
            return False

    missing_opt = [pip for pip, imp in OPTIONAL_PKGS if not _module_available(imp)]
    if missing_opt:
        _print("⚠️  以下可选包未安装（文件解析功能需要）:")
        for p in missing_opt:
            _print(f"   • {p}")
        _print()
        if _ask("是否安装可选包?", default_yes=False):
            _pip_install(missing_opt)

    return True


def _read_pid():
    if not os.path.exists(PID_FILE):
        return None
    try:
        with open(PID_FILE, "r") as f:
            pid = int(f.read().strip())
        return pid
    except Exception:
        return None


def _pid_alive(pid):
    if pid is None:
        return False
    if IS_WINDOWS:
        try:
            out = subprocess.check_output(
                ["tasklist", "/FI", f"PID eq {pid}"],
                stderr=subprocess.DEVNULL,
                creationflags=0x08000000,
            ).decode("utf-8", "ignore").lower()
            return "python" in out
        except Exception:
            return False
    else:
        try:
            os.kill(pid, 0)
            return True
        except Exception:
            return False


def is_running():
    pid = _read_pid()
    if pid and _pid_alive(pid):
        return pid
    if os.path.exists(PID_FILE):
        try:
            os.remove(PID_FILE)
        except Exception:
            pass
    return None


def _free_port():
    if IS_WINDOWS:
        try:
            out = subprocess.check_output(
                f'netstat -ano | findstr ":{PORT} "',
                shell=True, stderr=subprocess.DEVNULL,
                creationflags=0x08000000,
            ).decode("utf-8", "ignore")
            for line in out.splitlines():
                if "LISTENING" in line.upper() or "ESTABLISHED" in line.upper():
                    parts = line.split()
                    if parts:
                        pid = parts[-1]
                        _print(f"⚠️  端口 {PORT} 被占用 (PID: {pid})，正在释放...")
                        subprocess.call(["taskkill", "/PID", pid, "/F"],
                                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                        creationflags=0x08000000)
        except Exception:
            pass
    else:
        try:
            out = subprocess.check_output(
                ["lsof", "-ti", f":{PORT}"], stderr=subprocess.DEVNULL,
            ).decode().strip()
            for pid in out.splitlines():
                if pid:
                    _print(f"⚠️  端口 {PORT} 被占用 (PID: {pid})，正在释放...")
                    subprocess.call(["kill", pid], stderr=subprocess.DEVNULL)
            if out:
                time.sleep(1)
        except Exception:
            pass


def do_start():
    if not os.path.exists(APP_FILE):
        _print(f"❌ 找不到 {APP_FILE}")
        return 1

    if not check_dependencies():
        return 1

    existing = is_running()
    if existing:
        _print(f"⚠️  PolyAI Chat 已在运行 (PID: {existing})")
        _print(f"📎 访问: {URL}")
        _print(f"🛑 关闭: python start.py stop")
        webbrowser.open(URL)
        return 0

    _free_port()

    try:
        with open(LOG_FILE, "w", encoding="utf-8") as f:
            f.write("")
    except Exception:
        pass

    logf = open(LOG_FILE, "a", encoding="utf-8", errors="ignore")
    child_env = dict(os.environ)
    child_env["PYTHONUNBUFFERED"] = "1"  # 后台 app.py 日志实时写入，避免被缓冲
    child_env["PYTHONIOENCODING"] = "utf-8"
    kwargs = {
        "cwd": WEB_DIR,
        "stdout": logf,
        "stderr": subprocess.STDOUT,
        "stdin": subprocess.DEVNULL,  # 关键：关闭 stdin 防止后台子进程因读取失败而退出
        "env": child_env,
    }
    if IS_WINDOWS:
        kwargs["creationflags"] = (
            0x00000008 | 0x08000000  # DETACHED_PROCESS | CREATE_NO_WINDOW
        )
    else:
        kwargs["start_new_session"] = True

    proc = subprocess.Popen([sys.executable, "app.py"], **kwargs)
    pid = proc.pid

    with open(PID_FILE, "w") as f:
        f.write(str(pid))

    time.sleep(2)

    if _pid_alive(pid):
        _print(f"✅ PolyAI Chat 已启动 (PID: {pid})")
        _print(f"📎 访问: {URL}")
        _print(f"📋 日志: python start.py log")
        _print(f"🛑 关闭: python start.py stop")
        webbrowser.open(URL)
        return 0

    try:
        os.remove(PID_FILE)
    except Exception:
        pass
    _print("❌ 启动失败，最近日志:")
    _print(_tail(LOG_FILE, 20))
    return 1


def _notify_shutdown():
    try:
        import urllib.request
        req = urllib.request.Request(f"{URL}/__shutdown__", method="POST")
        urllib.request.urlopen(req, timeout=5)
    except Exception:
        pass


def do_stop():
    _notify_shutdown()
    time.sleep(1)
    pid = is_running()
    if not pid:
        _print("ℹ️  PolyAI Chat 未在运行")
        if os.path.exists(PID_FILE):
            try:
                os.remove(PID_FILE)
            except Exception:
                pass
        return 0

    _print(f"⏳ 正在关闭 PolyAI Chat (PID: {pid})...")
    if IS_WINDOWS:
        subprocess.call(["taskkill", "/PID", str(pid), "/F"],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                        creationflags=0x08000000)
    else:
        try:
            os.kill(pid, 15)
        except Exception:
            pass
        waited = 0
        while _pid_alive(pid) and waited < 5:
            time.sleep(1)
            waited += 1
        if _pid_alive(pid):
            try:
                os.kill(pid, 9)
            except Exception:
                pass

    if os.path.exists(PID_FILE):
        try:
            os.remove(PID_FILE)
        except Exception:
            pass
    _print("✅ PolyAI Chat 已关闭")
    return 0


def do_status():
    pid = is_running()
    if pid:
        _print(f"✅ PolyAI Chat 运行中 (PID: {pid})")
        _print(f"📎 访问: {URL}")
    else:
        _print("⭕ PolyAI Chat 未运行")
    return 0


def _tail(path, n):
    if not os.path.exists(path):
        return "ℹ️  暂无日志"
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
        return "".join(lines[-n:]) or "ℹ️  暂无日志"
    except Exception:
        return "ℹ️  暂无日志"


def do_log():
    _print(_tail(LOG_FILE, 50))
    return 0


def do_install():
    _print("🔧 PolyAI Chat 一键安装依赖")
    _print("==============================")
    if check_dependencies():
        _print()
        _print("✅ 所有依赖已就绪")
        return 0
    return 1


def main():
    cmd = (sys.argv[1].lower() if len(sys.argv) > 1 else "start")
    _print(f"[系统] {platform.system()} {platform.release()} | Python {platform.python_version()}")

    if cmd == "start":
        rc = do_start()
    elif cmd == "stop":
        rc = do_stop()
    elif cmd == "restart":
        do_stop()
        time.sleep(1)
        rc = do_start()
    elif cmd == "status":
        rc = do_status()
    elif cmd == "log":
        rc = do_log()
    elif cmd == "install":
        rc = do_install()
    else:
        _print("用法: python start.py {start|stop|restart|status|log|install}")
        _print()
        _print("  start    启动 PolyAI Chat（默认，可双击运行）")
        _print("  stop     关闭 PolyAI Chat")
        _print("  restart  重启 PolyAI Chat")
        _print("  status   查看运行状态")
        _print("  log      查看最近日志")
        _print("  install  检测并安装所有依赖")
        rc = 1

    if IS_WINDOWS and cmd in ("start", "install") and rc != 0:
        try:
            input("按回车键退出...")
        except Exception:
            pass
    sys.exit(rc)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        _print(f"❌ 未预期的错误: {e}")
        if IS_WINDOWS:
            try:
                input("按回车键退出...")
            except Exception:
                pass
        sys.exit(1)
