import os
import json
import subprocess
import threading
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SERVERS_DIR = os.path.join(PROJECT_ROOT, "mcp", "servers")


class MCPServerConnection:
    def __init__(self, name, command, args=None, env=None):
        self.name = name
        self.command = command
        self.args = args or []
        self.env = env
        self.process = None
        self.tools = []
        self._request_id = 0
        self._lock = threading.Lock()

    def start(self):
        full_cmd = [self.command] + self.args
        env = os.environ.copy()
        if self.env:
            env.update(self.env)
        try:
            self.process = subprocess.Popen(
                full_cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                bufsize=0
            )
        except FileNotFoundError:
            raise RuntimeError(f"找不到命令 '{self.command}'")
        except Exception as e:
            raise RuntimeError(f"{e}")

        self._initialize()

    def _next_id(self):
        self._request_id += 1
        return self._request_id

    def _send_request(self, method, params=None):
        if not self.process or self.process.poll() is not None:
            raise RuntimeError(f"MCP Server '{self.name}' 未运行")

        request = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": method,
        }
        if params:
            request["params"] = params

        data = json.dumps(request) + "\n"
        with self._lock:
            try:
                self.process.stdin.write(data.encode("utf-8"))
                self.process.stdin.flush()
                line = self.process.stdout.readline()
                if not line:
                    stderr_out = self.process.stderr.read(1024).decode("utf-8", errors="replace")
                    raise RuntimeError(f"无响应. stderr: {stderr_out[:200]}")
                return json.loads(line.decode("utf-8"))
            except (BrokenPipeError, OSError) as e:
                raise RuntimeError(f"通信失败: {e}")

    def _initialize(self):
        resp = self._send_request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "deepseek-cli", "version": "1.0.0"}
        })
        if "error" in resp:
            raise RuntimeError(f"初始化失败: {resp['error']}")

        notify = {"jsonrpc": "2.0", "method": "notifications/initialized"}
        data = json.dumps(notify) + "\n"
        self.process.stdin.write(data.encode("utf-8"))
        self.process.stdin.flush()

    def list_tools(self):
        resp = self._send_request("tools/list")
        if "error" in resp:
            return []
        self.tools = resp.get("result", {}).get("tools", [])
        return self.tools

    def call_tool(self, tool_name, arguments):
        resp = self._send_request("tools/call", {
            "name": tool_name,
            "arguments": arguments
        })
        if "error" in resp:
            return f"[MCP错误] {resp['error'].get('message', '未知错误')}"
        result = resp.get("result", {})
        content_list = result.get("content", [])
        texts = []
        for item in content_list:
            if item.get("type") == "text":
                texts.append(item.get("text", ""))
            elif item.get("type") == "image":
                texts.append("[图片内容]")
            else:
                texts.append(str(item))
        return "\n".join(texts) if texts else "[MCP工具无返回]"

    def stop(self):
        if self.process and self.process.poll() is None:
            try:
                self.process.stdin.close()
                self.process.wait(timeout=5)
            except Exception:
                self.process.kill()


class MCPManager:
    def __init__(self):
        self.connections = {}
        self.tool_to_server = {}
        self.all_tools_definition = []
        self._ready = threading.Event()
        self._load_thread = None
        self._loaded_count = 0
        self._failed = []

    def load_servers(self, async_load=True):
        if async_load:
            self._load_thread = threading.Thread(target=self._do_load, daemon=True)
            self._load_thread.start()
        else:
            self._do_load()

    def _do_load(self):
        if not os.path.isdir(SERVERS_DIR):
            self._ready.set()
            return

        configs = []
        for filename in os.listdir(SERVERS_DIR):
            if not filename.endswith(".json"):
                continue
            filepath = os.path.join(SERVERS_DIR, filename)
            name = filename[:-5]
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    config = json.load(f)
                configs.append((name, config, filename))
            except Exception as e:
                self._failed.append((name, str(e)))

        threads = []
        for name, config, filename in configs:
            t = threading.Thread(target=self._load_one, args=(name, config, filename), daemon=True)
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        self._ready.set()

    def _load_one(self, name, config, filename):
        command = config.get("command", "")
        args = config.get("args", [])
        env = config.get("env")
        if not command:
            self._failed.append((name, "缺少 command 字段"))
            return

        try:
            conn = MCPServerConnection(name, command, args, env)
            conn.start()
            tools = conn.list_tools()

            with threading.Lock():
                self.connections[name] = conn
                for tool in tools:
                    tool_name = tool["name"]
                    self.tool_to_server[tool_name] = name
                    tool_def = {
                        "type": "function",
                        "function": {
                            "name": tool_name,
                            "description": tool.get("description", ""),
                            "parameters": tool.get("inputSchema", {"type": "object", "properties": {}})
                        }
                    }
                    self.all_tools_definition.append(tool_def)
                self._loaded_count += 1
        except Exception as e:
            self._failed.append((name, str(e)))

    def wait_ready(self, timeout=30):
        self._ready.wait(timeout=timeout)

    def is_ready(self):
        return self._ready.is_set()

    def get_status_line(self):
        if not self.is_ready():
            return "⏳ MCP 加载中..."
        if self._loaded_count == 0 and not self._failed:
            return ""
        parts = []
        if self._loaded_count > 0:
            tool_count = len(self.tool_to_server)
            parts.append(f"🔌 MCP: {tool_count} 个外部工具已加载（输入 /mcp 查看详情）")
        for name, err in self._failed:
            parts.append(f"  ❌ MCP '{name}' 失败: {err}")
        return "\n".join(parts)

    def get_tools_definition(self):
        return self.all_tools_definition

    def get_tool_names(self):
        return list(self.tool_to_server.keys())

    def is_mcp_tool(self, tool_name):
        return tool_name in self.tool_to_server

    def call_tool(self, tool_name, arguments):
        if not self._ready.is_set():
            self._ready.wait(timeout=30)
        server_name = self.tool_to_server.get(tool_name)
        if not server_name:
            return f"[MCP错误] 未找到工具: {tool_name}"
        conn = self.connections.get(server_name)
        if not conn:
            return f"[MCP错误] Server '{server_name}' 未连接"
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except json.JSONDecodeError:
                return f"[MCP错误] 参数解析失败"
        return conn.call_tool(tool_name, arguments)

    def shutdown(self):
        if self._load_thread and self._load_thread.is_alive():
            self._ready.wait(timeout=10)
        for conn in self.connections.values():
            conn.stop()
        self.connections.clear()
        self.tool_to_server.clear()
        self.all_tools_definition.clear()
        self._loaded_count = 0
        self._failed.clear()
        self._ready.clear()


_mcp_manager = None


def get_mcp_manager():
    global _mcp_manager
    if _mcp_manager is None:
        _mcp_manager = MCPManager()
    return _mcp_manager
