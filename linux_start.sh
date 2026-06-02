#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
WEB_DIR="$SCRIPT_DIR/web"
PID_FILE="$WEB_DIR/.polyai.pid"
LOG_FILE="$WEB_DIR/.polyai.log"
PORT=8080

REQUIRED_PY_PACKAGES=("flask" "requests")
OPTIONAL_PY_PACKAGES=("PyPDF2" "python-docx" "openpyxl")

check_dependencies() {
    local missing_sys=()
    local missing_py=()
    local missing_opt=()

    if ! command -v python3 &>/dev/null; then
        missing_sys+=("python3")
    fi

    if ! command -v pip3 &>/dev/null && ! python3 -m pip --version &>/dev/null 2>&1; then
        missing_sys+=("pip3 (python3-pip)")
    fi

    if [ ${#missing_sys[@]} -gt 0 ]; then
        echo "❌ 缺少系统依赖:"
        for pkg in "${missing_sys[@]}"; do
            echo "   • $pkg"
        done
        echo ""
        read -rp "是否一键安装? [Y/n] " answer
        answer=${answer:-Y}
        if [[ "$answer" =~ ^[Yy]$ ]]; then
            install_system_deps "${missing_sys[@]}"
        else
            echo "请手动安装后重试"
            exit 1
        fi
    fi

    for pkg in "${REQUIRED_PY_PACKAGES[@]}"; do
        if ! python3 -c "import $pkg" 2>/dev/null; then
            missing_py+=("$pkg")
        fi
    done

    for pkg in "${OPTIONAL_PY_PACKAGES[@]}"; do
        local import_name="$pkg"
        if [ "$pkg" = "python-docx" ]; then
            import_name="docx"
        fi
        if ! python3 -c "import $import_name" 2>/dev/null; then
            missing_opt+=("$pkg")
        fi
    done

    if [ ${#missing_py[@]} -gt 0 ]; then
        echo "❌ 缺少必要 Python 包:"
        for pkg in "${missing_py[@]}"; do
            echo "   • $pkg"
        done
        echo ""
        read -rp "是否一键安装? [Y/n] " answer
        answer=${answer:-Y}
        if [[ "$answer" =~ ^[Yy]$ ]]; then
            install_py_packages "${missing_py[@]}"
        else
            echo "请手动安装: pip3 install ${missing_py[*]}"
            exit 1
        fi
    fi

    if [ ${#missing_opt[@]} -gt 0 ]; then
        echo "⚠️  以下可选包未安装（文件解析功能需要）:"
        for pkg in "${missing_opt[@]}"; do
            echo "   • $pkg"
        done
        echo ""
        read -rp "是否安装可选包? [y/N] " answer
        answer=${answer:-N}
        if [[ "$answer" =~ ^[Yy]$ ]]; then
            install_py_packages "${missing_opt[@]}"
        fi
    fi
}

install_system_deps() {
    echo "⏳ 正在安装系统依赖..."
    if command -v apt-get &>/dev/null; then
        sudo apt-get update -qq && sudo apt-get install -y python3 python3-pip
    elif command -v dnf &>/dev/null; then
        sudo dnf install -y python3 python3-pip
    elif command -v yum &>/dev/null; then
        sudo yum install -y python3 python3-pip
    elif command -v pacman &>/dev/null; then
        sudo pacman -S --noconfirm python python-pip
    else
        echo "❌ 无法识别包管理器，请手动安装 python3 和 pip3"
        exit 1
    fi
    echo "✅ 系统依赖安装完成"
}

install_py_packages() {
    echo "⏳ 正在安装 Python 包: $*"
    python3 -m pip install --user "$@" || pip3 install --user "$@"
    if [ $? -eq 0 ]; then
        echo "✅ Python 包安装完成"
    else
        echo "❌ 安装失败，请手动执行: pip3 install $*"
        exit 1
    fi
}

is_running() {
    if [ -f "$PID_FILE" ]; then
        local pid
        pid=$(cat "$PID_FILE")
        if kill -0 "$pid" 2>/dev/null; then
            echo "$pid"
            return 0
        fi
        rm -f "$PID_FILE"
    fi
    return 1
}

do_start() {
    cd "$WEB_DIR" || { echo "❌ 找不到 web 目录: $WEB_DIR"; exit 1; }

    check_dependencies

    local existing
    existing=$(is_running)
    if [ -n "$existing" ]; then
        echo "⚠️  PolyAI Chat 已在运行 (PID: $existing)"
        echo "📎 访问: http://localhost:$PORT"
        echo "🛑 关闭: $0 stop"
        return 0
    fi

    local port_pid
    port_pid=$(lsof -ti:$PORT 2>/dev/null)
    if [ -n "$port_pid" ]; then
        echo "⚠️  端口 $PORT 被占用 (PID: $port_pid)，正在释放..."
        kill "$port_pid" 2>/dev/null
        sleep 1
        if lsof -ti:$PORT >/dev/null 2>&1; then
            kill -9 "$port_pid" 2>/dev/null
            sleep 0.5
        fi
    fi

    echo "" > "$LOG_FILE"
    nohup python3 app.py >> "$LOG_FILE" 2>&1 &
    local app_pid=$!
    echo "$app_pid" > "$PID_FILE"

    sleep 2

    if kill -0 "$app_pid" 2>/dev/null; then
        echo "✅ PolyAI Chat 已启动 (PID: $app_pid)"
        echo "📎 访问: http://localhost:$PORT"
        echo "📋 日志: $0 log"
        echo "🛑 关闭: $0 stop"
        xdg-open "http://localhost:$PORT" 2>/dev/null
    else
        rm -f "$PID_FILE"
        echo "❌ 启动失败，最近日志:"
        tail -20 "$LOG_FILE" 2>/dev/null
        exit 1
    fi
}

do_stop() {
    local pid
    pid=$(is_running)
    if [ -z "$pid" ]; then
        echo "ℹ️  PolyAI Chat 未在运行"
        rm -f "$PID_FILE"
        return 0
    fi

    echo "⏳ 正在关闭 PolyAI Chat (PID: $pid)..."
    kill "$pid" 2>/dev/null
    local waited=0
    while kill -0 "$pid" 2>/dev/null && [ $waited -lt 5 ]; do
        sleep 1
        waited=$((waited + 1))
    done

    if kill -0 "$pid" 2>/dev/null; then
        kill -9 "$pid" 2>/dev/null
        sleep 0.5
    fi

    rm -f "$PID_FILE"
    echo "✅ PolyAI Chat 已关闭"
}

do_status() {
    local pid
    pid=$(is_running)
    if [ -n "$pid" ]; then
        echo "✅ PolyAI Chat 运行中 (PID: $pid)"
        echo "📎 访问: http://localhost:$PORT"
    else
        echo "⭕ PolyAI Chat 未运行"
    fi
}

do_log() {
    if [ ! -f "$LOG_FILE" ]; then
        echo "ℹ️  暂无日志"
        return 0
    fi
    tail -50 "$LOG_FILE"
}

do_install() {
    echo "🔧 PolyAI Chat 一键安装依赖"
    echo "=============================="
    check_dependencies
    echo ""
    echo "✅ 所有依赖已就绪"
}

case "${1:-start}" in
    start)   do_start   ;;
    stop)    do_stop    ;;
    restart) do_stop; sleep 1; do_start ;;
    status)  do_status  ;;
    log)     do_log     ;;
    install) do_install ;;
    *)
        echo "用法: $0 {start|stop|restart|status|log|install}"
        echo ""
        echo "  start    启动 PolyAI Chat（默认）"
        echo "  stop     关闭 PolyAI Chat"
        echo "  restart  重启 PolyAI Chat"
        echo "  status   查看运行状态"
        echo "  log      查看最近日志"
        echo "  install  检测并安装所有依赖"
        exit 1
        ;;
esac
