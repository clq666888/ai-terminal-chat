#!/usr/bin/env python3
import sys
import os
import json
import readline
import requests

from chat_core import (
    load_api_key, load_system_prompt, HistoryManager,
    send_chat_request, parse_stream_chunk
)
from terminal_control import TerminalManager, stream_output
from tools import TOOLS_DEFINITION, ToolExecutor
from agent_manager import (
    list_agents, get_agent, get_global_agent,
    filter_tools, print_agent_list
)

import sys as _sys
_parent = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _parent not in _sys.path:
    _sys.path.insert(0, _parent)
from config_manager import load_config

_mcp_dir = os.path.join(_parent, "mcp")
if _mcp_dir not in _sys.path:
    _sys.path.insert(0, _mcp_dir)
from mcp_client import get_mcp_manager

_cfg = load_config()

WORK_DIR = os.getcwd()
MAX_HISTORY_ROUNDS = _cfg["最大记忆轮数"]
MAX_TOOL_ROUNDS = _cfg["最大工具调用轮数"]
COMPRESS_THRESHOLD = _cfg["历史压缩阈值轮数"]
COMPRESS_KEEP_RECENT = _cfg["压缩保留最近轮数"]

TOOL_RULES = """

你拥有以下工具能力，可以直接操作用户的文件系统：
{tool_list}

当前工作目录: {work_dir}

工具使用原则：
1. 当用户请求涉及文件操作、代码修改、命令执行时，主动使用工具完成
2. 修改文件前先读取了解现状
3. 写入文件时给出完整内容，不要省略
4. 当用户只是聊天、提问、讨论时，直接回答即可，不需要调用工具
5. 不要在回复中暴露 API Key、密码等敏感信息
6. 当你需要向用户提问、确认方案、或获取补充信息时，必须调用 ask_user 工具，禁止在回复文本中直接写问题等待用户回答。ask_user 的结果会立即返回给你，你可以基于用户的回答继续执行后续操作，整个过程不会中断当前任务"""

TOOL_DESC_MAP = {
    "read_file": "读取文件内容",
    "edit_file": "编辑文件（写入/创建/覆盖/删除）",
    "run_command": "执行 shell 命令",
    "list_dir": "列出目录结构",
    "search_files": "在文件中搜索文本",
    "call_agent": "调用其他智能体执行子任务",
    "ask_user": "向用户提问澄清需求",
}

TOOL_DISPLAY_MAP = {
    "read_file": "读取文件",
    "edit_file": "编辑文件",
    "run_command": "执行命令",
    "list_dir": "列出目录",
    "search_files": "搜索文件",
    "call_agent": "调用智能体",
    "ask_user": "用户提问",
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

AI_NAME = global_agent["name"]

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

    return prompt



def _get_callable_agents():
    agents = list_agents()
    return [a for a in agents if a.get("callable") and a["id"] != (current_agent["id"] if current_agent else "global")]


def run_sub_agent(agent_id, message):
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

    sub_history = [
        {"role": "system", "content": sub_system},
        {"role": "user", "content": message}
    ]


    for round_num in range(MAX_TOOL_ROUNDS):
        try:
            resp = send_chat_request(
                sub_api_url, sub_api_key, sub_history, sub_model,
                temperature=sub_temp, tools=sub_tools_def, stream=False,
                connect_timeout=_cfg["连接超时秒数"], read_timeout=_cfg["响应超时秒数"]
            )
        except Exception as e:
            return f"[错误] 子智能体请求失败: {e}"

        if resp.status_code != 200:
            return f"[错误] 子智能体请求失败 [{resp.status_code}]"

        data = resp.json()
        msg = data["choices"][0]["message"]
        finish_reason = data["choices"][0].get("finish_reason", "")

        if finish_reason == "tool_calls" or msg.get("tool_calls"):
            tool_calls = msg["tool_calls"]
            assistant_msg = {
                "role": "assistant",
                "content": msg.get("content") or "",
                "tool_calls": tool_calls
            }
            sub_history.append(assistant_msg)

            for tc in tool_calls:
                func_name = tc["function"]["name"]
                func_args = tc["function"]["arguments"]
                tc_id = tc["id"]
                if mcp_mgr.is_mcp_tool(func_name):
                    result = mcp_mgr.call_tool(func_name, func_args)
                else:
                    result = tool_executor.execute(func_name, func_args)
                sub_history.append({"role": "tool", "tool_call_id": tc_id, "content": result})
            continue

        final_content = msg.get("content", "")
        return final_content if final_content else "[子智能体未返回内容]"

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
        print(f"\n🔄 已切换到: {current_agent['name']} (@{current_agent['id']})")
        tool_names = [t["function"]["name"] for t in current_tools]
        display = " | ".join(TOOL_DISPLAY_MAP.get(n, n) for n in tool_names)
        print(f"🔧 可用工具: {display}")
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
    elif mcp_mgr.is_mcp_tool(func_name):
        return f"  🔌 MCP: {func_name}"
    else:
        return f"  🔧 {func_name}"


def chat(user_input):
    mgr = HistoryManager(current_history, MAX_HISTORY_ROUNDS, AI_NAME)
    global current_tools
    mcp_defs = mcp_mgr.get_tools_definition()
    if mcp_defs and not any(mcp_mgr.is_mcp_tool(t["function"]["name"]) for t in current_tools):
        current_tools = current_tools + mcp_defs
    mgr.add_user_message(user_input)

    for round_num in range(MAX_TOOL_ROUNDS):
        try:
            resp = send_chat_request(
                current_api_url, current_api_key, current_history, current_model,
                temperature=current_temperature, tools=current_tools, stream=False,
                connect_timeout=_cfg["连接超时秒数"], read_timeout=_cfg["响应超时秒数"]
            )
        except requests.RequestException as e:
            print(f"\n❌ 网络请求异常: {e}")
            if round_num == 0:
                mgr.rollback_user_message()
            return None

        if resp.status_code != 200:
            print(f"\n❌ 请求失败 [{resp.status_code}]: {resp.text}")
            if round_num == 0:
                mgr.rollback_user_message()
            return None

        data = resp.json()
        message = data["choices"][0]["message"]
        finish_reason = data["choices"][0].get("finish_reason", "")

        if finish_reason == "tool_calls" or message.get("tool_calls"):
            if message.get("content"):
                print(f"\n{AI_NAME}: {message['content']}")

            tool_calls = message["tool_calls"]
            assistant_msg = {
                "role": "assistant",
                "content": message.get("content") or "",
                "tool_calls": tool_calls
            }
            mgr.save_tool_call_message(assistant_msg)

            for tc in tool_calls:
                func_name = tc["function"]["name"]
                func_args = tc["function"]["arguments"]
                tc_id = tc["id"]

                if func_name == "call_agent":
                    _args = json.loads(func_args) if isinstance(func_args, str) else func_args
                    _agent_id = _args.get("agent_id", "")
                    result = run_sub_agent(_agent_id, _args.get("message", ""))
                    if result.startswith("[错误]"):
                        print(f"  🤖 @{_agent_id} 调用失败: {result}")
                    else:
                        print(f"  🤖 @{_agent_id}:")
                        print(f"  {result}")
                elif mcp_mgr.is_mcp_tool(func_name):
                    print(format_tool_log(func_name, func_args))
                    result = mcp_mgr.call_tool(func_name, func_args)
                else:
                    print(format_tool_log(func_name, func_args))
                    result = tool_executor.execute(func_name, func_args)
                mgr.save_tool_result(tc_id, result)

            continue

        break
    else:
        print("\n⚠️ 达到最大工具调用轮数，停止执行")
        return None

    try:
        stream_resp = send_chat_request(
            current_api_url, current_api_key, current_history, current_model,
            temperature=current_temperature, tools=None, stream=True,
            connect_timeout=_cfg["连接超时秒数"], read_timeout=_cfg["响应超时秒数"]
        )
    except requests.RequestException as e:
        print(f"\n❌ 流式请求异常: {e}")
        return None

    if stream_resp.status_code != 200:
        print(f"\n❌ 请求失败 [{stream_resp.status_code}]: {stream_resp.text}")
        return None

    with TerminalManager():
        final_text = stream_output(stream_resp, AI_NAME)

    if final_text:
        mgr.save_assistant_reply(final_text)
        if COMPRESS_THRESHOLD > 0 and mgr.needs_compression(COMPRESS_THRESHOLD):
            _do_compress(mgr, silent=False)
    else:
        mgr.add_interrupt_hint()
    return final_text


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
    switch_agent(None, silent=True)

    agents = list_agents()
    other_agents = [a for a in agents if a["id"] != "global"]

    print(f"\n🤖 工具作者: clq")
    print(f"📂 工作目录: {WORK_DIR}")
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
        chat(user_input)
        mcp_mgr.shutdown()
        return

    while True:
        try:
            agent_tag = f"@{current_agent['id']}" if current_agent and current_agent["id"] != "global" else ""
            prompt = f"你{agent_tag}: "
            user_text = input(prompt).strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见！")
            break


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
            print("对话结束")
            break

        if user_text.lower() == "/clear":
            switch_agent(current_agent["id"] if current_agent else None, silent=True)
            print("📝 记忆已清空\n")
            continue



        if user_text.lower() == "/undo":
            if len(current_history) <= 1:
                print("⚠️ 没有可撤销的对话\n")
                continue
            removed = 0
            while len(current_history) > 1:
                last = current_history[-1]
                if last["role"] == "user" and removed > 0:
                    current_history.pop()
                    removed += 1
                    break
                current_history.pop()
                removed += 1
            print(f"↩️  已撤销上一轮对话（移除 {removed} 条消息）\n")
            continue

        if user_text.lower() == "/compress":
            mgr = HistoryManager(current_history, MAX_HISTORY_ROUNDS, AI_NAME)
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
            print("  /undo     - 撤销上一轮对话")
            print("  /compress - 压缩历史记忆（减少 token 占用）")
            print("  /reload   - 重新加载配置和智能体")
            print("  /agents   - 查看所有智能体列表")
            print("  /mcp      - 查看已加载的 MCP 工具")
            print("  /list     - 显示本指令列表")
            print()
            print("📋 特殊输入:")
            print("  @名称     - 切换到指定智能体")
            print("  @名称 内容 - 切换并直接对话")
            print('  \"\"\"       - 进入多行输入模式')
            print()
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

        if user_text.lower() == "/reload":
            _cfg.update(load_config())
            tool_executor.config = _cfg
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
                chat(msg)
                print()
            continue

        if not user_text:
            continue

        chat(user_text)
        print()

    mcp_mgr.shutdown()


if __name__ == "__main__":
    main()
