#!/usr/bin/env python3
import sys
import os
import json
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

WORK_DIR = os.getcwd()
MAX_HISTORY_ROUNDS = 50
MAX_TOOL_ROUNDS = 20

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
6. 当前运行环境是 Windows，执行命令时使用 Windows 语法"""

TOOL_DESC_MAP = {
    "read_file": "读取文件内容",
    "edit_file": "编辑文件（写入/创建/覆盖/删除）",
    "run_command": "执行命令",
    "list_dir": "列出目录结构",
    "search_files": "在文件中搜索文本",
}

TOOL_DISPLAY_MAP = {
    "read_file": "读取文件",
    "edit_file": "编辑文件",
    "run_command": "执行命令",
    "list_dir": "列出目录",
    "search_files": "搜索文件",
}

os.system("chcp 65001 >nul 2>&1")

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

tool_executor = ToolExecutor(WORK_DIR)

current_agent = None
current_history = []
current_tools = TOOLS_DEFINITION
current_model = global_agent["model"]
current_api_url = global_agent["api_url"]
current_api_key = global_agent["api_key"]
current_temperature = global_agent["temperature"] if global_agent["temperature"] is not None else 0.7
agent_histories = {}


def build_system_prompt(agent_config):
    base = agent_config["system_prompt"] if agent_config["system_prompt"] else ""

    tool_names = [t["function"]["name"] for t in current_tools]
    tool_lines = "\n".join(f"- {name}: {TOOL_DESC_MAP.get(name, name)}" for name in tool_names)

    return base + TOOL_RULES.format(tool_list=tool_lines, work_dir=WORK_DIR)


def switch_agent(agent_id):
    global current_agent, current_history, current_tools, current_model
    global current_api_url, current_api_key, current_temperature

    if agent_id is None or agent_id == "global":
        current_agent = global_agent
        current_history = agent_histories.setdefault("global", [])
        current_tools = filter_tools(TOOLS_DEFINITION, global_agent["allowed_tools"])
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
        current_tools = filter_tools(TOOLS_DEFINITION, agent["allowed_tools"])
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
    else:
        return f"  🔧 {func_name}"


def chat(user_input):
    mgr = HistoryManager(current_history, MAX_HISTORY_ROUNDS, AI_NAME)
    mgr.add_user_message(user_input)

    for round_num in range(MAX_TOOL_ROUNDS):
        try:
            resp = send_chat_request(
                current_api_url, current_api_key, current_history, current_model,
                temperature=current_temperature, tools=current_tools, stream=False
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

                print(format_tool_log(func_name, func_args))

                result = tool_executor.execute(func_name, func_args)
                mgr.save_tool_result(tc_id, result)

            continue

        final_text = message.get("content", "")
        if final_text:
            print(f"\n{AI_NAME}: {final_text}")
            mgr.save_assistant_reply(final_text)
        return final_text

    print("\n⚠️ 达到最大工具调用轮数，停止执行")
    return None


def main():
    switch_agent(None)

    agents = list_agents()

    print(f"\n🤖 {AI_NAME}")
    print(f"📂 工作目录: {WORK_DIR}")
    tool_names = [t["function"]["name"] for t in current_tools]
    display = " | ".join(TOOL_DISPLAY_MAP.get(n, n) for n in tool_names)
    print(f"🔧 可用工具: {display}")
    other_agents = [a for a in agents if a["id"] != "global"]
    if other_agents:
        ids = ", ".join(f"@{a['id']}" for a in other_agents)
        print(f"🧩 可用智能体: {ids}")
    print("─" * 50)
    print("输入 exit 退出 | clear 清空记忆 | agents 列表 | @名称 切换\n")

    if len(sys.argv) > 1:
        user_input = " ".join(sys.argv[1:])
        print(f"你: {user_input}")
        chat(user_input)
        return

    while True:
        try:
            agent_tag = f"@{current_agent['id']}" if current_agent and current_agent["id"] != "global" else ""
            prompt = f"你{agent_tag}: "
            user_text = input(prompt).strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见！")
            break

        if user_text.lower() == "exit":
            print("对话结束")
            break

        if user_text.lower() == "clear":
            switch_agent(current_agent["id"] if current_agent else None)
            print("📝 记忆已清空\n")
            continue

        if user_text.lower() == "agents":
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


if __name__ == "__main__":
    main()
