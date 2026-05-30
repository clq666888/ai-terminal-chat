#!/usr/bin/env python3
import sys
import readline
import requests

from chat_core import load_api_key, load_system_prompt, HistoryManager, send_chat_request
from terminal_control import TerminalManager, stream_output

# ==================== 配置区（可直接修改） ====================
# -- API 访问设置 --
BASE_URL = "https://api.deepseek.com/v1/chat/completions"   # 接口地址
KEY_FILE_PATH = "/home/sti/apikey.txt"                      # API Key 文件路径（建议用绝对路径）

# -- 模型选择（取消注释你想用的那一行） --
MODEL = "deepseek-chat"
# MODEL = "deepseek-v4-pro"
# MODEL = "deepseek-v4-flash"

# 外部系统提示词文件路径（留空则使用默认提示词）
SYSTEM_PROMPT_FILE = "/home/sti/api调用脚本/提示词/无限制.txt"

# -- AI 显示名称（切换其他 AI 时修改这里即可） --
AI_NAME = "DeepSeek"

# -- 上下文轮数限制（0 = 不限制，建议 20-50） --
MAX_HISTORY_ROUNDS = 50

# 默认系统提示词（未指定外部文件时生效）
DEFAULT_SYSTEM_PROMPT = "你是一个聪明的 AI 助手。"
# =============================================================

try:
    API_KEY = load_api_key(KEY_FILE_PATH)
except RuntimeError as e:
    print(f"❌ {e}")
    sys.exit(1)

history = []


def chat(user_input):
    mgr = HistoryManager(history, MAX_HISTORY_ROUNDS, AI_NAME)
    mgr.add_user_message(user_input)

    try:
        with TerminalManager():
            resp = send_chat_request(BASE_URL, API_KEY, history, MODEL)

            if resp.status_code != 200:
                print(f"\n❌ 请求失败 [{resp.status_code}]: {resp.text}")
                mgr.rollback_user_message()
                return None

            reply = stream_output(resp, AI_NAME)

        if reply is None:
            mgr.add_interrupt_hint()
        else:
            mgr.save_assistant_reply(reply)

        return reply

    except requests.RequestException as e:
        print(f"\n❌ 网络请求异常: {e}")
        mgr.rollback_user_message()
        return None


if __name__ == "__main__":
    system_content = DEFAULT_SYSTEM_PROMPT
    prompt_source = None
    if SYSTEM_PROMPT_FILE:
        loaded_prompt = load_system_prompt(SYSTEM_PROMPT_FILE)
        if loaded_prompt:
            system_content = loaded_prompt
            prompt_source = SYSTEM_PROMPT_FILE

    if prompt_source:
        print(f"📄 当前系统提示词文件：{prompt_source}")
    else:
        print("📋 使用默认系统提示词")

    history.append({"role": "system", "content": system_content})

    if len(sys.argv) > 1:
        user_input = " ".join(sys.argv[1:])
        print(f"你: {user_input}")
        chat(user_input)
        sys.exit(0)

    print(f"\n🤖 {AI_NAME} 上下文对话（输入 exit 退出，输入 clear 清空记忆）")
    print("💡 流式输出中：按 空格 暂停/继续，按 Ctrl+空格 打断当前生成\n")
    while True:
        try:
            user_text = input("你: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见！")
            break

        if user_text.lower() == "exit":
            print("对话结束")
            break
        if user_text.lower() == "clear":
            history.clear()
            history.append({"role": "system", "content": system_content})
            print("📝 记忆已清空\n")
            continue
        if not user_text:
            continue

        chat(user_text)
        print()
