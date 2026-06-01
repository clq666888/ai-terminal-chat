#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
WEB_DIR="$SCRIPT_DIR/web"
PID_FILE="$WEB_DIR/.polyai.pid"
LOG_FILE="$WEB_DIR/.polyai.log"
PORT=8080

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

case "${1:-start}" in
    start)   do_start   ;;
    stop)    do_stop    ;;
    restart) do_stop; sleep 1; do_start ;;
    status)  do_status  ;;
    log)     do_log     ;;
    *)
        echo "用法: $0 {start|stop|restart|status|log}"
        echo ""
        echo "  start    启动 PolyAI Chat（默认）"
        echo "  stop     关闭 PolyAI Chat"
        echo "  restart  重启 PolyAI Chat"
        echo "  status   查看运行状态"
        echo "  log      查看最近日志"
        exit 1
        ;;
esac
