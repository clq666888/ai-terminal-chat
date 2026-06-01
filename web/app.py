#!/usr/bin/env python3
import sys
import os
import json
import uuid
import time
from flask import Flask, render_template, request, Response, jsonify, stream_with_context, send_from_directory

from chat_core import load_api_key, load_system_prompt, HistoryManager, send_chat_request, parse_stream_chunk, build_request_payload
import requests

# ==================== 配置区 ====================
BASE_URL = "https://api.deepseek.com/v1/chat/completions"
KEY_FILE_PATH = "/home/sti/apikey.txt"
MODEL = "deepseek-chat"
AI_NAME = "AI Chat"
MAX_HISTORY_ROUNDS = 50
HOST = "0.0.0.0"
PORT = 8080
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings.json")
AGENTS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "agents.json")
UPLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "uploads")
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp", "svg"}
# =============================================================

PROVIDER_MODELS = {
    "deepseek": {
        "name": "DeepSeek",
        "base_url": "https://api.deepseek.com/v1/chat/completions",
        "models": ["deepseek-chat", "deepseek-reasoner", "deepseek-v4-pro", "deepseek-v4-flash"]
    },
    "openai": {
        "name": "OpenAI",
        "base_url": "https://api.openai.com/v1/chat/completions",
        "models": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo", "o1", "o1-mini", "o3-mini"]
    },
    "claude": {
        "name": "Claude (via API proxy)",
        "base_url": "https://api.anthropic.com/v1/chat/completions",
        "models": ["claude-sonnet-4-20250514", "claude-3-5-sonnet-20241022", "claude-3-haiku-20240307", "claude-3-opus-20240229"]
    },
    "gemini": {
        "name": "Google Gemini (OpenAI 兼容)",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
        "models": ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.0-flash", "gemini-1.5-pro"]
    },
    "qwen": {
        "name": "通义千问",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
        "models": ["qwen-max", "qwen-plus", "qwen-turbo", "qwen-long"]
    },
    "zhipu": {
        "name": "智谱 GLM",
        "base_url": "https://open.bigmodel.cn/api/paas/v4/chat/completions",
        "models": ["glm-4-plus", "glm-4", "glm-4-flash", "glm-4-long"]
    },
    "moonshot": {
        "name": "Moonshot / Kimi",
        "base_url": "https://api.moonshot.cn/v1/chat/completions",
        "models": ["moonshot-v1-128k", "moonshot-v1-32k", "moonshot-v1-8k"]
    },
    "custom": {
        "name": "自定义",
        "base_url": "",
        "models": []
    }
}

app = Flask(__name__)
os.makedirs(UPLOAD_DIR, exist_ok=True)


def _default_config():
    return {
        "base_url": BASE_URL,
        "api_key": "",
        "key_file_path": KEY_FILE_PATH,
        "model": MODEL,
        "provider": "deepseek",
        "max_history_rounds": MAX_HISTORY_ROUNDS,
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


def _allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


runtime_config = _load_config()
agents_list = _load_agents()
conversations = {}
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
        "max_history_rounds": runtime_config["max_history_rounds"]
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
    return jsonify({"status": "ok"})


@app.route("/api/conversations/<cid>/title", methods=["PUT"])
def rename_conversation(cid):
    conv = _get_conv(cid)
    if not conv:
        return jsonify({"error": "对话不存在"}), 404
    data = request.get_json()
    conv["title"] = data.get("title", "新对话")[:50]
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
    return jsonify({"status": "ok", "agent_id": new_agent_id})


@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json()
    cid = data.get("conversation_id", "")
    user_input = data.get("message", "").strip()

    if not user_input:
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
    mgr.add_user_message(user_input)

    non_sys = [m for m in history if m["role"] != "system"]
    if len(non_sys) == 1:
        conv["title"] = user_input[:30]

    def generate():
        try:
            resp = send_chat_request(
                chat_cfg["base_url"],
                chat_cfg["api_key"],
                history,
                chat_cfg["model"]
            )
            if resp.status_code != 200:
                mgr.rollback_user_message()
                error_data = json.dumps({"error": f"请求失败 [{resp.status_code}]"}, ensure_ascii=False)
                yield f"data: {error_data}\n\n"
                return

            full_reply = ""
            for line in resp.iter_lines(decode_unicode=True):
                content = parse_stream_chunk(line)
                if content is None:
                    break
                if content:
                    full_reply += content
                    yield f"data: {content}\n\n"

            mgr.save_assistant_reply(full_reply)
            yield "data: [DONE]\n\n"

        except Exception as e:
            mgr.rollback_user_message()
            error_data = json.dumps({"error": str(e)}, ensure_ascii=False)
            yield f"data: {error_data}\n\n"

    return Response(stream_with_context(generate()), mimetype="text/event-stream")


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
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    print(f"🌐 Web 聊天界面启动中...")
    print(f"📎 打开浏览器访问: http://localhost:{PORT}")
    app.run(host=HOST, port=PORT, debug=False)
