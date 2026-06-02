#!/usr/bin/env python3
import sys
import os
import json
import uuid
import time
import threading
from flask import Flask, render_template, request, Response, jsonify, stream_with_context, send_from_directory

from chat_core import load_api_key, load_system_prompt, HistoryManager, send_chat_request, parse_stream_chunk, parse_stream_chunk_full, build_request_payload
import requests
import re
import csv
import io

# ==================== 配置区 ====================
BASE_URL = "https://api.deepseek.com"
KEY_FILE_PATH = "/home/sti/apikey.txt"
MODEL = "deepseek-v4-flash"
AI_NAME = "AI Chat"
MAX_HISTORY_ROUNDS = 50
HOST = "0.0.0.0"
PORT = 8080
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings.json")
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
        "key_file_path": KEY_FILE_PATH,
        "model": MODEL,
        "provider": "deepseek",
        "max_history_rounds": MAX_HISTORY_ROUNDS,
        "max_context_size_kb": 0,
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
            if "_api_key" in saved and not cfg["api_key"]:
                cfg["api_key"] = saved["_api_key"]
        except Exception:
            pass
    if not cfg["api_key"] and cfg["key_file_path"]:
        try:
            cfg["api_key"] = load_api_key(cfg["key_file_path"])
        except RuntimeError:
            pass
    return cfg


def _save_config(cfg):
    save_data = {}
    for k, v in cfg.items():
        if k == "api_key":
            continue
        save_data[k] = v
    if cfg.get("api_key") and not cfg.get("key_file_path"):
        save_data["api_key_masked"] = cfg["api_key"][:8] + "***"
        save_data["_api_key"] = cfg["api_key"]
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
            "api_key": runtime_config["api_key"]
        }
    return {
        "base_url": runtime_config["base_url"],
        "model": runtime_config["model"],
        "api_key": runtime_config["api_key"]
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
        "created": time.time()
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


@app.route("/api/settings", methods=["GET"])
def get_settings():
    return jsonify({
        "provider": runtime_config["provider"],
        "base_url": runtime_config["base_url"],
        "model": runtime_config["model"],
        "has_api_key": bool(runtime_config["api_key"]),
        "key_file_path": runtime_config["key_file_path"],
        "max_history_rounds": runtime_config["max_history_rounds"],
        "max_context_size_kb": runtime_config.get("max_context_size_kb", 0)
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
    if "api_key" in data and data["api_key"]:
        runtime_config["api_key"] = data["api_key"].strip()
        runtime_config["key_file_path"] = ""
    if "key_file_path" in data and data["key_file_path"]:
        path = data["key_file_path"].strip()
        try:
            runtime_config["api_key"] = load_api_key(path)
            runtime_config["key_file_path"] = path
        except RuntimeError as e:
            return jsonify({"error": str(e)}), 400
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
    for c in sorted(conversations.values(), key=lambda x: x["created"], reverse=True):
        result.append({"id": c["id"], "title": c["title"], "agent_id": c.get("agent_id")})
    return jsonify(result)


@app.route("/api/conversations", methods=["POST"])
def create_conversation():
    data = request.get_json() if request.is_json else {}
    agent_id = data.get("agent_id", current_agent_id)
    cid = _new_conversation(agent_id)
    conv = conversations[cid]
    return jsonify({"id": conv["id"], "title": conv["title"], "agent_id": conv.get("agent_id")})


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

    if not user_input and not images:
        return jsonify({"error": "消息不能为空"}), 400

    if not runtime_config["api_key"]:
        return jsonify({"error": "未配置 API Key，请先在设置中配置"}), 400

    conv = _get_conv(cid)
    if not conv:
        return jsonify({"error": "对话不存在"}), 404

    agent_id = conv.get("agent_id")
    chat_cfg = _get_chat_config(agent_id)

    history = conv["history"]
    mgr = HistoryManager(history, runtime_config["max_history_rounds"], "AI")

    if images:
        content_blocks = []
        if user_input:
            content_blocks.append({"type": "text", "text": user_input})
        for img_data in images:
            content_blocks.append({"type": "image_url", "image_url": {"url": img_data}})
        mgr.add_user_message(content_blocks)
    else:
        mgr.add_user_message(user_input)

    max_size_kb = runtime_config.get("max_context_size_kb", 0)
    if max_size_kb > 0:
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
        if not callable_prompt:
            return history
        req_history = list(history)
        sys_idx = next((i for i, m in enumerate(req_history) if m["role"] == "system"), -1)
        if sys_idx >= 0:
            req_history[sys_idx] = dict(req_history[sys_idx])
            req_history[sys_idx]["content"] = req_history[sys_idx]["content"] + callable_prompt
        else:
            req_history.insert(0, {"role": "system", "content": callable_prompt.strip()})
        return req_history

    stream_state = {"full_reply": "", "saved": False, "request_sent": False, "cancel": threading.Event(), "upstream_resp": None}

    def generate():
        try:
            resp = send_chat_request(
                chat_cfg["base_url"],
                chat_cfg["api_key"],
                _build_request_history(),
                chat_cfg["model"]
            )
            stream_state["upstream_resp"] = resp
            stream_state["request_sent"] = True
            if resp.status_code != 200:
                mgr.rollback_user_message()
                stream_state["saved"] = True
                error_data = json.dumps({"error": f"请求失败 [{resp.status_code}]"}, ensure_ascii=False)
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


if __name__ == "__main__":
    print(f"🌐 Web 聊天界面启动中...")
    print(f"📎 打开浏览器访问: http://localhost:{PORT}")
    app.run(host=HOST, port=PORT, debug=False, threaded=True)
