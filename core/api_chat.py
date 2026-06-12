#!/usr/bin/env python3
import sys
import os
import json
import requests
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

if sys.platform != "win32":
    import readline
else:
    os.system("chcp 65001 >nul 2>&1")
    def _win_ctrl_handler(ctrl_type):
        if ctrl_type == 0:
            try:
                sys.stdout.write('\n再见！\n')
                sys.stdout.flush()
            except Exception:
                pass
            os._exit(0)
        return False
    try:
        import ctypes
        _HandlerRoutine = ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_uint)
        _ctrl_cb = _HandlerRoutine(_win_ctrl_handler)
        ctypes.windll.kernel32.SetConsoleCtrlHandler(_ctrl_cb, True)
    except Exception:
        import signal
        signal.signal(signal.SIGINT, lambda *_: os._exit(0))

from .chat_core import (
    load_api_key, load_system_prompt, HistoryManager,
    send_chat_request, parse_stream_chunk, parse_stream_response
)
from .terminal_control import (
    TerminalManager, stream_output, start_abort_listener,
    stop_abort_listener, is_aborted,
    set_abort_callback, clear_abort_callback
)
from .spinner import Spinner
from .tools import TOOLS_DEFINITION, ToolExecutor
from .agent_manager import (
    list_agents, get_agent, get_global_agent,
    filter_tools, print_agent_list
)
from .config_manager import load_config, load_project_context, get_sessions_dir
from .mcp_client import get_mcp_manager

_cfg = load_config()

WORK_DIR = os.environ.get("POLYAI_USER_CWD", os.getcwd())
MAX_HISTORY_ROUNDS = _cfg["最大记忆轮数"]
MAX_TOOL_ROUNDS = _cfg["最大工具调用轮数"]
COMPRESS_THRESHOLD = _cfg["历史压缩阈值轮数"]
COMPRESS_KEEP_RECENT = _cfg["压缩保留最近轮数"]

TOOL_RULES = """

You have access to the following tools and can directly operate on the user's file system:
{tool_list}

Current working directory: {work_dir}

# Working Style
- When a request involves file operations, code changes, or running commands, actively use tools to complete it instead of only giving suggestions.
- Always read a file with read_file before modifying it.
- Prefer edit_file patch mode (action="patch") for existing files: provide only the exact original snippet and its replacement. old_content MUST match the file exactly, including indentation. Use write mode only for new files or full rewrites.
- When writing a new file, provide the complete content; never omit parts.
- When the user is just chatting or asking questions, answer directly without calling tools.

# Restraint (IMPORTANT)
- Do ONLY what the user asked. Do not add extra features, do not refactor unrelated code, do not "improve" things that work.
- Do not add defensive code for situations that cannot happen.
- Do not create documentation files (README, guides, etc.) unless the user explicitly asks.

# Honesty (IMPORTANT)
- NEVER claim something is "done", "tested", or "working" if you have not actually verified it. State clearly when something is unverified.
- For changes to executable code, proactively verify with run_command (syntax check or tests) when possible.
- If a tool returns an error, report it truthfully. Do not pretend it succeeded or fill gaps with guesses.

# Safety
- Be cautious with destructive operations (delete, overwrite, git push). When unsure, use ask_user to confirm.
- NEVER expose, log, or write API keys, passwords, or secrets.
- When you need to ask the user something, you MUST call ask_user. Never write a question in your reply text and wait — the user will not see it as a prompt.

# Tools
- When reading multiple files or gathering info from several places, call multiple read-only tools in parallel rather than one by one.
- Use get_diff to check your own past file changes; do not rely on memory.
- You ONLY have the tools listed above. You have no web access, no knowledge graph, and no long-term memory. Never claim capabilities you do not have.

# Language (CRITICAL)
- ALWAYS respond in the SAME language the user uses in their latest message.
- If the user writes in Chinese, you MUST think and respond entirely in Chinese.
- NEVER switch your response language because this prompt, tool outputs, file contents, or code comments are in English.
- This rule overrides everything else regarding language."""

if sys.platform == "win32":
    TOOL_RULES += "\n- The current environment is Windows; use Windows command syntax when running commands."

PARALLEL_SAFE_TOOLS = {"read_file", "list_dir", "search_files"}
_print_lock = threading.Lock()

TOOL_DESC_MAP = {
    "read_file": "读取文件内容",
    "edit_file": "编辑文件（写入/局部修改/删除）",
    "run_command": "执行命令" if sys.platform == "win32" else "执行 shell 命令",
    "list_dir": "列出目录结构",
    "search_files": "在文件中搜索文本",
    "call_agent": "调用其他智能体执行子任务",
    "ask_user": "向用户提问澄清需求",
    "get_diff": "查看文件改动记录",
}

TOOL_DISPLAY_MAP = {
    "read_file": "读取文件",
    "edit_file": "编辑文件",
    "run_command": "执行命令",
    "list_dir": "列出目录",
    "search_files": "搜索文件",
    "call_agent": "调用智能体",
    "ask_user": "用户提问",
    "get_diff": "查看改动",
}

global_agent = get_global_agent()
if not global_agent:
    print("❌ 缺少全局智能体配置，请先创建 agents/global.txt")
    print("   详见 agents/创建智能体须知.md")
    sys.exit(1)

if not global_agent["api_key"]:
    print("❌ 全局智能体缺少 API Key 配置")
    print("   请在 agents/global.txt 中填写 [API Key] 或 [API Key 文件]")
    sys.exit(1)

if not global_agent["api_url"]:
    print("❌ 全局智能体缺少 API 地址配置")
    print("   请在 agents/global.txt 中填写 [服务商] 或 [API地址]")
    sys.exit(1)

if not global_agent["model"]:
    print("❌ 全局智能体缺少模型配置")
    print("   请在 agents/global.txt 的 [模型] 中填写模型名称")
    sys.exit(1)

def get_ai_name():
    if current_agent:
        return f"@{current_agent['id']}"
    return f"@{global_agent['id']}"

tool_executor = ToolExecutor(WORK_DIR, config=_cfg)

mcp_mgr = get_mcp_manager()
mcp_mgr.load_servers()

ALL_TOOLS = TOOLS_DEFINITION + mcp_mgr.get_tools_definition()

current_agent = None
current_history = []
current_tools = ALL_TOOLS
current_model = global_agent["model"]
current_api_url = global_agent["api_url"]
current_api_key = global_agent["api_key"]
current_temperature = global_agent["temperature"] if global_agent["temperature"] is not None else 0.7
agent_histories = {}


def build_system_prompt(agent_config):
    base = agent_config["system_prompt"] if agent_config["system_prompt"] else ""

    perm = tool_executor.permission
    if perm == 0:
        prompt = base + f"\n\n当前权限等级: 0（仅聊天）\n你没有任何工具权限，不能读取文件、不能修改文件、不能执行命令。请直接与用户对话。\n如果用户要求你操作文件或执行命令，请告知用户当前权限不足，建议在 config.txt 中将权限调高后执行 /reload。\n工作目录: {WORK_DIR}"
        model_name = current_model if current_model else (agent_config.get("model") or global_agent.get("model", ""))
        display_model = model_name.split("/")[-1] if "/" in model_name else model_name
        prompt += f"\n\n[内部信息，仅在用户主动询问时使用] 当前模型: {display_model}"
        prompt += load_project_context(WORK_DIR)
        return prompt
    elif perm == 1:
        tool_names = [t["function"]["name"] for t in current_tools]
        tool_lines = "\n".join(f"- {name}: {TOOL_DESC_MAP.get(name, name)}" for name in tool_names)
        perm_note = "\n\n当前权限等级: 1（只读）\n你只能使用只读工具（read_file、list_dir、search_files、ask_user），不能修改文件或执行命令。\n如果用户要求修改操作，请告知用户当前权限不足，建议在 config.txt 中将权限调高后执行 /reload。"
        prompt = base + TOOL_RULES.format(tool_list=tool_lines, work_dir=WORK_DIR) + perm_note
    elif perm == 2:
        tool_names = [t["function"]["name"] for t in current_tools]
        tool_lines = "\n".join(f"- {name}: {TOOL_DESC_MAP.get(name, name)}" for name in tool_names)
        perm_note = "\n\n当前权限等级: 2（读写，需确认）\n你可以使用所有工具，但文件修改和命令执行会弹出确认提示，用户可能拒绝。"
        prompt = base + TOOL_RULES.format(tool_list=tool_lines, work_dir=WORK_DIR) + perm_note
    else:
        tool_names = [t["function"]["name"] for t in current_tools]
        tool_lines = "\n".join(f"- {name}: {TOOL_DESC_MAP.get(name, name)}" for name in tool_names)
        prompt = base + TOOL_RULES.format(tool_list=tool_lines, work_dir=WORK_DIR)

    callable_agents = [a for a in list_agents() if a.get("callable") and a["id"] != agent_config.get("id", "")]
    if callable_agents and "call_agent" in tool_names:
        agent_info = "\n\n可调用的智能体:\n"
        for a in callable_agents:
            desc = a.get("when_to_call", "") or a.get("system_prompt", "")[:50]
            agent_info += f"- @{a['id']} ({a['name']}): {desc}\n"
        prompt += agent_info

    model_name = current_model if current_model else (agent_config.get("model") or global_agent.get("model", ""))
    display_model = model_name.split("/")[-1] if "/" in model_name else model_name
    prompt += f"\n\n[内部信息，仅在用户主动询问时使用] 当前模型: {display_model}"

    prompt += load_project_context(WORK_DIR)
    return prompt



def _get_callable_agents():
    agents = list_agents()
    return [a for a in agents if a.get("callable") and a["id"] != (current_agent["id"] if current_agent else "global")]


def run_sub_agent(agent_id, message):
    agent_id = agent_id.lstrip("@")
    target = get_agent(agent_id)
    if not target:
        return f"[错误] 未找到智能体: @{agent_id}"
    if not target.get("callable"):
        return f"[错误] 智能体 @{agent_id} 未授权被调用"

    sub_model = target["model"] if target["model"] else global_agent["model"]
    sub_api_url = target["api_url"] if target["api_url"] else global_agent["api_url"]
    sub_api_key = target["api_key"] if target["api_key"] else global_agent["api_key"]
    sub_temp = target["temperature"] if target["temperature"] is not None else 0.7
    sub_tools_def = filter_tools(ALL_TOOLS, target["allowed_tools"])

    sub_tool_names = [t["function"]["name"] for t in sub_tools_def]
    sub_tool_lines = "\n".join(f"- {name}: {TOOL_DESC_MAP.get(name, name)}" for name in sub_tool_names)
    sub_system = (target["system_prompt"] or "") + TOOL_RULES.format(tool_list=sub_tool_lines, work_dir=WORK_DIR)
    SUB_AGENT_PROMPT = """

你当前是被主智能体通过 call_agent 工具调用的子智能体，负责完成主智能体分配的具体子任务。

【你的身份】
- 你不是直接面对最终用户的助手，而是主智能体的执行单元
- 主智能体通过 message 给你明确的任务指令，你只需完成该任务并返回结果
- 你的输出会被主智能体接收并整合，因此要简洁、准确、可直接使用

【语言要求 - 强制】
- 全程使用中文回复，包括思考过程、计划和总结，禁止输出英文句子或段落（代码中的变量名、函数名等标识符除外）

【超时约束】
- 每一轮思考+响应必须在 60 秒内产出内容，否则会被强制中断

【执行原则 - 极其重要】
1. 禁止在调用工具之前输出任何分析、计划、步骤说明或思考过程。你的第一个动作必须是工具调用（read_file、list_dir、edit_file 等），绝不能是文字输出
2. 收到任务后立即调用工具获取信息或执行操作，边做边用极短的文字说明（一句话以内），禁止动手前罗列步骤
3. 写代码时尽量一次写好主体；如果需要修改已有文件，优先用 patch 模式做局部修补，避免整体重写
4. 不编造文件内容、命令输出或 API 返回，一切信息必须来自工具调用的真实结果
5. 不要声称执行了未实际执行的操作
6. 如果任务描述有歧义或关键信息缺失，直接说明需要什么信息

【输出要求】
- 任务完成后直接输出结果，不要输出无关寒暄
- 如果任务是写代码，确保代码完整可运行
- 如果任务是分析/检查，给出明确结论和依据"""
    sub_system += SUB_AGENT_PROMPT

    sub_history = [
        {"role": "system", "content": sub_system},
        {"role": "user", "content": message}
    ]

    SUB_IDLE_TIMEOUT = 60
    sub_spinner = Spinner(f"@{agent_id} 工作中")
    sub_spinner.start()

    for round_num in range(MAX_TOOL_ROUNDS):
        if not sub_spinner._started:
            sub_spinner.message = f"@{agent_id} 工作中"
            sub_spinner.start()
        try:
            resp = send_chat_request(
                sub_api_url, sub_api_key, sub_history, sub_model,
                temperature=sub_temp, tools=sub_tools_def, stream=True,
                connect_timeout=_cfg["连接超时秒数"], read_timeout=_cfg["响应超时秒数"],
                max_tokens=16384
            )
        except Exception as e:
            sub_spinner.stop()
            return f"[错误] 子智能体请求失败: {e}"

        if resp.status_code != 200:
            sub_spinner.stop()
            try:
                err_text = resp.text[:200]
            except Exception:
                err_text = ""
            return f"[错误] 子智能体请求失败 [{resp.status_code}]: {err_text}"

        collected_content = ""
        tool_calls_map = {}
        finish_reason = None
        _last_data_time = time.time()
        timed_out = False
        _sub_header_printed = False
        _ssw_buf = ""
        _ssw_phase = "init"
        _ssw_path = None
        _ssw_file = None
        _ssw_lines = 0
        _ssw_written = 0
        _ssw_done = False
        _ssw_old_content = ""
        _ssw_idx = None
        _ssw_done_paths = {}

        sub_aborted = False

        def _sub_abort_check():
            from . import terminal_control as _tc
            if _tc.get_abort_flag():
                return True
            return (time.time() - _last_data_time) > SUB_IDLE_TIMEOUT

        try:
            from . import terminal_control as _tc
            for event in parse_stream_response(resp, abort_check=_sub_abort_check):
                if _tc.get_abort_flag():
                    sub_aborted = True
                    break
                _last_data_time = time.time()
                sub_spinner.reset_time()
                if event[0] == "content":
                    collected_content += event[1]
                elif event[0] == "tool_receiving":
                    tool_name = event[1]
                    args_delta = event[3] if len(event) > 3 else ""
                    tc_idx = event[4] if len(event) > 4 else 0
                    _is_write = tool_name in ("edit_file",)
                    if not _is_write:
                        if not sub_spinner._started and not _sub_header_printed:
                            sub_spinner.message = f"@{agent_id} 工作中"
                            sub_spinner.start()
                        continue
                    if _ssw_done:
                        if _ssw_idx is not None and tc_idx == _ssw_idx:
                            continue
                        _ssw_done = False
                        _ssw_buf = ""
                        _ssw_phase = "init"
                        _ssw_path = None
                        _ssw_lines = 0
                        _ssw_written = 0
                        _ssw_old_content = ""
                        _ssw_idx = tc_idx
                    if _ssw_idx is None:
                        _ssw_idx = tc_idx
                    if tc_idx != _ssw_idx:
                        continue
                    _ssw_buf += args_delta
                    if _ssw_phase in ("init", "scanning"):
                        if _ssw_phase == "init":
                            if '"action"' in _ssw_buf:
                                if '"patch"' in _ssw_buf or '"delete"' in _ssw_buf:
                                    _ssw_phase = "not_write"
                                    continue
                                elif '"write"' in _ssw_buf:
                                    _ssw_phase = "scanning"
                                else:
                                    continue
                            else:
                                continue
                        if _ssw_phase == "scanning":
                            if not _ssw_path:
                                for pm in ['"path": "', '"path":"']:
                                    pi = _ssw_buf.find(pm)
                                    if pi >= 0:
                                        pe = _ssw_buf.find('"', pi + len(pm))
                                        if pe >= 0:
                                            _ssw_path = _ssw_buf[pi + len(pm):pe]
                                            break
                            content_pos = -1
                            for cm in ['"content": "', '"content":"']:
                                ci = _ssw_buf.find(cm)
                                if ci >= 0:
                                    content_pos = ci + len(cm)
                                    break
                            if _ssw_path and content_pos >= 0:
                                _ssw_phase = "streaming"
                                _ssw_buf = _ssw_buf[content_pos:]
                                sub_spinner.stop()
                                if _sub_header_printed:
                                    sys.stdout.write("\n")
                                    _sub_header_printed = False
                                abs_path = os.path.join(WORK_DIR, _ssw_path) if not os.path.isabs(_ssw_path) else _ssw_path
                                parent_dir = os.path.dirname(abs_path) or "."
                                os.makedirs(parent_dir, exist_ok=True)
                                if os.path.isfile(abs_path):
                                    try:
                                        with open(abs_path, "r", encoding="utf-8", errors="replace") as _of:
                                            _ssw_old_content = _of.read()
                                    except Exception:
                                        pass
                                _ssw_file = open(abs_path, "w", encoding="utf-8")
                                sys.stdout.write(f"    ✏️  写入: {_ssw_path} ")
                                sys.stdout.flush()
                            else:
                                continue
                    if _ssw_phase == "not_write":
                        continue
                    if _ssw_phase == "streaming":
                        out = ""
                        i = 0
                        while i < len(_ssw_buf):
                            ch = _ssw_buf[i]
                            if ch == "\\":
                                if i + 1 < len(_ssw_buf):
                                    nch = _ssw_buf[i + 1]
                                    if nch == "n":
                                        out += "\n"
                                        i += 2
                                    elif nch == "t":
                                        out += "\t"
                                        i += 2
                                    elif nch == "r":
                                        out += "\r"
                                        i += 2
                                    elif nch == '"':
                                        out += '"'
                                        i += 2
                                    elif nch == "\\":
                                        out += "\\"
                                        i += 2
                                    elif nch == "/":
                                        out += "/"
                                        i += 2
                                    elif nch == "u" and i + 5 < len(_ssw_buf):
                                        hex_str = _ssw_buf[i+2:i+6]
                                        try:
                                            out += chr(int(hex_str, 16))
                                            i += 6
                                        except ValueError:
                                            out += "\\"
                                            out += nch
                                            i += 2
                                    elif nch == "u":
                                        break
                                    else:
                                        out += "\\"
                                        out += nch
                                        i += 2
                                else:
                                    break
                            elif ch == '"':
                                _ssw_phase = "closed"
                                _ssw_done = True
                                break
                            else:
                                out += ch
                                i += 1
                        _ssw_buf = _ssw_buf[i:]
                        if out:
                            _ssw_file.write(out)
                            _ssw_file.flush()
                            _ssw_lines += out.count("\n")
                            _ssw_written += len(out.encode("utf-8"))
                            sys.stdout.write(f"\r    ✏️  写入: {_ssw_path} ({_ssw_lines + 1} 行, {_ssw_written}B)")
                            sys.stdout.flush()
                        if _ssw_done:
                            _ssw_file.close()
                            _ssw_file = None
                            try:
                                with open(_ssw_path, "r", encoding="utf-8", errors="replace") as _fcnt:
                                    _real_lines = len(_fcnt.read().splitlines())
                                sys.stdout.write(f"\r    ✏️  写入: {_ssw_path} ({_real_lines} 行, {_ssw_written}B)\n")
                            except Exception:
                                sys.stdout.write("\n")
                            sys.stdout.flush()
                            if _ssw_idx is not None and _ssw_path:
                                _ssw_done_paths[_ssw_idx] = (_ssw_path, _ssw_old_content)
                elif event[0] == "tool_calls":
                    tool_calls = event[1]
                    collected_content = event[2] or collected_content
                    actual_fr = event[3] if len(event) > 3 else "tool_calls"
                    finish_reason = actual_fr if actual_fr else "tool_calls"
                    break
                elif event[0] == "done":
                    collected_content = event[1] or collected_content
                    finish_reason = "stop"
                    break
            else:
                if (time.time() - _last_data_time) > SUB_IDLE_TIMEOUT and finish_reason is None:
                    timed_out = True
        except Exception as e:
            err_str = str(e)
            if "timed out" in err_str.lower() or "timeout" in err_str.lower():
                timed_out = True
            else:
                if _ssw_file:
                    try:
                        _ssw_file.close()
                    except Exception:
                        pass
                sub_spinner.stop()
                return f"[错误] 子智能体流式响应异常: {e}"

        if sub_aborted:
            sub_spinner.stop()
            if _ssw_file:
                try:
                    _ssw_file.close()
                except Exception:
                    pass
                _ssw_file = None
                if _ssw_path:
                    _ssw_done_paths[_ssw_idx] = (_ssw_path, _ssw_old_content)
                    sys.stdout.write(f"\r    ✏️  写入: {_ssw_path} ({_ssw_lines + 1} 行, {_ssw_written}B) [已中断]\n")
                    sys.stdout.flush()
            for _di, (_dp, _dp_old) in _ssw_done_paths.items():
                abs_p = os.path.join(WORK_DIR, _dp) if not os.path.isabs(_dp) else _dp
                try:
                    with open(abs_p, "r", encoding="utf-8") as _rf:
                        _written = _rf.read()
                    _act = "覆盖" if _dp_old else "创建"
                    tool_executor._record_diff(_dp, _act, _dp_old, _written)
                except Exception:
                    pass
            if _sub_header_printed:
                sys.stdout.write("\n")
                sys.stdout.flush()
            try:
                resp.raw._fp.close()
            except Exception:
                pass
            try:
                resp.close()
            except Exception:
                pass
            return "[已中断] 用户中断了子智能体执行"

        if _sub_header_printed:
            sys.stdout.write("\n")
            sys.stdout.flush()

        if _ssw_file:
            try:
                _ssw_file.close()
            except Exception:
                pass
            _ssw_file = None
            if _ssw_idx is not None and _ssw_path and _ssw_idx not in _ssw_done_paths:
                _ssw_done_paths[_ssw_idx] = (_ssw_path, _ssw_old_content)
                sys.stdout.write(f"\r    ✏️  写入: {_ssw_path} ({_ssw_lines + 1} 行, {_ssw_written}B) [截断]\n")
                sys.stdout.flush()

        if timed_out:
            sub_spinner.stop()
            try:
                resp.close()
            except Exception:
                pass
            return f"[超时] @{agent_id} 超过 {SUB_IDLE_TIMEOUT}s 无响应，已中断"

        if finish_reason == "length":
            sub_spinner.stop()
            if _ssw_file:
                try:
                    _ssw_file.close()
                except Exception:
                    pass
                _ssw_file = None
                if _ssw_idx is not None and _ssw_path and _ssw_idx not in _ssw_done_paths:
                    _ssw_done_paths[_ssw_idx] = (_ssw_path, _ssw_old_content)
                    sys.stdout.write(f"\r    \u270f\ufe0f  \u5199\u5165: {_ssw_path} ({_ssw_lines + 1} \u884c, {_ssw_written}B) [\u622a\u65ad]\n")
                    sys.stdout.flush()
            sub_history.append({"role": "assistant", "content": collected_content or ""})
            sub_history.append({"role": "user", "content": "[系统提示] 你的上一次输出因 token 上限被截断。请勿重复已写入内容，直接从断点继续完成剩余工作。如果是文件写入，请使用 edit_file 的 patch 模式追加剩余内容。"})
            _ssw_buf = ""
            _ssw_phase = "init"
            _ssw_path = None
            _ssw_lines = 0
            _ssw_written = 0
            _ssw_old_content = ""
            _ssw_idx = None
            _ssw_done = False
            continue

        if finish_reason == "tool_calls":
            assistant_msg = {
                "role": "assistant",
                "content": collected_content or "",
                "tool_calls": tool_calls
            }
            sub_history.append(assistant_msg)

            sub_spinner.stop()
            for _tc_i, tc in enumerate(tool_calls):
                func_name = tc["function"]["name"]
                func_args = tc["function"]["arguments"]
                tc_id = tc["id"]
                _json_valid = True
                if isinstance(func_args, str):
                    try:
                        json.loads(func_args)
                    except (json.JSONDecodeError, ValueError):
                        _json_valid = False
                if not _json_valid:
                    result = f"[错误] 工具 {func_name} 的参数 JSON 不完整（可能因输出被截断），请重新生成完整调用"
                    sub_history.append({"role": "tool", "tool_call_id": tc_id, "content": result})
                    continue
                if func_name == "edit_file" and _tc_i in _ssw_done_paths:
                    _dp_path, _dp_old = _ssw_done_paths[_tc_i]
                    try:
                        _fa = json.loads(func_args) if isinstance(func_args, str) else func_args
                    except Exception:
                        _fa = {}
                    _fa_action = _fa.get("action", "write")
                    _fa_path = _fa.get("path", "")
                    if _fa_action == "write" and _fa_path == _dp_path:
                        abs_p = os.path.join(WORK_DIR, _fa_path) if not os.path.isabs(_fa_path) else _fa_path
                        try:
                            with open(abs_p, "r", encoding="utf-8") as _rf:
                                written_content = _rf.read()
                            _action_str = "覆盖" if _dp_old else "创建"
                            tool_executor._record_diff(_fa_path, _action_str, _dp_old, written_content)
                        except Exception:
                            pass
                        result = f"[成功] 已写入文件: {_fa_path}"
                    else:
                        print(f"    {format_tool_log(func_name, func_args).strip()}")
                        result = tool_executor.execute(func_name, func_args)
                elif func_name == "call_agent":
                    try:
                        _ca = json.loads(func_args) if isinstance(func_args, str) else func_args
                    except (json.JSONDecodeError, ValueError):
                        result = "[错误] call_agent 参数不完整（可能因输出截断）"
                        sub_history.append({"role": "tool", "tool_call_id": tc_id, "content": result})
                        continue
                    result = run_sub_agent(_ca.get("agent_id", ""), _ca.get("message", ""))
                elif mcp_mgr.is_mcp_tool(func_name):
                    result = mcp_mgr.call_tool(func_name, func_args)
                else:
                    print(f"    {format_tool_log(func_name, func_args).strip()}")
                    result = tool_executor.execute(func_name, func_args)
                sub_history.append({"role": "tool", "tool_call_id": tc_id, "content": result})
            _ssw_done = False
            _ssw_path = None
            _ssw_old_content = ""
            _ssw_buf = ""
            _ssw_phase = "init"
            _ssw_lines = 0
            _ssw_written = 0
            _ssw_idx = None
            _ssw_done_paths = {}
            sub_spinner.reset_time()
            continue

        sub_spinner.stop()
        return collected_content if collected_content else "[子智能体未返回内容]"

    sub_spinner.stop()
    return "[错误] 子智能体达到最大工具调用轮数"




def switch_agent(agent_id, silent=False):
    global current_agent, current_history, current_tools, current_model
    global current_api_url, current_api_key, current_temperature

    if agent_id is None or agent_id == "global":
        current_agent = global_agent
        current_history = agent_histories.setdefault("global", [])
        current_tools = filter_tools(TOOLS_DEFINITION, global_agent["allowed_tools"]) + mcp_mgr.get_tools_definition()
        current_model = global_agent["model"]
        current_api_url = global_agent["api_url"]
        current_api_key = global_agent["api_key"]
        current_temperature = global_agent["temperature"] if global_agent["temperature"] is not None else 0.7
    else:
        agent = get_agent(agent_id)
        if not agent:
            print(f"\n❌ 未找到智能体: @{agent_id}")
            return False
        current_agent = agent
        current_history = agent_histories.setdefault(agent_id, [])
        current_tools = filter_tools(TOOLS_DEFINITION, agent["allowed_tools"]) + mcp_mgr.get_tools_definition()
        current_model = agent["model"] if agent["model"] else global_agent["model"]
        current_api_url = agent["api_url"] if agent["api_url"] else global_agent["api_url"]
        current_api_key = agent["api_key"] if agent["api_key"] else global_agent["api_key"]
        if agent["temperature"] is not None:
            current_temperature = agent["temperature"]
        elif global_agent["temperature"] is not None:
            current_temperature = global_agent["temperature"]
        else:
            current_temperature = 0.7

    current_history.clear()
    system_content = build_system_prompt(current_agent)
    current_history.append({"role": "system", "content": system_content})

    if not silent:
        print(f"\n🔄 已切换到: @{current_agent['id']}")
    return True


def format_tool_log(func_name, func_args):
    try:
        args = json.loads(func_args) if isinstance(func_args, str) else func_args
    except Exception:
        args = {}

    if func_name == "read_file":
        path = args.get("path", "?")
        return f"  👓 读取: {path}"
    elif func_name == "edit_file":
        action = args.get("action", "write")
        path = args.get("path", "?")
        if action == "delete":
            return f"  🗑️  删除: {path}"
        elif action == "patch":
            old_content = args.get("old_content", "")
            new_content = args.get("new_content", "")
            old_lines = old_content.count("\n") + 1 if old_content else 0
            new_lines = new_content.count("\n") + 1 if new_content else 0
            return f"  🩹 局部修改: {path} ({old_lines} 行 -> {new_lines} 行)"
        else:
            content = args.get("content", "")
            lines = content.count("\n") + 1
            return f"  ✏️  写入: {path} ({lines} 行)"
    elif func_name == "run_command":
        cmd = args.get("command", "?")
        return f"  🔧 执行: {cmd}"
    elif func_name == "list_dir":
        path = args.get("path", ".")
        recursive = args.get("recursive", False)
        suffix = " (递归)" if recursive else ""
        return f"  📁 列目录: {path}{suffix}"
    elif func_name == "search_files":
        pattern = args.get("pattern", "?")
        path = args.get("path", ".")
        return f"  🔍 搜索: '{pattern}' @ {path}"
    elif func_name == "call_agent":
        agent_id = args.get("agent_id", "?")
        message = args.get("message", "?")
        short_msg = message[:50] + "..." if len(message) > 50 else message
        return f"  🤖 调用 @{agent_id}: {short_msg}"
    elif func_name == "ask_user":
        question = args.get("question", "?")
        return f"  ❓ 提问: {question}"
    elif func_name == "get_diff":
        path = args.get("path", "")
        if path:
            return f"  📄 查看改动: {path}"
        return f"  📄 查看改动记录"
    elif mcp_mgr.is_mcp_tool(func_name):
        return f"  🔌 MCP: {func_name}"
    else:
        return f"  🔧 {func_name}"


def chat(user_input):
    mgr = HistoryManager(current_history, MAX_HISTORY_ROUNDS, get_ai_name())
    global current_tools
    mcp_defs = mcp_mgr.get_tools_definition()
    if mcp_defs and not any(mcp_mgr.is_mcp_tool(t["function"]["name"]) for t in current_tools):
        current_tools = current_tools + mcp_defs

    perm = tool_executor.permission
    if perm == 0:
        effective_tools = None
    elif perm == 1:
        effective_tools = [t for t in current_tools if t["function"]["name"] in ("read_file", "list_dir", "search_files", "ask_user")]
    else:
        effective_tools = current_tools

    mgr.add_user_message(user_input)

    start_abort_listener()
    try:
        return _chat_loop(mgr, effective_tools)
    except KeyboardInterrupt:
        sys.stdout.write("\n\n🛑 已中断生成")
        sys.stdout.flush()
        mgr.add_interrupt_hint()
        return None
    finally:
        stop_abort_listener()


def _chat_loop(mgr, effective_tools):
    from .terminal_control import get_abort_flag as _get_abort_flag

    for round_num in range(MAX_TOOL_ROUNDS):
        from . import terminal_control as _tc
        if _tc.get_abort_flag():
            mgr.add_interrupt_hint()
            return None

        spinner = Spinner("AI 正在整理工具结果" if round_num > 0 else "AI 正在思考")
        spinner.start()
        try:
            resp = send_chat_request(
                current_api_url, current_api_key, current_history, current_model,
                temperature=current_temperature, tools=effective_tools, stream=True,
                connect_timeout=_cfg["连接超时秒数"], read_timeout=_cfg["响应超时秒数"],
                max_tokens=16384
            )
        except requests.RequestException as e:
            spinner.stop()
            print(f"\n❌ 网络请求异常: {e}")
            if round_num == 0:
                mgr.rollback_user_message()
            return None

        if resp.status_code != 200:
            spinner.stop()
            print(f"\n❌ 请求失败 [{resp.status_code}]: {resp.text}")
            if round_num == 0:
                mgr.rollback_user_message()
            return None

        from . import terminal_control as _tc
        if _tc.get_abort_flag():
            spinner.stop()
            resp.close()
            mgr.add_interrupt_hint()
            return None

        got_tool_calls = False
        final_text = ""
        aborted = False
        header_printed = False
        _tc_entered = False
        _sw_buf = ""
        _sw_phase = "init"
        _sw_path = None
        _sw_file = None
        _sw_lines = 0
        _sw_written = 0
        _sw_done = False
        _sw_old_content = ""
        _sw_idx = None
        _sw_done_paths = {}

        def _force_close_resp():
            try:
                resp.raw._fp.close()
            except Exception:
                pass
            try:
                resp.close()
            except Exception:
                pass
        set_abort_callback(_force_close_resp)
        from . import terminal_control as _tc
        for event in parse_stream_response(resp, abort_check=lambda: _tc.get_abort_flag()):
            if _tc.get_abort_flag():
                spinner.stop()
                aborted = True
                break

            if event[0] == "content":
                if _tc.get_abort_flag():
                    aborted = True
                    break
                if not header_printed:
                    spinner.stop()
                    sys.stdout.write(f"\n{get_ai_name()}: ")
                    sys.stdout.flush()
                    header_printed = True
                sys.stdout.write(event[1])
                sys.stdout.flush()
                final_text += event[1]

            elif event[0] == "tool_receiving":
                tool_name = event[1]
                args_len = event[2]
                args_delta = event[3] if len(event) > 3 else ""
                tc_idx = event[4] if len(event) > 4 else 0
                if not _tc_entered:
                    _tc_entered = True
                    if header_printed:
                        sys.stdout.write("\n")
                        sys.stdout.flush()
                _is_write_tool = tool_name in ("edit_file",)
                if not _is_write_tool:
                    if not spinner._started:
                        spinner.message = "AI 正在思考"
                        spinner.start()
                    continue
                if _sw_done:
                    if _sw_idx is not None and tc_idx == _sw_idx:
                        continue
                    _sw_done = False
                    _sw_buf = ""
                    _sw_phase = "init"
                    _sw_path = None
                    _sw_lines = 0
                    _sw_written = 0
                    _sw_old_content = ""
                    _sw_idx = tc_idx
                if _sw_idx is None:
                    _sw_idx = tc_idx
                if tc_idx != _sw_idx:
                    continue
                _sw_buf += args_delta
                if _sw_phase in ("init", "scanning"):
                    if _sw_phase == "init":
                        if '"action"' in _sw_buf:
                            if '"patch"' in _sw_buf or '"delete"' in _sw_buf:
                                _sw_phase = "not_write"
                                if not spinner._started:
                                    spinner.message = "AI 正在思考"
                                    spinner.start()
                                continue
                            elif '"write"' in _sw_buf:
                                _sw_phase = "scanning"
                            else:
                                if not spinner._started:
                                    spinner.message = "AI 正在思考"
                                    spinner.start()
                                continue
                        else:
                            if not spinner._started:
                                spinner.message = "AI 正在思考"
                                spinner.start()
                            continue
                    if _sw_phase == "scanning":
                        if not _sw_path:
                            for pm in ['"path": "', '"path":"']:
                                pi = _sw_buf.find(pm)
                                if pi >= 0:
                                    pe = _sw_buf.find('"', pi + len(pm))
                                    if pe >= 0:
                                        _sw_path = _sw_buf[pi + len(pm):pe]
                                        break
                        content_pos = -1
                        for cm in ['"content": "', '"content":"']:
                            ci = _sw_buf.find(cm)
                            if ci >= 0:
                                content_pos = ci + len(cm)
                                break
                        if _sw_path and content_pos >= 0:
                            _sw_phase = "streaming"
                            _sw_buf = _sw_buf[content_pos:]
                            if spinner._started:
                                spinner.stop()
                            abs_path = os.path.join(WORK_DIR, _sw_path) if not os.path.isabs(_sw_path) else _sw_path
                            parent_dir = os.path.dirname(abs_path) or "."
                            os.makedirs(parent_dir, exist_ok=True)
                            if os.path.isfile(abs_path):
                                try:
                                    with open(abs_path, "r", encoding="utf-8", errors="replace") as _of:
                                        _sw_old_content = _of.read()
                                except Exception:
                                    pass
                            _sw_file = open(abs_path, "w", encoding="utf-8")
                            sys.stdout.write(f"  ✏️  写入: {_sw_path} ")
                            sys.stdout.flush()
                        else:
                            if not spinner._started:
                                spinner.message = "AI 正在思考"
                                spinner.start()
                            continue
                if _sw_phase == "not_write":
                    if not spinner._started:
                        spinner.message = "AI 正在思考"
                        spinner.start()
                    continue
                if _sw_phase == "streaming":
                    out = ""
                    i = 0
                    while i < len(_sw_buf):
                        ch = _sw_buf[i]
                        if ch == "\\":
                            if i + 1 < len(_sw_buf):
                                nch = _sw_buf[i + 1]
                                if nch == "n":
                                    out += "\n"
                                    i += 2
                                elif nch == "t":
                                    out += "\t"
                                    i += 2
                                elif nch == "r":
                                    out += "\r"
                                    i += 2
                                elif nch == '"':
                                    out += '"'
                                    i += 2
                                elif nch == "\\":
                                    out += "\\"
                                    i += 2
                                elif nch == "/":
                                    out += "/"
                                    i += 2
                                elif nch == "u" and i + 5 < len(_sw_buf):
                                    hex_str = _sw_buf[i+2:i+6]
                                    try:
                                        out += chr(int(hex_str, 16))
                                        i += 6
                                    except ValueError:
                                        out += "\\"
                                        out += nch
                                        i += 2
                                elif nch == "u":
                                    break
                                else:
                                    out += "\\"
                                    out += nch
                                    i += 2
                            else:
                                break
                        elif ch == '"':
                            _sw_phase = "closed"
                            _sw_done = True
                            break
                        else:
                            out += ch
                            i += 1
                    _sw_buf = _sw_buf[i:]
                    if out:
                        _sw_file.write(out)
                        _sw_file.flush()
                        _sw_lines += out.count("\n")
                        _sw_written += len(out.encode("utf-8"))
                        sys.stdout.write(f"\r  ✏️  写入: {_sw_path} ({_sw_lines + 1} 行, {_sw_written}B)")
                        sys.stdout.flush()
                    if _sw_done:
                        _sw_file.close()
                        _sw_file = None
                        sys.stdout.write("\n")
                        sys.stdout.flush()
                        if _sw_idx is not None and _sw_path:
                            _sw_done_paths[_sw_idx] = (_sw_path, _sw_old_content)

            elif event[0] == "tool_calls":
                if _tc.get_abort_flag():
                    aborted = True
                    break
                spinner.stop()
                got_tool_calls = True
                tool_calls = event[1]
                tc_content = event[2]
                tc_finish_reason = event[3] if len(event) > 3 else "tool_calls"
                break

            elif event[0] == "done":
                spinner.stop()
                final_text = event[1]
                break

        clear_abort_callback()

        if not aborted and _tc.get_abort_flag():
            aborted = True

        if aborted:
            if _sw_file:
                try:
                    _sw_file.close()
                except Exception:
                    pass
                _sw_file = None
                if _sw_path:
                    _sw_done_paths[_sw_idx] = (_sw_path, _sw_old_content)
                    sys.stdout.write(f" [中断]\n")
                    sys.stdout.flush()
            for _di, (_dp, _dp_old) in _sw_done_paths.items():
                abs_p = os.path.join(WORK_DIR, _dp) if not os.path.isabs(_dp) else _dp
                try:
                    with open(abs_p, "r", encoding="utf-8") as _rf:
                        _written = _rf.read()
                    _act = "覆盖" if _dp_old else "创建"
                    tool_executor._record_diff(_dp, _act, _dp_old, _written)
                except Exception:
                    pass
            try:
                resp.close()
            except Exception:
                pass
            if header_printed:
                sys.stdout.write("\n")
            if final_text:
                mgr.save_assistant_reply(final_text + "\n[此处被用户中断]")
            mgr.add_interrupt_hint()
            return None

        if _sw_file:
            try:
                _sw_file.close()
            except Exception:
                pass
            _sw_file = None
            if _sw_idx is not None and _sw_path and _sw_idx not in _sw_done_paths:
                _sw_done_paths[_sw_idx] = (_sw_path, _sw_old_content)
                sys.stdout.write(f"\r  ✏️  写入: {_sw_path} ({_sw_lines + 1} 行, {_sw_written}B) [截断]\n")
                sys.stdout.flush()

        if got_tool_calls and tc_finish_reason == "length":
            sys.stdout.write("  ⚠️  输出被截断（token上限），自动续写中...\n")
            sys.stdout.flush()
            _done_info = []
            for _di, (_dp, _) in _sw_done_paths.items():
                _done_info.append(_dp)
            mgr.save_assistant_reply(tc_content or "")
            _hint = "[系统提示] 你的上一次输出因 token 上限被截断，工具调用参数不完整。请勿重复已完成的操作，直接从断点继续完成剩余工作。如果是文件写入，请使用 edit_file 重新生成完整的工具调用。"
            if _done_info:
                _hint += f" 以下文件已通过流式写入完成，不要再写：{', '.join(_done_info)}"
            mgr.history.append({"role": "user", "content": _hint})
            continue

        if not got_tool_calls:
            if header_printed:
                sys.stdout.write("\n")
            if final_text:
                mgr.save_assistant_reply(final_text)
                if COMPRESS_THRESHOLD > 0 and mgr.needs_compression(COMPRESS_THRESHOLD):
                    _do_compress(mgr, silent=False)
            return final_text

        if tc_content and not header_printed:
            print(f"\n{get_ai_name()}: {tc_content}")
        elif not header_printed and not _tc_entered:
            print(f"\n{get_ai_name()}: [执行操作]")

        assistant_msg = {
            "role": "assistant",
            "content": tc_content or "",
            "tool_calls": tool_calls
        }
        mgr.save_tool_call_message(assistant_msg)


        can_parallel = (
            len(tool_calls) > 1
            and all(tc["function"]["name"] in PARALLEL_SAFE_TOOLS for tc in tool_calls)
        )

        _fold_types = set()
        if len(tool_calls) > 2:
            _type_count = {}
            for _t in tool_calls:
                _tn = _t["function"]["name"]
                _type_count[_tn] = _type_count.get(_tn, 0) + 1
            for _tn, _cnt in _type_count.items():
                if _cnt > 2:
                    _fold_types.add(_tn)
            print("  🔧 调用工具中")

        if can_parallel:
            results_map = {}

            def _run_parallel(tc):
                fn = tc["function"]["name"]
                fa = tc["function"]["arguments"]
                tid = tc["id"]
                if fn not in _fold_types:
                    with _print_lock:
                        print(format_tool_log(fn, fa))
                res = tool_executor.execute(fn, fa)
                return tid, res

            with ThreadPoolExecutor(max_workers=min(len(tool_calls), 8)) as pool:
                futures = {pool.submit(_run_parallel, tc): tc for tc in tool_calls}
                for future in as_completed(futures):
                    from . import terminal_control as _tc
                    if _tc.get_abort_flag():
                        print("\n\n🛑 已中断工具执行")
                        mgr.add_interrupt_hint()
                        return None
                    tid, res = future.result()
                    results_map[tid] = res

            for tc in tool_calls:
                mgr.save_tool_result(tc["id"], results_map[tc["id"]])
        else:
            for _tc_i, tc in enumerate(tool_calls):
                from . import terminal_control as _tc
                if _tc.get_abort_flag():
                    print("\n\n🛑 已中断工具执行")
                    mgr.add_interrupt_hint()
                    return None

                func_name = tc["function"]["name"]
                func_args = tc["function"]["arguments"]
                tc_id = tc["id"]

                _json_valid = True
                if isinstance(func_args, str):
                    try:
                        json.loads(func_args)
                    except (json.JSONDecodeError, ValueError):
                        _json_valid = False
                if not _json_valid:
                    result = f"[错误] 工具 {func_name} 的参数 JSON 不完整（可能因输出被截断），请重新生成完整调用"
                    mgr.save_tool_result(tc_id, result)
                    continue

                if func_name == "edit_file" and _tc_i in _sw_done_paths:
                    _dp_path, _dp_old = _sw_done_paths[_tc_i]
                    try:
                        _fa = json.loads(func_args) if isinstance(func_args, str) else func_args
                    except Exception:
                        _fa = {}
                    _fa_action = _fa.get("action", "write")
                    _fa_path = _fa.get("path", "")
                    if _fa_action == "write" and _fa_path == _dp_path:
                        abs_p = os.path.join(WORK_DIR, _fa_path) if not os.path.isabs(_fa_path) else _fa_path
                        try:
                            with open(abs_p, "r", encoding="utf-8") as _rf:
                                written_content = _rf.read()
                            _action = "覆盖" if _dp_old else "创建"
                            tool_executor._record_diff(_fa_path, _action, _dp_old, written_content)
                        except Exception:
                            pass
                        result = f"[成功] 已写入文件: {_fa_path}"
                    else:
                        if func_name not in _fold_types:
                            print(format_tool_log(func_name, func_args))
                        result = tool_executor.execute(func_name, func_args)
                elif func_name == "call_agent":
                    print(format_tool_log(func_name, func_args))
                    try:
                        _args = json.loads(func_args) if isinstance(func_args, str) else func_args
                    except (json.JSONDecodeError, ValueError):
                        result = "[错误] call_agent 参数不完整（可能因输出截断）"
                        mgr.save_tool_result(tc_id, result)
                        continue
                    _agent_id = _args.get("agent_id", "")
                    result = run_sub_agent(_agent_id, _args.get("message", ""))
                    if result.startswith("[错误]"):
                        print(f"  🤖 @{_agent_id} 调用失败: {result}")
                    else:
                        print(f"  🤖 @{_agent_id}:")
                        print(f"  {result}")
                elif mcp_mgr.is_mcp_tool(func_name):
                    if func_name not in _fold_types:
                        print(format_tool_log(func_name, func_args))
                    result = mcp_mgr.call_tool(func_name, func_args)
                else:
                    if func_name not in _fold_types:
                        print(format_tool_log(func_name, func_args))
                    result = tool_executor.execute(func_name, func_args)
                mgr.save_tool_result(tc_id, result)

                if _tc.get_abort_flag():
                    mgr.add_interrupt_hint()
                    return None
        continue

    print("\n⚠️ 达到最大工具调用轮数，停止执行")
    return None

def _save_session(name=None):
    from datetime import datetime
    sessions_dir = get_sessions_dir()
    if not name:
        name = "autosave"
    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)
    filepath = os.path.join(sessions_dir, f"{safe_name}.json")
    agent_id = current_agent["id"] if current_agent else "global"
    data = {
        "agent_id": agent_id,
        "model": current_model,
        "history": current_history,
        "diff_records": tool_executor.diff_records,
        "current_round": tool_executor.current_round,
        "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return safe_name, filepath
    except Exception as e:
        return None, str(e)


def _load_session(name):
    sessions_dir = get_sessions_dir()
    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)
    filepath = os.path.join(sessions_dir, f"{safe_name}.json")
    if not os.path.isfile(filepath):
        return None, f"会话文件不存在: {safe_name}"
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data, None
    except Exception as e:
        return None, str(e)


def _list_sessions():
    sessions_dir = get_sessions_dir()
    files = []
    for fname in os.listdir(sessions_dir):
        if fname.endswith(".json"):
            fpath = os.path.join(sessions_dir, fname)
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                name = fname[:-5]
                saved_at = data.get("saved_at", "未知")
                agent_id = data.get("agent_id", "?")
                rounds = sum(1 for m in data.get("history", []) if m.get("role") == "user")
                files.append((name, saved_at, agent_id, rounds))
            except Exception:
                files.append((fname[:-5], "读取失败", "?", 0))
    files.sort(key=lambda x: x[1], reverse=True)
    return files


def _do_compress(mgr, silent=False):
    if not silent:
        print("\n📦 正在压缩历史记忆...")
    success, result = mgr.compress_history(
        current_api_url, current_api_key, current_model,
        keep_recent=COMPRESS_KEEP_RECENT,
        connect_timeout=_cfg["连接超时秒数"],
        read_timeout=_cfg["响应超时秒数"]
    )
    if success:
        rounds = mgr.count_rounds()
        if not silent:
            print(f"✅ 压缩完成，保留最近 {COMPRESS_KEEP_RECENT} 轮对话，摘要已注入上下文")
            print(f"   当前记忆轮数: {rounds}\n")
    else:
        if not silent:
            print(f"⚠️ 压缩未执行: {result}\n")


def main():
    global MAX_HISTORY_ROUNDS, MAX_TOOL_ROUNDS, COMPRESS_THRESHOLD, COMPRESS_KEEP_RECENT, ALL_TOOLS
    switch_agent(None, silent=True)

    agents = list_agents()
    other_agents = [a for a in agents if a["id"] != "global"]

    print(f"\n🤖 工具作者: clq")
    perm_desc = {0: "0 (仅聊天)", 1: "1 (只读)", 2: "2 (读写，需确认)", 3: "3 (完全自动)"}
    print(f"📂 工作目录: {WORK_DIR}")
    print(f"🔒 权限等级: {perm_desc.get(tool_executor.permission, str(tool_executor.permission))}")
    if other_agents:
        ids = ", ".join(f"@{a['id']}" for a in other_agents)
        print(f"🧩 可用智能体: {ids}")
    mcp_status = mcp_mgr.get_status_line()
    if mcp_status:
        print(mcp_status)
    print("─" * 50)
    print("输入 /list 获取指令列表\n")

    if len(sys.argv) > 1:
        user_input = " ".join(sys.argv[1:])
        print(f"你: {user_input}")
        tool_executor.next_round()
        chat(user_input)
        mcp_mgr.shutdown()
        return

    _interrupt_pending = False
    while True:
        try:
            agent_tag = f"@{current_agent['id']}" if current_agent and current_agent["id"] != "global" else ""
            round_num = tool_executor.current_round + 1
            user_text = input(f"[{round_num}] 你{agent_tag}: ").strip()
        except KeyboardInterrupt:
            if _interrupt_pending:
                if current_history:
                    _save_session("autosave")
                print("\n对话结束")
                break
            _interrupt_pending = True
            print("\n（再按一次 Ctrl+C 退出）")
            continue
        except EOFError:
            print("\n再见！")
            break

        _interrupt_pending = False


        if user_text == '"""' or user_text.startswith('"""'):
            first_line = user_text[3:]
            collected = [first_line] if first_line else []
            print('  ... (多行模式，输入 \"\"\" 结束)')
            while True:
                try:
                    ml = input("  ... ")
                except (EOFError, KeyboardInterrupt):
                    print("\n已取消多行输入")
                    collected = []
                    break
                if ml.rstrip() == '"""':
                    break
                collected.append(ml)
            if not collected:
                continue
            user_text = "\n".join(collected).strip()
            if not user_text:
                continue

        if user_text.lower() == "/exit":
            if current_history:
                _save_session("autosave")
            print("对话结束")
            break

        if user_text.lower() == "/clear":
            switch_agent(current_agent["id"] if current_agent else None, silent=True)
            print("📝 记忆已清空\n")
            continue



        if user_text.lower().startswith("/undo"):
            undo_arg = user_text[5:].strip()
            if not undo_arg:
                target_round = tool_executor.current_round - 1
            else:
                try:
                    target_round = int(undo_arg)
                    if target_round < 0:
                        print("⚠️ 请输入非负整数\n")
                        continue
                except ValueError:
                    print("⚠️ 格式错误，用法: /undo 或 /undo N（回退到第N轮）\n")
                    continue

            if target_round >= tool_executor.current_round:
                print(f"⚠️ 当前已在第 {tool_executor.current_round} 轮，无法回退到第 {target_round} 轮\n")
                continue

            if len(current_history) <= 1:
                print("⚠️ 没有可撤销的对话\n")
                continue

            rounds_to_undo = tool_executor.current_round - target_round
            file_preview = tool_executor.get_undo_preview_to(target_round)
            history_rounds = 0
            tmp_hist = list(current_history)
            for _ in range(rounds_to_undo):
                if len(tmp_hist) <= 1:
                    break
                removed_one = False
                while len(tmp_hist) > 1:
                    last = tmp_hist[-1]
                    if last["role"] == "user" and removed_one:
                        tmp_hist.pop()
                        break
                    tmp_hist.pop()
                    removed_one = True
                history_rounds += 1

            print(f"\n\033[31m⚠️  警告：此操作不可撤回！\033[0m")
            print(f"  将回退到第 {target_round} 轮（撤回第 {target_round + 1}~{tool_executor.current_round} 轮）")
            if file_preview:
                print(f"  并恢复以下 {len(file_preview)} 个文件:")
                for fp, desc in file_preview:
                    print(f"    - {fp} ({desc})")
            else:
                print(f"  （无文件改动需要恢复）")
            try:
                confirm = input("\n  确认执行？(y/n): ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                print("\n已取消")
                continue
            if confirm not in ("y", "yes"):
                print("已取消\n")
                continue

            restored = tool_executor.undo_to_round(target_round)

            removed_msgs = 0
            for _ in range(rounds_to_undo):
                if len(current_history) <= 1:
                    break
                removed_one = False
                while len(current_history) > 1:
                    last = current_history[-1]
                    if last["role"] == "user" and removed_one:
                        current_history.pop()
                        removed_msgs += 1
                        break
                    current_history.pop()
                    removed_msgs += 1
                    removed_one = True

            print(f"\n↩️  已回退到第 {target_round} 轮（撤回 {history_rounds} 轮对话，移除 {removed_msgs} 条消息）")
            if restored:
                for fp, status in restored:
                    print(f"  📄 {fp} → {status}")
            print()
            continue

        if user_text.lower() == "/compress":
            mgr = HistoryManager(current_history, MAX_HISTORY_ROUNDS, get_ai_name())
            rounds = mgr.count_rounds()
            if rounds <= COMPRESS_KEEP_RECENT:
                print(f"⚠️ 当前仅 {rounds} 轮对话，无需压缩\n")
                continue
            _do_compress(mgr, silent=False)
            continue

        if user_text.lower() == "/list":
            print("\n📋 可用指令:")
            print("  /exit     - 退出程序")
            print("  /clear    - 清空当前对话记忆")
            print("  /undo [N]  - 回退到第 N 轮（默认回退1轮）")
            print("  /compress - 压缩历史记忆（减少 token 占用）")
            print("  /config   - 打开配置面板（键盘导航）")
            print("  /reload   - 重新加载配置和智能体")
            print("  /agents   - 查看所有智能体列表")
            print("  /diff       - 查看 AI 的文件改动记录")
            print("  /mcp      - 查看已加载的 MCP 工具")
            print("  /save [名] - 保存当前会话")
            print("  /load <名> - 恢复已保存的会话")
            print("  /sessions - 查看所有已保存会话")
            print("  /list     - 显示本指令列表")
            print()
            print("📋 特殊输入:")
            print("  @名称     - 切换到指定智能体")
            print("  @名称 内容 - 切换并直接对话")
            print('  \"\"\"       - 进入多行输入模式')
            print("  Ctrl+C    - 中断 AI 生成或工具执行")
            print()
            print("  📖 详细说明见项目根目录 指令操作指南.md")
            print()
            continue

        if user_text.lower().startswith("/diff"):
            arg = user_text[5:].strip()
            records = tool_executor.get_diff_records()
            cur = tool_executor.current_round

            def _group_records(records, cur):
                groups = []
                current_round_val = None
                current_group = []
                for r in records:
                    if r["round"] != current_round_val:
                        if current_group:
                            groups.append(current_group)
                        current_group = [r]
                        current_round_val = r["round"]
                    else:
                        current_group.append(r)
                if current_group:
                    groups.append(current_group)
                return groups

            def _build_display_list(groups, cur):
                display = []
                for grp in groups:
                    when = f"第{grp[0]['round']}轮对话"
                    if len(grp) <= 3:
                        for r in grp:
                            act_map = {"创建": "创建", "覆盖": "修改", "删除": "删除"}
                            act = act_map.get(r["action"], r["action"])
                            display.append({"type": "single", "record": r, "when": when, "act": act})
                    else:
                        display.append({"type": "group", "records": grp, "when": when, "count": len(grp), "time": grp[0]["time"]})
                return display

            def _show_detail(r, cur):
                when = f"第{r['round']}轮对话"
                act_map = {"创建": "创建", "覆盖": "修改", "删除": "删除"}
                act = act_map.get(r["action"], r["action"])
                print(f"\n📄 [{r['time']}] 于{when}中{act} {r['path']}")
                print("─" * 50)
                detail_record = {"old": r["old"], "new": r["new"], "action": r["action"]}
                diff_text = tool_executor._format_diff(detail_record)
                if diff_text:
                    print(diff_text)
                else:
                    print("（无差异）")
                print("─" * 50)
                print("  \033[31m- 删除/旧\033[0m  \033[32m+ 新增/新\033[0m")
                print()

            if not arg:
                if not records:
                    print("\n📄 暂无文件改动记录\n")
                else:
                    groups = _group_records(records, cur)
                    groups.reverse()
                    display = _build_display_list(groups, cur)
                    print(f"\n📄 文件改动记录（共 {len(records)} 条，{len(display)} 项）:")
                    for i, item in enumerate(display, 1):
                        if item["type"] == "single":
                            r = item["record"]
                            print(f"  {i}. [{r['time']}] 于{item['when']}中{item['act']} {r['path']}")
                        else:
                            print(f"  {i}. [{item['time']}] 于{item['when']}中改动 {item['count']} 个文件")
                    print(f"\n  /diff N      查看第 N 项详情（折叠项会展开）")
                    print(f"  /diff N.M    查看折叠项中第 M 条的详细 diff")
                    print(f"  /diff 路径   查看指定文件的改动历史\n")
            elif "." in arg and arg.replace(".", "").isdigit():
                parts_dot = arg.split(".", 1)
                try:
                    main_idx = int(parts_dot[0])
                    sub_idx = int(parts_dot[1])
                except ValueError:
                    print("⚠️ 格式错误，请使用 /diff N.M\n")
                    continue
                if not records:
                    print("\n📄 暂无文件改动记录\n")
                    continue
                groups = _group_records(records, cur)
                groups.reverse()
                display = _build_display_list(groups, cur)
                if main_idx < 1 or main_idx > len(display):
                    print(f"⚠️ 序号超出范围（当前共 {len(display)} 项）\n")
                    continue
                item = display[main_idx - 1]
                if item["type"] == "single":
                    print(f"⚠️ 第 {main_idx} 项为单条记录，请直接使用 /diff {main_idx}\n")
                    continue
                grp_records = item["records"]
                if sub_idx < 1 or sub_idx > len(grp_records):
                    print(f"⚠️ 子序号超出范围（该组共 {len(grp_records)} 条）\n")
                    continue
                _show_detail(grp_records[sub_idx - 1], cur)
            else:
                try:
                    idx = int(arg)
                    if not records:
                        print("\n📄 暂无文件改动记录\n")
                        continue
                    groups = _group_records(records, cur)
                    groups.reverse()
                    display = _build_display_list(groups, cur)
                    if idx < 1 or idx > len(display):
                        print(f"⚠️ 序号超出范围（当前共 {len(display)} 项）\n")
                        continue
                    item = display[idx - 1]
                    if item["type"] == "single":
                        _show_detail(item["record"], cur)
                    else:
                        grp_records = item["records"]
                        print(f"\n📄 于{item['when']}中改动详情（{item['count']} 个文件）:")
                        for j, r in enumerate(grp_records, 1):
                            act_map = {"创建": "创建", "覆盖": "修改", "删除": "删除"}
                            act = act_map.get(r["action"], r["action"])
                            print(f"  {idx}.{j} [{r['time']}] {act} {r['path']}")
                        print(f"\n  /diff {idx}.M  查看第 M 条的详细 diff\n")
                except ValueError:
                    parts = arg.rsplit(None, 1)
                    file_path = parts[0]
                    sub_idx = None
                    if len(parts) == 2:
                        try:
                            sub_idx = int(parts[1])
                        except ValueError:
                            pass
                    file_records = tool_executor.get_diff_by_path(file_path)
                    if not file_records:
                        print(f"⚠️ 未找到 {file_path} 的改动记录\n")
                    elif sub_idx is not None:
                        if sub_idx < 1 or sub_idx > len(file_records):
                            print(f"⚠️ 序号超出范围（该文件共 {len(file_records)} 条记录）\n")
                        else:
                            _show_detail(file_records[sub_idx - 1], cur)
                    else:
                        print(f"\n📄 {file_path} 的改动历史（共 {len(file_records)} 条）:")
                        for i, r in enumerate(file_records, 1):
                            when = f"第{r['round']}轮对话"
                            act_map = {"创建": "创建", "覆盖": "修改", "删除": "删除"}
                            act = act_map.get(r["action"], r["action"])
                            print(f"  {i}. [{r['time']}] 于{when}中{act}")
                        print(f"\n  /diff {file_path} N  查看第 N 条的详细 diff\n")
            continue

        if user_text.lower() == "/mcp":
            mcp_tools = mcp_mgr.get_tool_names()
            if mcp_tools:
                print(f"\n🔌 已加载 MCP 工具 ({len(mcp_tools)} 个):")
                for name in mcp_tools:
                    for td in mcp_mgr.get_tools_definition():
                        if td["function"]["name"] == name:
                            desc = td["function"].get("description", "")
                            print(f"  - {name}: {desc}")
                            break
            else:
                print("\n⚠️ 未加载任何 MCP 工具")
                print(f"  将 MCP 配置文件放入 mcp/servers/ 目录即可自动加载")
            print()
            continue

        if user_text.lower().startswith("/save"):
            save_name = user_text[5:].strip() or None
            result_name, result_info = _save_session(save_name)
            if result_name:
                print(f"\n💾 会话已保存: {result_name}\n")
            else:
                print(f"\n❌ 保存失败: {result_info}\n")
            continue

        if user_text.lower().startswith("/load"):
            load_name = user_text[5:].strip()
            if not load_name:
                print("\n⚠️ 用法: /load <名称>\n   使用 /sessions 查看可用会话\n")
                continue
            data, err = _load_session(load_name)
            if err:
                print(f"\n❌ {err}\n")
                continue
            agent_id = data.get("agent_id", "global")
            switch_agent(agent_id, silent=True)
            current_history.clear()
            current_history.extend(data["history"])
            if "diff_records" in data:
                tool_executor.diff_records = data["diff_records"]
                tool_executor.current_round = data.get("current_round", 0)
            rounds = sum(1 for m in current_history if m.get("role") == "user")
            print(f"\n📂 已恢复会话: {load_name} (@{agent_id}, {rounds} 轮对话)")
            print(f"   保存时间: {data.get('saved_at', '未知')}\n")
            continue

        if user_text.lower() == "/sessions":
            sessions = _list_sessions()
            if not sessions:
                print("\n📁 暂无保存的会话\n   使用 /save [名称] 保存当前对话\n")
            else:
                print(f"\n📁 已保存的会话 ({len(sessions)} 个):")
                for name, saved_at, agent_id, rounds in sessions:
                    print(f"  - {name}  [{saved_at}]  @{agent_id}  {rounds}轮")
                print(f"\n   /load <名称> 恢复会话\n")
            continue


        if user_text.lower() == "/config":
            from .config_tui import open_config_tui
            _cur_aid = current_agent["id"] if current_agent else None
            saved, new_values, err = open_config_tui(_cur_aid)
            if err:
                print(f"\n⚠️ {err}\n")
                continue
            if not saved:
                print("\n已取消，未保存任何修改\n")
                continue
            _cfg.update(load_config())
            tool_executor.config = _cfg
            tool_executor.permission = min(3, max(0, _cfg.get("权限", 3)))
            MAX_HISTORY_ROUNDS = _cfg["最大记忆轮数"]
            MAX_TOOL_ROUNDS = _cfg["最大工具调用轮数"]
            COMPRESS_THRESHOLD = _cfg["历史压缩阈值轮数"]
            COMPRESS_KEEP_RECENT = _cfg["压缩保留最近轮数"]
            print("\n✅ 配置已保存并生效")
            for key, val in _cfg.items():
                print(f"   [{key}] = {val}")
            print()
            continue

        if user_text.lower() == "/reload":
            _cfg.update(load_config())
            tool_executor.config = _cfg
            tool_executor.permission = min(3, max(0, _cfg.get("权限", 3)))
            MAX_HISTORY_ROUNDS = _cfg["最大记忆轮数"]
            MAX_TOOL_ROUNDS = _cfg["最大工具调用轮数"]
            COMPRESS_THRESHOLD = _cfg["历史压缩阈值轮数"]
            COMPRESS_KEEP_RECENT = _cfg["压缩保留最近轮数"]
            mcp_mgr.shutdown()
            mcp_mgr.load_servers()
            ALL_TOOLS = TOOLS_DEFINITION + mcp_mgr.get_tools_definition()
            print("🔄 配置已重新加载")
            for key, val in _cfg.items():
                print(f"   [{key}] = {val}")
            agent_id = current_agent["id"] if current_agent else None
            if agent_id and agent_id != "global":
                refreshed = get_agent(agent_id)
                if refreshed:
                    current_agent.update(refreshed)
                    print(f"🔄 智能体 @{agent_id} 配置已重载")
            else:
                refreshed_global = get_global_agent()
                if refreshed_global:
                    global_agent.update(refreshed_global)
                    current_agent.update(refreshed_global)
                    print("🔄 全局智能体配置已重载")
            switch_agent(agent_id, silent=True)
            print()
            continue

        if user_text.lower() == "/agents":
            agents = list_agents()
            if agents:
                cid = current_agent["id"] if current_agent else "global"
                print_agent_list(agents, cid)
            else:
                print("\n⚠️ 没有找到智能体配置文件")
                print(f"  请在 agents/ 目录下创建 .txt 配置文件")
            continue

        if user_text.startswith("@") and " " not in user_text:
            target_id = user_text[1:]
            switch_agent(target_id)
            continue

        if user_text.startswith("@") and " " in user_text:
            parts = user_text.split(" ", 1)
            target_id = parts[0][1:]
            msg = parts[1].strip()
            if current_agent is None or current_agent["id"] != target_id:
                if not switch_agent(target_id):
                    continue
            if msg:
                tool_executor.next_round()
                chat(msg)
                print()
            continue

        if not user_text:
            continue

        tool_executor.next_round()
        chat(user_text)
        print()

    mcp_mgr.shutdown()


if __name__ == "__main__":
    main()
