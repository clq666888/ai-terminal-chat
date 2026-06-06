#!/usr/bin/env python3
import sys
import os
import json
import uuid
import time
import threading
import queue
from flask import Flask, render_template, request, Response, jsonify, stream_with_context, send_from_directory

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass

from chat_core import load_api_key, load_system_prompt, HistoryManager, send_chat_request, parse_stream_chunk, parse_stream_chunk_full, build_request_payload
import requests
import re
import csv
import io

# ==================== 配置区 ====================
BASE_URL = "https://api.deepseek.com"
MODEL = ""
AI_NAME = "AI Chat"
MAX_HISTORY_ROUNDS = 50
HOST = "0.0.0.0"
PORT = 8080
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings.json")
APIKEY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".apikey")
AGENTS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "agents.json")
CONVERSATIONS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "conversations.json")
UPLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "uploads")
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp", "svg"}
# =============================================================

PROVIDER_MODELS = {
    "deepseek": {
        "name": "DeepSeek",
        "base_url": "https://api.deepseek.com",
        "models": ["deepseek-v4-flash", "deepseek-v4-pro", "deepseek-chat", "deepseek-reasoner"]
    },
    "openai": {
        "name": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "models": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo", "o1", "o1-mini", "o3-mini"]
    },
    "claude": {
        "name": "Claude (via API proxy)",
        "base_url": "https://api.anthropic.com/v1",
        "models": ["claude-sonnet-4-20250514", "claude-3-5-sonnet-20241022", "claude-3-haiku-20240307", "claude-3-opus-20240229"]
    },
    "gemini": {
        "name": "Google Gemini (OpenAI 兼容)",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "models": ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.0-flash", "gemini-1.5-pro"]
    },
    "qwen": {
        "name": "通义千问",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "models": ["qwen-max", "qwen-plus", "qwen-turbo", "qwen-long"]
    },
    "zhipu": {
        "name": "智谱 GLM",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "models": ["glm-4-plus", "glm-4", "glm-4-flash", "glm-4-long"]
    },
    "moonshot": {
        "name": "Moonshot / Kimi",
        "base_url": "https://api.moonshot.cn/v1",
        "models": ["moonshot-v1-128k", "moonshot-v1-32k", "moonshot-v1-8k"]
    },
    "custom": {
        "name": "自定义",
        "base_url": "",
        "models": []
    }
}

app = Flask(__name__)
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0
APP_START_TIME = str(int(time.time()))

@app.context_processor
def inject_cache_version():
    return {"cache_version": APP_START_TIME}
os.makedirs(UPLOAD_DIR, exist_ok=True)


def _default_config():
    return {
        "base_url": BASE_URL,
        "api_key": "",
        "api_keys": {},
        "model": "",
        "provider": "deepseek",
        "max_history_rounds": MAX_HISTORY_ROUNDS,
        "max_context_size_kb": 0,
        "auto_compress": False,
        "compress_threshold_kb": 8,
        "web_search_count": 5,
        "custom_models": []
    }

def _load_config():
    cfg = _default_config()
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
            for k in cfg:
                if k in saved:
                    cfg[k] = saved[k]
        except Exception:
            pass
    cfg["api_keys"] = _load_api_keys()
    cfg["api_key"] = cfg["api_keys"].get(cfg["provider"], "")
    return cfg


def _load_api_keys():
    keys = {}
    if os.path.exists(APIKEY_FILE):
        try:
            with open(APIKEY_FILE, "r", encoding="utf-8") as f:
                raw = f.read().strip()
            if raw:
                if raw.startswith("{"):
                    keys = json.loads(raw)
                else:
                    keys["deepseek"] = raw
        except Exception:
            pass
    return keys if isinstance(keys, dict) else {}


def _save_api_keys(keys):
    try:
        with open(APIKEY_FILE, "w", encoding="utf-8") as f:
            json.dump(keys or {}, f, ensure_ascii=False, indent=2)
        try:
            os.chmod(APIKEY_FILE, 0o600)
        except Exception:
            pass
    except Exception:
        pass


def _get_key_for(provider):
    return runtime_config.get("api_keys", {}).get(provider, "")


def _set_key_for(provider, key):
    if "api_keys" not in runtime_config or not isinstance(runtime_config["api_keys"], dict):
        runtime_config["api_keys"] = {}
    runtime_config["api_keys"][provider] = (key or "").strip()
    _save_api_keys(runtime_config["api_keys"])
    if provider == runtime_config.get("provider"):
        runtime_config["api_key"] = runtime_config["api_keys"][provider]


def _save_config(cfg):
    save_data = {}
    for k, v in cfg.items():
        if k in ("api_key", "api_keys"):
            continue
        save_data[k] = v
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(save_data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _load_agents():
    if os.path.exists(AGENTS_FILE):
        try:
            with open(AGENTS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return []


def _save_agents(agents):
    try:
        with open(AGENTS_FILE, "w", encoding="utf-8") as f:
            json.dump(agents, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _load_conversations():
    if os.path.exists(CONVERSATIONS_FILE):
        try:
            with open(CONVERSATIONS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return {c["id"]: c for c in data}
        except Exception:
            pass
    return {}


def _save_conversations():
    try:
        data = list(conversations.values())
        with open(CONVERSATIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
    except Exception:
        pass


def _allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


import web_search

runtime_config = _load_config()
agents_list = _load_agents()
conversations = _load_conversations()
current_agent_id = None


def _get_agent(agent_id):
    if not agent_id:
        return None
    for a in agents_list:
        if a["id"] == agent_id:
            return a
    return None


def _get_system_content(agent_id=None):
    agent = _get_agent(agent_id)
    if agent and agent.get("system_prompt"):
        return agent["system_prompt"]
    return ""


def _get_chat_config(agent_id=None):
    agent = _get_agent(agent_id)
    if agent and agent.get("model"):
        base_url = agent.get("base_url", "") or runtime_config["base_url"]
        provider = agent.get("provider", "") or runtime_config["provider"]
        p = PROVIDER_MODELS.get(provider)
        if not base_url and p:
            base_url = p["base_url"]
        return {
            "base_url": base_url,
            "model": agent["model"],
            "api_key": _get_key_for(provider)
        }
    return {
        "base_url": runtime_config["base_url"],
        "model": runtime_config["model"],
        "api_key": _get_key_for(runtime_config["provider"])
    }


def _get_callable_agents():
    return [a for a in agents_list if a.get("callable") and a.get("slug")]


def _build_callable_prompt(callable_agents):
    if not callable_agents:
        return ""
    lines = ["\n\n你可以调用以下智能体来协助完成任务："]
    for a in callable_agents:
        lines.append(f"- {a['slug']}（{a['name']}）: {a.get('when_to_call', '')}")
    lines.append("\n调用格式：在回复中使用 [CALL:英文标识名] 你要交给该智能体的具体任务描述 [/CALL]")
    lines.append("你可以在一次回复中调用多个智能体。调用结果会自动返回给你，你再整合后回复用户。")
    lines.append("如果不需要调用任何智能体，直接回复用户即可。")
    return "\n".join(lines)


ASK_ANSWER_PREFIX = "[[ASK_ANSWER]]"
HISTORY_SUMMARY_PREFIX = "[[HISTORY_SUMMARY]]"


def _history_bytes(history):
    try:
        return len(json.dumps(history, ensure_ascii=False).encode("utf-8"))
    except Exception:
        return 0


def _msg_plain_text(m):
    c = m.get("content")
    if isinstance(c, str):
        if c.startswith(ASK_ANSWER_PREFIX):
            c = c[len(ASK_ANSWER_PREFIX):]
        if c.startswith(HISTORY_SUMMARY_PREFIX):
            c = c[len(HISTORY_SUMMARY_PREFIX):]
        return c
    if isinstance(c, list):
        parts = []
        for b in c:
            if isinstance(b, dict) and b.get("type") == "text":
                parts.append(b.get("text", ""))
            elif isinstance(b, dict) and b.get("type") == "image_url":
                parts.append("[图片]")
        return "\n".join(parts)
    return ""


def _compress_history(history, llm_call, threshold_bytes, keep_recent_msgs=6):
    """超阈值时把最老的若干条普通消息压成一条摘要 system 消息。
    返回 True 表示发生了压缩。完整原文不在此处删除（仅影响传入的 history 列表副本逻辑由调用方决定）。"""
    if threshold_bytes <= 0:
        return False
    if _history_bytes(history) <= threshold_bytes:
        return False

    sys_count = 1 if (history and history[0].get("role") == "system") else 0
    summary_idx = next(
        (i for i, m in enumerate(history)
         if m.get("role") == "system" and isinstance(m.get("content"), str)
         and m["content"].startswith(HISTORY_SUMMARY_PREFIX)),
        -1
    )

    head = sys_count
    if summary_idx == head:
        head += 1

    total = len(history)
    end = total - keep_recent_msgs
    if end <= head:
        return False

    to_compress = history[head:end]
    if not to_compress:
        return False

    prev_summary = ""
    if summary_idx >= 0:
        prev_summary = _msg_plain_text(history[summary_idx])

    lines = []
    for m in to_compress:
        role = m.get("role")
        if role == "user":
            who = "用户"
        elif role == "assistant":
            who = "助手"
        else:
            who = "系统"
        txt = _msg_plain_text(m).strip()
        if txt:
            lines.append(f"{who}：{txt}")
    convo_text = "\n".join(lines)
    if not convo_text.strip():
        return False

    prompt = (
        "请把下面这段较早的对话历史压缩成一份简洁的中文「前情提要」，"
        "保留关键事实、用户偏好、已达成的结论、未完成的任务和重要约定，"
        "去掉寒暄和冗余，用要点列出，不要编造未出现的信息。\n\n"
    )
    if prev_summary.strip():
        prompt += "已有的前情提要（请与下面新内容融合为一份）：\n" + prev_summary.strip() + "\n\n"
    prompt += "需要压缩的对话：\n" + convo_text

    try:
        summary = llm_call([{"role": "user", "content": prompt}])
    except Exception:
        summary = ""
    if not summary or not summary.strip():
        return False

    summary_msg = {
        "role": "system",
        "content": HISTORY_SUMMARY_PREFIX + "【前情提要（自动压缩）】\n" + summary.strip()
    }

    new_history = []
    new_history.extend(history[:sys_count])
    new_history.append(summary_msg)
    new_history.extend(history[end:])
    history.clear()
    history.extend(new_history)
    return True




ASK_PROMPT = (
    "\n\n【向用户提问能力·重要】你具备主动向用户提问的能力，这是你的核心交互方式之一。"
    "当任务存在多种可能方向、需求不明确、缺少关键信息、或你需要用户在几个方案中做选择时，"
    "你【应当主动发起提问】来获取信息，而不是自行假设或要求用户重述。需要提问时，"
    "在回复中输出一个用 [ASK] 与 [/ASK] 包裹的 JSON，格式如下：\n"
    "[ASK]{\"questions\":[{\"type\":\"choice\",\"q\":\"问题文本\",\"options\":[\"选项A\",\"选项B\"]},"
    "{\"type\":\"text\",\"q\":\"另一个需要用户描述的问题\"}]}[/ASK]\n"
    "规则：\n"
    "1. type 为 choice（选项题，需给 options 数组）或 text（问答题，用户自由输入）。\n"
    "2. 一次最多提 5 个问题（不含系统自动追加的补充项），不要超过。\n"
    "3. 选项题不必自己加“其他”，系统会自动为用户提供“其他”和“是否需要补充”的入口。\n"
    "4. [ASK] 之前可以写一句简短引导语，[ASK] 块必须是本次回复的最后内容，其后不要再输出正文。\n"
    "5. 信息已经充分、能直接给出可靠答案时就直接回答，不要为了提问而提问；"
    "但只要存在需求歧义或方向选择，就优先用提问澄清。收到用户回答后，结合回答自然地继续完成任务，"
    "无需复述用户的每一条回答。"
)


def _parse_ask_block(text):
    """从回复中解析 [ASK]{json}[/ASK]，返回 (questions_list 或 None, 去掉ASK块的前置文本)。"""
    m = re.search(r"\[ASK\]([\s\S]*?)\[/ASK\]", text)
    if not m:
        return None, text
    raw = m.group(1).strip()
    try:
        data = json.loads(raw)
    except Exception:
        return None, text
    questions = data.get("questions") if isinstance(data, dict) else None
    if not isinstance(questions, list) or not questions:
        return None, text
    clean = []
    for q in questions[:5]:
        if not isinstance(q, dict):
            continue
        qtype = "choice" if q.get("type") == "choice" else "text"
        item = {"type": qtype, "q": str(q.get("q", "")).strip()}
        if qtype == "choice":
            opts = q.get("options") or []
            item["options"] = [str(o) for o in opts if str(o).strip()]
            if not item["options"]:
                item["type"] = "text"
                item.pop("options", None)
        if item["q"]:
            clean.append(item)
    if not clean:
        return None, text
    prefix = text[:m.start()].rstrip()
    return clean, prefix


def _execute_agent_calls(text):
    pattern = r"\[CALL:(\S+?)\]([\s\S]*?)\[/CALL\]"
    matches = re.findall(pattern, text)
    if not matches:
        return text

    for slug, task_content in matches:
        task_content = task_content.strip()
        agent = None
        for a in agents_list:
            if a.get("slug") == slug and a.get("callable"):
                agent = a
                break
        if not agent:
            result = f"[错误: 未找到智能体 {slug}]"
        else:
            try:
                sub_cfg = _get_chat_config(agent["id"])
                sub_history = []
                if agent.get("system_prompt"):
                    sub_history.append({"role": "system", "content": agent["system_prompt"]})
                sub_history.append({"role": "user", "content": task_content})
                resp = send_chat_request(
                    sub_cfg["base_url"],
                    sub_cfg["api_key"],
                    sub_history,
                    sub_cfg["model"]
                )
                if resp.status_code != 200:
                    result = f"[调用失败: HTTP {resp.status_code}]"
                else:
                    sub_reply = ""
                    for line in resp.iter_lines(decode_unicode=True):
                        chunk = parse_stream_chunk(line)
                        if chunk is None:
                            break
                        if chunk:
                            sub_reply += chunk
                    result = sub_reply if sub_reply else "[智能体无回复]"
            except Exception as e:
                result = f"[调用异常: {str(e)}]"

        old_block = f"[CALL:{slug}]{task_content}[/CALL]"
        # 用正则精确匹配（因为 task_content 可能有换行）
        escaped_slug = re.escape(slug)
        block_pattern = f"\\[CALL:{escaped_slug}\\][\\s\\S]*?\\[/CALL\\]"
        text = re.sub(block_pattern, f"[CALL:{slug}]{result}[/CALL]", text, count=1)

    return text


def _new_conversation(agent_id=None):
    cid = str(uuid.uuid4())[:8]
    system_content = _get_system_content(agent_id)
    history = []
    if system_content:
        history.append({"role": "system", "content": system_content})
    conversations[cid] = {
        "id": cid,
        "title": "新对话",
        "agent_id": agent_id,
        "history": history,
        "created": time.time(),
        "pinned": False
    }
    _save_conversations()
    return cid


def _get_conv(cid):
    return conversations.get(cid)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/providers", methods=["GET"])
def get_providers():
    result = {}
    for key, val in PROVIDER_MODELS.items():
        result[key] = {"name": val["name"], "base_url": val["base_url"], "models": val["models"]}
    return jsonify(result)


@app.route("/api/provider-key-status", methods=["GET"])
def provider_key_status():
    provider = request.args.get("provider", "").strip()
    return jsonify({"has_api_key": bool(_get_key_for(provider)) if provider else False})


@app.route("/api/settings", methods=["GET"])
def get_settings():
    return jsonify({
        "provider": runtime_config["provider"],
        "base_url": runtime_config["base_url"],
        "model": runtime_config["model"],
        "has_api_key": bool(_get_key_for(runtime_config["provider"])),
        "max_history_rounds": runtime_config["max_history_rounds"],
        "max_context_size_kb": runtime_config.get("max_context_size_kb", 0),
        "auto_compress": runtime_config.get("auto_compress", False),
        "compress_threshold_kb": runtime_config.get("compress_threshold_kb", 8),
        "web_search_count": runtime_config.get("web_search_count", 5)
    })


@app.route("/api/settings", methods=["PUT"])
def update_settings():
    data = request.get_json()
    if "provider" in data:
        runtime_config["provider"] = data["provider"]
    if "base_url" in data:
        runtime_config["base_url"] = data["base_url"]
    if "model" in data:
        runtime_config["model"] = data["model"]
    if "max_history_rounds" in data:
        try:
            runtime_config["max_history_rounds"] = int(data["max_history_rounds"])
        except (ValueError, TypeError):
            pass
    if "max_context_size_kb" in data:
        try:
            runtime_config["max_context_size_kb"] = int(data["max_context_size_kb"])
        except (ValueError, TypeError):
            pass
    if "auto_compress" in data:
        runtime_config["auto_compress"] = bool(data["auto_compress"])
    if "compress_threshold_kb" in data:
        try:
            v = int(data["compress_threshold_kb"])
            runtime_config["compress_threshold_kb"] = max(1, v)
        except (ValueError, TypeError):
            pass
    if "web_search_count" in data:
        try:
            n = int(data["web_search_count"])
            runtime_config["web_search_count"] = max(3, min(10, n))
        except (ValueError, TypeError):
            pass
    if "api_key" in data and data["api_key"]:
        target_provider = data.get("provider") or runtime_config["provider"]
        _set_key_for(target_provider, data["api_key"])
    _save_config(runtime_config)
    return jsonify({"status": "ok"})


@app.route("/api/model", methods=["PUT"])
def switch_model():
    data = request.get_json()
    provider = data.get("provider", "")
    model = data.get("model", "")
    base_url = data.get("base_url", "")
    if provider and model:
        runtime_config["provider"] = provider
        runtime_config["model"] = model
        runtime_config["api_key"] = _get_key_for(provider)
        if base_url:
            runtime_config["base_url"] = base_url
        else:
            p = PROVIDER_MODELS.get(provider)
            if p and p["base_url"]:
                runtime_config["base_url"] = p["base_url"]
        _save_config(runtime_config)
        return jsonify({"status": "ok"})
    return jsonify({"error": "缺少参数"}), 400


@app.route("/api/active-model", methods=["GET"])
def get_active_model():
    return jsonify({"provider": runtime_config["provider"], "model": runtime_config["model"]})


@app.route("/api/custom-models", methods=["GET"])
def get_custom_models():
    return jsonify(runtime_config.get("custom_models", []))


@app.route("/api/custom-models", methods=["POST"])
def add_custom_model():
    data = request.get_json()
    provider = data.get("provider", "").strip()
    model = data.get("model", "").strip()
    base_url = data.get("base_url", "").strip()
    name = data.get("name", "").strip()
    if not provider or not model:
        return jsonify({"error": "需要 provider 和 model"}), 400
    if not name:
        p = PROVIDER_MODELS.get(provider)
        provider_name = p["name"] if p else provider
        name = provider_name + " / " + model
    if not base_url:
        p = PROVIDER_MODELS.get(provider)
        base_url = p["base_url"] if p else ""
    models = runtime_config.get("custom_models", [])
    for m in models:
        if m["provider"] == provider and m["model"] == model:
            return jsonify({"error": "该模型已存在"}), 409
    entry = {"provider": provider, "model": model, "base_url": base_url, "name": name}
    models.append(entry)
    runtime_config["custom_models"] = models
    _save_config(runtime_config)
    return jsonify(entry), 201


@app.route("/api/custom-models", methods=["DELETE"])
def remove_custom_model():
    data = request.get_json()
    provider = data.get("provider", "")
    model = data.get("model", "")
    models = runtime_config.get("custom_models", [])
    runtime_config["custom_models"] = [m for m in models if not (m["provider"] == provider and m["model"] == model)]
    _save_config(runtime_config)
    return jsonify({"status": "ok"})


@app.route("/api/custom-models", methods=["PUT"])
def update_custom_model():
    data = request.get_json()
    old_provider = data.get("old_provider", "").strip()
    old_model = data.get("old_model", "").strip()
    new_provider = data.get("provider", "").strip()
    new_model = data.get("model", "").strip()
    new_base_url = data.get("base_url", "").strip()
    new_name = data.get("name", "").strip()
    if not new_model:
        return jsonify({"error": "模型名称不能为空"}), 400
    models = runtime_config.get("custom_models", [])
    found = False
    for m in models:
        if m["provider"] == old_provider and m["model"] == old_model:
            m["provider"] = new_provider
            m["model"] = new_model
            m["base_url"] = new_base_url
            m["name"] = new_name
            found = True
            break
    if not found:
        return jsonify({"error": "未找到原模型"}), 404
    runtime_config["custom_models"] = models
    _save_config(runtime_config)
    return jsonify({"status": "ok"})


# ==================== 智能体 API ====================

@app.route("/api/agents", methods=["GET"])
def list_agents():
    return jsonify(agents_list)


@app.route("/api/agents", methods=["POST"])
def create_agent():
    data = request.get_json()
    name = data.get("name", "").strip()
    if not name:
        return jsonify({"error": "名称不能为空"}), 400
    agent = {
        "id": str(uuid.uuid4())[:8],
        "name": name,
        "avatar": data.get("avatar", ""),
        "system_prompt": data.get("system_prompt", ""),
        "model": data.get("model", ""),
        "provider": data.get("provider", ""),
        "base_url": data.get("base_url", ""),
        "callable": data.get("callable", False),
        "slug": data.get("slug", ""),
        "when_to_call": data.get("when_to_call", ""),
        "created": time.time()
    }
    agents_list.append(agent)
    _save_agents(agents_list)
    return jsonify(agent), 201


@app.route("/api/agents/<agent_id>", methods=["PUT"])
def update_agent(agent_id):
    agent = _get_agent(agent_id)
    if not agent:
        return jsonify({"error": "智能体不存在"}), 404
    data = request.get_json()
    if "name" in data:
        agent["name"] = data["name"].strip()
    if "avatar" in data:
        agent["avatar"] = data["avatar"]
    if "system_prompt" in data:
        agent["system_prompt"] = data["system_prompt"]
    if "model" in data:
        agent["model"] = data["model"]
    if "provider" in data:
        agent["provider"] = data["provider"]
    if "base_url" in data:
        agent["base_url"] = data["base_url"]
    if "callable" in data:
        agent["callable"] = data["callable"]
    if "slug" in data:
        agent["slug"] = data["slug"]
    if "when_to_call" in data:
        agent["when_to_call"] = data["when_to_call"]
    _save_agents(agents_list)
    return jsonify(agent)


@app.route("/api/agents/<agent_id>", methods=["DELETE"])
def delete_agent(agent_id):
    global agents_list
    agents_list = [a for a in agents_list if a["id"] != agent_id]
    _save_agents(agents_list)
    return jsonify({"status": "ok"})


@app.route("/api/agents/upload-avatar", methods=["POST"])
def upload_avatar():
    if "file" not in request.files:
        return jsonify({"error": "没有文件"}), 400
    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "没有选择文件"}), 400
    if not _allowed_file(file.filename):
        return jsonify({"error": "不支持的文件格式，允许: png, jpg, jpeg, gif, webp, svg"}), 400
    ext = file.filename.rsplit(".", 1)[1].lower()
    filename = str(uuid.uuid4())[:12] + "." + ext
    filepath = os.path.join(UPLOAD_DIR, filename)
    file.save(filepath)
    url = "/static/uploads/" + filename
    return jsonify({"url": url}), 201


DOC_EXTENSIONS = {
    "txt", "md", "log", "json", "xml", "html", "csv",
    "py", "js", "ts", "java", "c", "cpp", "go", "rs", "sh",
    "yaml", "yml", "ini", "conf", "cfg", "toml",
    "pdf", "docx", "xlsx"
}

def _extract_text(filepath, ext):
    if ext == "pdf":
        try:
            from PyPDF2 import PdfReader
            reader = PdfReader(filepath)
            pages = []
            for i, page in enumerate(reader.pages):
                text = page.extract_text()
                if text:
                    pages.append(f"[第{i+1}页]\n{text}")
            return "\n\n".join(pages) if pages else "[PDF 无法提取文本内容]"
        except Exception as e:
            return f"[PDF 解析失败: {e}]"

    if ext == "docx":
        try:
            from docx import Document
            doc = Document(filepath)
            paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
            return "\n".join(paragraphs) if paragraphs else "[Word 文档内容为空]"
        except Exception as e:
            return f"[Word 解析失败: {e}]"

    if ext == "xlsx":
        try:
            from openpyxl import load_workbook
            wb = load_workbook(filepath, read_only=True, data_only=True)
            sheets = []
            for ws in wb.worksheets:
                rows = []
                for row in ws.iter_rows(values_only=True):
                    cells = [str(c) if c is not None else "" for c in row]
                    rows.append(" | ".join(cells))
                if rows:
                    sheets.append(f"[工作表: {ws.title}]\n" + "\n".join(rows))
            wb.close()
            return "\n\n".join(sheets) if sheets else "[Excel 文件内容为空]"
        except Exception as e:
            return f"[Excel 解析失败: {e}]"

    if ext == "csv":
        try:
            with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                reader = csv.reader(f)
                rows = [" | ".join(row) for row in reader]
            return "\n".join(rows) if rows else "[CSV 文件内容为空]"
        except Exception as e:
            return f"[CSV 解析失败: {e}]"

    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except Exception as e:
        return f"[文件读取失败: {e}]"


@app.route("/api/upload-doc", methods=["POST"])
def upload_doc():
    if "file" not in request.files:
        return jsonify({"error": "没有文件"}), 400
    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "没有选择文件"}), 400
    ext = file.filename.rsplit(".", 1)[1].lower() if "." in file.filename else ""
    if ext and ext not in DOC_EXTENSIONS:
        supported = "PDF、Word(.docx)、Excel(.xlsx)、CSV、TXT、Markdown、代码文件"
        return jsonify({"error": f"不支持的文件格式: .{ext}，支持: {supported}"}), 400
    if not ext:
        ext = "txt"
    filename = str(uuid.uuid4())[:12] + "." + ext
    filepath = os.path.join(UPLOAD_DIR, filename)
    file.save(filepath)
    text = _extract_text(filepath, ext)
    max_chars = 100000
    truncated = False
    if len(text) > max_chars:
        text = text[:max_chars]
        truncated = True
    try:
        os.remove(filepath)
    except Exception:
        pass
    return jsonify({
        "filename": file.filename,
        "text": text,
        "char_count": len(text),
        "truncated": truncated
    })


@app.route("/api/current-agent", methods=["GET"])
def get_current_agent():
    global current_agent_id
    return jsonify({"agent_id": current_agent_id})


@app.route("/api/current-agent", methods=["PUT"])
def set_current_agent():
    global current_agent_id
    data = request.get_json()
    current_agent_id = data.get("agent_id", None)
    return jsonify({"status": "ok", "agent_id": current_agent_id})


# ==================== 对话 API ====================

@app.route("/api/conversations", methods=["GET"])
def list_conversations():
    result = []
    ordered = sorted(conversations.values(),
                     key=lambda x: (1 if x.get("pinned") else 0, x["created"]),
                     reverse=True)
    for c in ordered:
        result.append({"id": c["id"], "title": c["title"],
                       "agent_id": c.get("agent_id"), "pinned": bool(c.get("pinned"))})
    return jsonify(result)


@app.route("/api/conversations", methods=["POST"])
def create_conversation():
    data = request.get_json() if request.is_json else {}
    agent_id = data.get("agent_id", current_agent_id)
    cid = _new_conversation(agent_id)
    conv = conversations[cid]
    return jsonify({"id": conv["id"], "title": conv["title"], "agent_id": conv.get("agent_id"), "pinned": bool(conv.get("pinned"))})


@app.route("/api/conversations/<cid>", methods=["DELETE"])
def delete_conversation(cid):
    if cid in conversations:
        del conversations[cid]
        _save_conversations()
    return jsonify({"status": "ok"})


@app.route("/api/conversations/<cid>/title", methods=["PUT"])
def rename_conversation(cid):
    conv = _get_conv(cid)
    if not conv:
        return jsonify({"error": "对话不存在"}), 404
    data = request.get_json()
    conv["title"] = data.get("title", "新对话")[:50]
    _save_conversations()
    return jsonify({"status": "ok"})


@app.route("/api/conversations/<cid>/pin", methods=["PUT"])
def pin_conversation(cid):
    conv = _get_conv(cid)
    if not conv:
        return jsonify({"error": "对话不存在"}), 404
    data = request.get_json() or {}
    conv["pinned"] = bool(data.get("pinned"))
    _save_conversations()
    return jsonify({"status": "ok", "pinned": conv["pinned"]})


@app.route("/api/conversations/<cid>/messages", methods=["GET"])
def get_messages(cid):
    conv = _get_conv(cid)
    if not conv:
        return jsonify({"error": "对话不存在"}), 404
    msgs = [m for m in conv["history"] if m["role"] != "system"]
    return jsonify(msgs)


@app.route("/api/conversations/<cid>/agent", methods=["PUT"])
def update_conversation_agent(cid):
    conv = _get_conv(cid)
    if not conv:
        return jsonify({"error": "对话不存在"}), 404
    data = request.get_json()
    new_agent_id = data.get("agent_id", None)
    conv["agent_id"] = new_agent_id
    conv["history"] = [m for m in conv["history"] if m["role"] != "system"]
    system_content = _get_system_content(new_agent_id)
    if system_content:
        conv["history"].insert(0, {"role": "system", "content": system_content})
    _save_conversations()
    return jsonify({"status": "ok", "agent_id": new_agent_id})


@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json()
    cid = data.get("conversation_id", "")
    user_input = data.get("message", "").strip()
    images = data.get("images", [])
    web_search_on = bool(data.get("web_search", False))
    is_ask_answer = bool(data.get("ask_answer", False))

    if not user_input and not images:
        return jsonify({"error": "消息不能为空"}), 400

    if not runtime_config["api_key"]:
        return jsonify({"error": "未配置 API Key，请先在设置中配置"}), 400

    conv = _get_conv(cid)
    if not conv:
        return jsonify({"error": "对话不存在"}), 404

    agent_id = conv.get("agent_id")
    chat_cfg = _get_chat_config(agent_id)
    if not chat_cfg["model"]:
        return jsonify({"error": "当前未选择模型，请先选择一个可用模型"}), 400

    history = conv["history"]
    mgr = HistoryManager(history, runtime_config["max_history_rounds"], "AI")

    if images:
        content_blocks = []
        if user_input:
            content_blocks.append({"type": "text", "text": user_input})
        for img_data in images:
            content_blocks.append({"type": "image_url", "image_url": {"url": img_data}})
        mgr.add_user_message(content_blocks)
    elif is_ask_answer:
        mgr.add_user_message(ASK_ANSWER_PREFIX + user_input)
    else:
        mgr.add_user_message(user_input)

    max_size_kb = runtime_config.get("max_context_size_kb", 0)
    if max_size_kb > 0 and not runtime_config.get("auto_compress", False):
        max_bytes = int(max_size_kb * 1024)
        while len(json.dumps(history, ensure_ascii=False).encode("utf-8")) > max_bytes:
            non_sys = [i for i, m in enumerate(history) if m["role"] != "system"]
            if len(non_sys) <= 1:
                break
            history.pop(non_sys[0])


    non_sys = [m for m in history if m["role"] != "system"]
    if len(non_sys) == 1:
        title_text = user_input if user_input else ("[图片]" if images else "新对话")
        conv["title"] = title_text[:30]

    callable_agents = _get_callable_agents()
    callable_prompt = _build_callable_prompt(callable_agents)

    def _build_request_history():
        date_note = ("\n\n【当前真实日期】今天是 " + web_search._current_date_str()
                     + "（由系统提供，准确无误）。涉及今天/日期/时效的问题一律以此为准。")
        extra = (callable_prompt or "") + ASK_PROMPT + date_note
        req_history = []
        for m in history:
            c = m.get("content")
            if isinstance(c, str) and c.startswith(ASK_ANSWER_PREFIX):
                m = dict(m)
                m["content"] = c[len(ASK_ANSWER_PREFIX):]
            req_history.append(m)
        sys_idx = next((i for i, m in enumerate(req_history) if m["role"] == "system"), -1)
        if sys_idx >= 0:
            req_history[sys_idx] = dict(req_history[sys_idx])
            req_history[sys_idx]["content"] = req_history[sys_idx]["content"] + extra
        else:
            req_history.insert(0, {"role": "system", "content": extra.strip()})
        return req_history

    def _inject_search(req_history, search_result):
        if not (search_result and search_result.get("context")):
            return req_history
        prompt = web_search.build_search_prompt(user_input, search_result)
        if not prompt:
            return req_history
        new_hist = list(req_history)
        last_user = next((i for i in range(len(new_hist) - 1, -1, -1)
                          if new_hist[i]["role"] == "user"), -1)
        if last_user >= 0:
            new_hist[last_user] = dict(new_hist[last_user])
            content = new_hist[last_user]["content"]
            if isinstance(content, str):
                new_hist[last_user]["content"] = prompt
            elif isinstance(content, list):
                blocks = list(content)
                replaced = False
                for j, b in enumerate(blocks):
                    if isinstance(b, dict) and b.get("type") == "text":
                        nb = dict(b)
                        nb["text"] = prompt
                        blocks[j] = nb
                        replaced = True
                        break
                if not replaced:
                    blocks.insert(0, {"type": "text", "text": prompt})
                new_hist[last_user]["content"] = blocks
        return new_hist

    stream_state = {"full_reply": "", "saved": False, "request_sent": False, "cancel": threading.Event(), "upstream_resp": None, "search_result": None}

    def _llm_call(messages):
        try:
            url = chat_cfg["base_url"].rstrip("/") + "/chat/completions"
            headers, payload = build_request_payload(
                chat_cfg["api_key"], messages, chat_cfg["model"], temperature=0.3, stream=False
            )
            r = requests.post(url, json=payload, headers=headers, timeout=(10, 60))
            if r.status_code != 200:
                return ""
            data = r.json()
            return data["choices"][0]["message"].get("content", "") or ""
        except Exception:
            return ""

    def _run_agentic_search(q_out):
        try:
            q_out.put(("status", "正在判断是否需要联网…"))
            if not web_search.should_search(user_input, _llm_call):
                q_out.put(("skip", None))
                return
            count = runtime_config.get("web_search_count", 5)
            result = web_search.agentic_search(
                user_input, _llm_call, max_results=count, max_rounds=1,
                progress=lambda msg: q_out.put(("status", msg)),
            )
            q_out.put(("done", result))
        except Exception:
            q_out.put(("done", None))

    def generate():
        try:
            search_result = None
            if web_search_on and user_input:
                q_out = queue.Queue()
                worker = threading.Thread(target=_run_agentic_search, args=(q_out,), daemon=True)
                worker.start()
                skipped = False
                while True:
                    if stream_state["cancel"].is_set():
                        break
                    try:
                        kind, val = q_out.get(timeout=0.2)
                    except queue.Empty:
                        continue
                    if kind == "status":
                        st = json.dumps({"search_status": val}, ensure_ascii=False)
                        yield f"data: {st}\n\n"
                    elif kind == "skip":
                        skipped = True
                        break
                    elif kind == "done":
                        search_result = val
                        break
                stream_state["search_result"] = search_result
                if skipped:
                    st = json.dumps({"search_status": "判断本次无需联网，直接作答"}, ensure_ascii=False)
                    yield f"data: {st}\n\n"
                elif not (search_result and search_result.get("ok")):
                    st = json.dumps({"search_status": "联网检索未获得有效结果，将基于已有知识回答"}, ensure_ascii=False)
                    yield f"data: {st}\n\n"
            resp = send_chat_request(
                chat_cfg["base_url"],
                chat_cfg["api_key"],
                _inject_search(_build_request_history(), search_result),
                chat_cfg["model"]
            )
            stream_state["upstream_resp"] = resp
            stream_state["request_sent"] = True
            if resp.status_code != 200:
                mgr.rollback_user_message()
                stream_state["saved"] = True
                upstream_msg = ""
                try:
                    err_body = resp.json()
                    if isinstance(err_body, dict):
                        err_obj = err_body.get("error", err_body)
                        if isinstance(err_obj, dict):
                            upstream_msg = err_obj.get("message", "") or ""
                        elif isinstance(err_obj, str):
                            upstream_msg = err_obj
                except Exception:
                    try:
                        upstream_msg = (resp.text or "")[:300]
                    except Exception:
                        upstream_msg = ""
                low = upstream_msg.lower()
                vision_keywords = ("image", "vision", "multimodal", "multi-modal", "modality", "image_url", "not support")
                if images and (resp.status_code == 400 or any(k in low for k in vision_keywords)):
                    friendly = f"当前模型「{chat_cfg['model']}」不支持图片输入，请改用支持视觉的模型，或移除图片后重试。"
                elif upstream_msg:
                    friendly = f"请求失败 [{resp.status_code}]：{upstream_msg}"
                else:
                    friendly = f"请求失败 [{resp.status_code}]"
                error_data = json.dumps({"error": friendly}, ensure_ascii=False)
                yield f"data: {error_data}\n\n"
                return

            history.append({"role": "assistant", "content": ""})
            reasoning_buf = ""
            in_reasoning = False
            for line in resp.iter_lines(decode_unicode=True):
                if stream_state["cancel"].is_set():
                    break
                result = parse_stream_chunk_full(line)
                if result is None:
                    break
                c_text, r_text = result
                if r_text:
                    if not in_reasoning:
                        in_reasoning = True
                        rs_data = json.dumps({"reasoning_start": True}, ensure_ascii=False)
                        yield f"data: {rs_data}\n\n"
                    reasoning_buf += r_text
                    chunk_data = json.dumps({"reasoning": r_text}, ensure_ascii=False)
                    yield f"data: {chunk_data}\n\n"
                if c_text:
                    if in_reasoning:
                        in_reasoning = False
                        re_data = json.dumps({"reasoning_end": True}, ensure_ascii=False)
                        yield f"data: {re_data}\n\n"
                    stream_state["full_reply"] += c_text
                    history[-1]["content"] = stream_state["full_reply"]
                    chunk_data = json.dumps({"chunk": c_text}, ensure_ascii=False)
                    yield f"data: {chunk_data}\n\n"
            if in_reasoning and not stream_state["full_reply"]:
                stream_state["full_reply"] = reasoning_buf
                history[-1]["content"] = stream_state["full_reply"]

            full_reply = stream_state["full_reply"]
            if callable_agents and re.search(r"\[CALL:\S+?\]", full_reply):
                yield "data: \n\n"
                final_reply = _execute_agent_calls(full_reply)
                replace_data = json.dumps({"replace": final_reply}, ensure_ascii=False)
                yield f"data: {replace_data}\n\n"
                history[-1]["content"] = final_reply
                mgr._trim_history()
            else:
                mgr._trim_history()

            if runtime_config.get("auto_compress", False):
                thr_kb = runtime_config.get("compress_threshold_kb", 8)
                thr_bytes = int(thr_kb) * 1024 if thr_kb else 0
                if thr_bytes > 0 and _history_bytes(history) > thr_bytes:
                    try:
                        did = _compress_history(history, _llm_call, thr_bytes)
                    except Exception:
                        did = False
                    if did:
                        cmp_data = json.dumps({"compress": {"threshold_kb": int(thr_kb)}}, ensure_ascii=False)
                        yield f"data: {cmp_data}\n\n"

            ask_questions, ask_prefix = _parse_ask_block(stream_state["full_reply"])
            if ask_questions:
                ask_data = json.dumps({"ask": {"questions": ask_questions, "prefix": ask_prefix}}, ensure_ascii=False)
                yield f"data: {ask_data}\n\n"

            _sr = stream_state.get("search_result")
            if _sr and _sr.get("sources"):
                src_data = json.dumps({"sources": _sr["sources"]}, ensure_ascii=False)
                yield f"data: {src_data}\n\n"
            stream_state["saved"] = True
            _save_conversations()
            yield "data: [DONE]\n\n"

        except GeneratorExit:
            return
        except Exception as e:
            if not stream_state["saved"]:
                if not stream_state["full_reply"] and history and history[-1].get("role") == "assistant" and history[-1].get("content") == "":
                    history.pop()
                    mgr.rollback_user_message()
                stream_state["saved"] = True
                _save_conversations()
            error_data = json.dumps({"error": str(e)}, ensure_ascii=False)
            yield f"data: {error_data}\n\n"


    def on_close():
        stream_state["cancel"].set()
        upstream = stream_state.get("upstream_resp")
        if upstream:
            try:
                upstream.close()
            except Exception:
                pass
        if not stream_state["saved"]:
            if not stream_state["full_reply"] and history and history[-1].get("role") == "assistant" and history[-1].get("content") == "":
                history.pop()
                if not stream_state["request_sent"]:
                    mgr.rollback_user_message()
            stream_state["saved"] = True
            _save_conversations()


    resp = Response(stream_with_context(generate()), mimetype="text/event-stream")
    resp.call_on_close(on_close)
    return resp



@app.route("/api/conversations/<cid>/clear", methods=["POST"])
def clear_conversation(cid):
    conv = _get_conv(cid)
    if not conv:
        return jsonify({"error": "对话不存在"}), 404
    agent_id = conv.get("agent_id")
    conv["history"].clear()
    system_content = _get_system_content(agent_id)
    if system_content:
        conv["history"].append({"role": "system", "content": system_content})
    _save_conversations()
    return jsonify({"status": "ok"})


@app.route("/api/conversations/<cid>/retry", methods=["POST"])
def retry_conversation(cid):
    conv = _get_conv(cid)
    if not conv:
        return jsonify({"error": "对话不存在"}), 404
    history = conv["history"]
    removed_user_content = ""
    removed_images = []
    if history and history[-1]["role"] == "assistant":
        history.pop()
    if history and history[-1]["role"] == "user":
        raw = history.pop()["content"]
        if isinstance(raw, list):
            for block in raw:
                if block.get("type") == "text":
                    removed_user_content = block.get("text", "")
                elif block.get("type") == "image_url":
                    removed_images.append(block["image_url"]["url"])
        else:
            removed_user_content = raw
    _save_conversations()
    return jsonify({"status": "ok", "user_message": removed_user_content, "images": removed_images})


@app.route("/api/conversations/<cid>/undo", methods=["POST"])
def undo_conversation(cid):
    conv = _get_conv(cid)
    if not conv:
        return jsonify({"error": "对话不存在"}), 404
    data = request.get_json() or {}

    history = conv["history"]

    def _is_ask_answer(m):
        c = m.get("content")
        return isinstance(c, str) and c.startswith(ASK_ANSWER_PREFIX)

    visible_positions = [
        i for i, m in enumerate(history)
        if m.get("role") == "user" and not _is_ask_answer(m)
    ]

    cut_pos = None
    visible_index = data.get("visible_index", None)
    if visible_index is not None and visible_positions:
        idx = visible_index
        if idx < 0:
            idx = 0
        if idx >= len(visible_positions):
            idx = len(visible_positions) - 1
        cut_pos = visible_positions[idx]
    else:
        user_index = data.get("user_index", -1)
        all_user_positions = [i for i, m in enumerate(history) if m.get("role") == "user"]
        if all_user_positions:
            idx = user_index
            if idx < 0:
                idx = 0
            if idx >= len(all_user_positions):
                idx = len(all_user_positions) - 1
            cut_pos = all_user_positions[idx]

    if cut_pos is None:
        return jsonify({"status": "ok", "user_message": "", "images": []})
    removed_user_content = ""
    removed_images = []
    raw = history[cut_pos]["content"]
    if isinstance(raw, list):
        for block in raw:
            if block.get("type") == "text":
                removed_user_content = block.get("text", "")
            elif block.get("type") == "image_url":
                removed_images.append(block["image_url"]["url"])
    else:
        removed_user_content = raw

    if isinstance(removed_user_content, str) and removed_user_content.startswith(ASK_ANSWER_PREFIX):
        removed_user_content = removed_user_content[len(ASK_ANSWER_PREFIX):]

    del history[cut_pos:]
    _save_conversations()
    return jsonify({
        "status": "ok",
        "user_message": removed_user_content,
        "images": removed_images
    })
@app.route("/api/conversations/export", methods=["GET"])
def export_conversations():
    cid = request.args.get("id", "").strip()
    if cid:
        conv = _get_conv(cid)
        if not conv:
            return jsonify({"error": "对话不存在"}), 404
        data = [conv]
    else:
        data = list(conversations.values())
    payload = {
        "type": "ai_chat_conversations_export",
        "version": 1,
        "exported_at": int(time.time()),
        "count": len(data),
        "conversations": data
    }
    body = json.dumps(payload, ensure_ascii=False, indent=2)
    fname = "conversations_export_%d.json" % int(time.time())
    return Response(
        body,
        mimetype="application/json",
        headers={"Content-Disposition": "attachment; filename=%s" % fname}
    )


@app.route("/api/conversations/import", methods=["POST"])
def import_conversations():
    data = request.get_json(silent=True) or {}
    incoming = data.get("conversations")
    if incoming is None and isinstance(data, list):
        incoming = data
    if not isinstance(incoming, list):
        if isinstance(data.get("conversations"), list):
            incoming = data["conversations"]
        else:
            return jsonify({"error": "文件格式不正确，缺少 conversations 列表"}), 400

    mode = data.get("mode", "merge")
    imported = 0
    skipped = 0

    if mode == "replace":
        conversations.clear()

    for conv in incoming:
        if not isinstance(conv, dict):
            skipped += 1
            continue
        cid = conv.get("id")
        title = conv.get("title", "导入的对话")
        history = conv.get("history", [])
        if not isinstance(history, list):
            skipped += 1
            continue
        if not cid or cid in conversations:
            cid = str(uuid.uuid4())[:8]
        new_conv = {
            "id": cid,
            "title": str(title)[:50] if title else "导入的对话",
            "agent_id": conv.get("agent_id"),
            "pinned": bool(conv.get("pinned")),
            "created": conv.get("created", time.time()),
            "history": history
        }
        conversations[cid] = new_conv
        imported += 1

    if imported > 0:
        _save_conversations()
    return jsonify({"status": "ok", "imported": imported, "skipped": skipped})



if __name__ == "__main__":
    print(f"🌐 Web 聊天界面启动中...")
    print(f"📎 打开浏览器访问: http://localhost:{PORT}")
    app.run(host=HOST, port=PORT, debug=False, threaded=True)
