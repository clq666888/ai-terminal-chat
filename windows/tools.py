import os
import re
import json
import subprocess
import fnmatch

TOOLS_DEFINITION = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "读取指定文件的内容。支持文本文件、代码文件等。返回文件内容字符串。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "文件路径（相对于工作目录或绝对路径）"
                    },
                    "offset": {
                        "type": "integer",
                        "description": "从第几行开始读取（从1开始），默认1"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "最多读取多少行，默认200"
                    }
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "edit_file",
            "description": "编辑文件：写入内容（创建或覆盖）或删除文件/空目录。通过 action 参数指定操作类型。",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["write", "delete"],
                        "description": "操作类型：write 写入文件，delete 删除文件或空目录"
                    },
                    "path": {
                        "type": "string",
                        "description": "文件路径（相对于工作目录或绝对路径）"
                    },
                    "content": {
                        "type": "string",
                        "description": "写入的完整文件内容（仅 action=write 时需要）"
                    }
                },
                "required": ["action", "path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": "执行 shell 命令并返回输出。用于运行测试、安装依赖、git 操作、编译等。",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "要执行的 shell 命令"
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "超时秒数，默认30"
                    }
                },
                "required": ["command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_dir",
            "description": "列出目录下的文件和子目录。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "目录路径，默认为当前工作目录"
                    },
                    "recursive": {
                        "type": "boolean",
                        "description": "是否递归列出子目录，默认false"
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_files",
            "description": "在文件中搜索匹配的文本（类似 grep）。返回匹配的文件名和行内容。",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "搜索的文本或正则表达式"
                    },
                    "path": {
                        "type": "string",
                        "description": "搜索的目录路径，默认当前工作目录"
                    },
                    "file_pattern": {
                        "type": "string",
                        "description": "文件名过滤（glob），如 '*.py'"
                    }
                },
                "required": ["pattern"]
            }
        }
    }
]

DANGEROUS_COMMANDS = [
    "rm -rf /", "rm -rf /*", "mkfs", "dd if=", ":(){:|:&};:",
    "chmod -R 777 /", "shutdown", "reboot", "halt", "poweroff",
    "passwd", "useradd", "userdel", "groupadd", "groupdel",
    "systemctl", "service"
]


class ToolExecutor:
    def __init__(self, work_dir, auto_confirm=False):
        self.work_dir = os.path.abspath(work_dir)
        self.auto_confirm = auto_confirm

    def _resolve_path(self, path):
        if os.path.isabs(path):
            return path
        return os.path.join(self.work_dir, path)

    def _confirm(self, action_desc):
        if self.auto_confirm:
            return True
        try:
            answer = input(f"\n⚠️  {action_desc}\n   确认执行？(y/n): ").strip().lower()
            return answer in ("y", "yes")
        except (EOFError, KeyboardInterrupt):
            print("\n已取消")
            return False

    def execute(self, tool_name, arguments):
        try:
            args = json.loads(arguments) if isinstance(arguments, str) else arguments
        except json.JSONDecodeError as e:
            return f"[错误] 参数解析失败: {e}"

        handler = {
            "read_file": self._read_file,
            "edit_file": self._edit_file,
            "run_command": self._run_command,
            "list_dir": self._list_dir,
            "search_files": self._search_files,
        }.get(tool_name)

        if not handler:
            return f"[错误] 未知工具: {tool_name}"

        return handler(args)

    def _read_file(self, args):
        path = self._resolve_path(args["path"])
        offset = args.get("offset", 1)
        limit = args.get("limit", 200)
        if not os.path.exists(path):
            return f"[错误] 文件不存在: {path}"
        if not os.path.isfile(path):
            return f"[错误] 不是文件: {path}"
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
            total = len(lines)
            start = max(0, offset - 1)
            end = min(total, start + limit)
            selected = lines[start:end]
            result = ""
            for i, line in enumerate(selected, start=start + 1):
                result += f"{i:4d} | {line}"
            if end < total:
                result += f"\n... 共 {total} 行，已显示 {start+1}-{end} 行"
            return result
        except Exception as e:
            return f"[错误] 读取失败: {e}"

    def _edit_file(self, args):
        action = args.get("action", "write")
        path = self._resolve_path(args["path"])

        if action == "delete":
            return self._do_delete(path, args["path"])
        else:
            return self._do_write(path, args)

    def _do_write(self, path, args):
        content = args.get("content", "")
        exists = os.path.exists(path)
        action = "覆盖" if exists else "创建"
        line_count = content.count("\n") + 1

        if not self._confirm(f"{action}文件: {args['path']} ({line_count} 行)"):
            return "[已取消] 用户拒绝了写入操作"

        try:
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            return f"[成功] 已{action}文件: {args['path']}"
        except Exception as e:
            return f"[错误] 写入失败: {e}"

    def _do_delete(self, path, display_path):
        if not os.path.exists(path):
            return f"[错误] 路径不存在: {path}"

        if os.path.isfile(path):
            if not self._confirm(f"删除文件: {display_path}"):
                return "[已取消] 用户拒绝了删除操作"
            try:
                os.remove(path)
                return f"[成功] 已删除文件: {display_path}"
            except Exception as e:
                return f"[错误] 删除失败: {e}"
        elif os.path.isdir(path):
            if os.listdir(path):
                return f"[拒绝] 目录非空，不允许删除: {display_path}"
            if not self._confirm(f"删除空目录: {display_path}"):
                return "[已取消] 用户拒绝了删除操作"
            try:
                os.rmdir(path)
                return f"[成功] 已删除空目录: {display_path}"
            except Exception as e:
                return f"[错误] 删除失败: {e}"
        else:
            return f"[错误] 无法识别的路径类型: {path}"

    def _run_command(self, args):
        command = args["command"]
        timeout = args.get("timeout", 30)

        for dangerous in DANGEROUS_COMMANDS:
            if dangerous in command:
                return f"[拒绝] 危险命令被阻止: {command}"

        if not self._confirm(f"执行命令: {command}"):
            return "[已取消] 用户拒绝了命令执行"

        try:
            result = subprocess.run(
                command, shell=True, capture_output=True, text=True,
                timeout=timeout, cwd=self.work_dir
            )
            output = ""
            if result.stdout:
                output += result.stdout
            if result.stderr:
                output += "\n[stderr]\n" + result.stderr
            if result.returncode != 0:
                output += f"\n[退出码: {result.returncode}]"
            if not output.strip():
                output = "[命令执行成功，无输出]"
            if len(output) > 10000:
                output = output[:10000] + "\n... (输出已截断)"
            return output
        except subprocess.TimeoutExpired:
            return f"[错误] 命令超时 ({timeout}秒)"
        except Exception as e:
            return f"[错误] 执行失败: {e}"

    def _list_dir(self, args):
        path = self._resolve_path(args.get("path", "."))
        recursive = args.get("recursive", False)
        if not os.path.exists(path):
            return f"[错误] 目录不存在: {path}"
        if not os.path.isdir(path):
            return f"[错误] 不是目录: {path}"

        try:
            result_lines = []
            if recursive:
                for root, dirs, files in os.walk(path):
                    dirs[:] = [d for d in dirs if not d.startswith(".")]
                    rel = os.path.relpath(root, path)
                    level = 0 if rel == "." else rel.count(os.sep) + 1
                    if level > 4:
                        continue
                    indent = "  " * level
                    dirname = os.path.basename(root) + "/" if rel != "." else "./"
                    result_lines.append(f"{indent}{dirname}")
                    for f in sorted(files):
                        if f.startswith("."):
                            continue
                        result_lines.append(f"{indent}  {f}")
            else:
                entries = sorted(os.listdir(path))
                for entry in entries:
                    if entry.startswith("."):
                        continue
                    full = os.path.join(path, entry)
                    suffix = "/" if os.path.isdir(full) else ""
                    result_lines.append(f"  {entry}{suffix}")
            return "\n".join(result_lines) if result_lines else "[目录为空]"
        except Exception as e:
            return f"[错误] 列目录失败: {e}"

    def _search_files(self, args):
        pattern = args["pattern"]
        search_path = self._resolve_path(args.get("path", "."))
        file_pattern = args.get("file_pattern", "*")

        if not os.path.exists(search_path):
            return f"[错误] 路径不存在: {search_path}"

        try:
            regex = re.compile(pattern)
        except re.error:
            regex = re.compile(re.escape(pattern))

        matches = []
        for root, dirs, files in os.walk(search_path):
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            for fname in files:
                if fname.startswith("."):
                    continue
                if not fnmatch.fnmatch(fname, file_pattern):
                    continue
                fpath = os.path.join(root, fname)
                try:
                    with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                        for line_num, line in enumerate(f, 1):
                            if regex.search(line):
                                rel = os.path.relpath(fpath, search_path)
                                matches.append(f"{rel}:{line_num}: {line.rstrip()}")
                                if len(matches) >= 50:
                                    break
                except (OSError, UnicodeDecodeError):
                    continue
                if len(matches) >= 50:
                    break
            if len(matches) >= 50:
                break

        if not matches:
            return f"[无匹配] 在 {args.get('path', '.')} 中未找到 '{pattern}'"

        result = "\n".join(matches)
        if len(matches) >= 50:
            result += "\n... 结果已截断，仅显示前 50 条匹配"
        return result
