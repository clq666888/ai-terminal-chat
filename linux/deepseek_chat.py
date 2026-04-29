#!/usr/bin/env python3
import sys
import readline
import requests

# ==================== 配置区（可直接修改） ====================
API_KEY = "你的 API Key"
BASE_URL = "https://api.deepseek.com/v1/chat/completions"

# 模型选择（取消注释你想用的那一行）
# MODEL = "deepseek-chat"
# MODEL = "deepseek-v4-pro"
MODEL = "deepseek-v4-flash"

# 外部系统提示词文件路径（留空则使用默认提示词）
SYSTEM_PROMPT_FILE = "/home/clq/api脚本调用/提示词/.txt"   # 例如: "/home/clq/prompts/assistant.txt"

# 默认系统提示词（未指定外部文件时生效）
DEFAULT_SYSTEM_PROMPT = "你是 DeepSeek，一个聪明的 AI 助手。"
# =============================================================

history = []

def load_system_prompt(file_path):
    """从 txt 文件读取系统提示词，如果文件不存在或读取失败则返回 None"""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            prompt = f.read().strip()
            if not prompt:
                raise ValueError("提示词文件为空")
            return prompt
    except Exception as e:
        print(f"⚠️ 无法加载提示词文件 '{file_path}': {e}")
        return None

def chat(user_input):
    """发送对话，维护上下文记忆"""
    history.append({"role": "user", "content": user_input})

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": MODEL,
        "messages": history,
        # "max_tokens": 1024,
        "temperature": 0.7
    }

    resp = requests.post(BASE_URL, json=payload, headers=headers)

    if resp.status_code != 200:
        print(f"❌ 请求失败 [{resp.status_code}]: {resp.text}")
        history.pop()
        return None

    data = resp.json()
    reply = data["choices"][0]["message"]["content"]
    history.append({"role": "assistant", "content": reply})
    return reply

if __name__ == "__main__":
    # 确定系统提示词
    system_content = DEFAULT_SYSTEM_PROMPT
    prompt_source = None   # 保存提示词来源（文件名或None）
    if SYSTEM_PROMPT_FILE:
        loaded_prompt = load_system_prompt(SYSTEM_PROMPT_FILE)
        if loaded_prompt:
            system_content = loaded_prompt
            prompt_source = SYSTEM_PROMPT_FILE

    # 输出提示词来源（不打印内容）
    if prompt_source:
        print(f"📄 当前系统提示词文件：{prompt_source}")
    else:
        print("📋 使用默认系统提示词")

    # 初始化历史
    history.append({"role": "system", "content": system_content})

    # 命令行单次提问
    if len(sys.argv) > 1:
        user_input = " ".join(sys.argv[1:])
        print(f"你: {user_input}")
        reply = chat(user_input)
        if reply:
            print(f"DeepSeek: {reply}")
        sys.exit(0)

    # 交互循环
    print("\n🤖 DeepSeek 上下文对话（输入 exit 退出，输入 clear 清空记忆）")
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

        reply = chat(user_text)
        if reply:
            print(f"DeepSeek: {reply}\n")