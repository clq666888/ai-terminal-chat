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

from chat_core import load_api_key, load_system_prompt, HistoryManager, send_chat_request, parse_stream_chunk, parse_stream_chunk_full, build_request_payload, parse_stream_usage
import requests
import re
import csv
import io

# ==================== 配置区 ====================
MAX_HISTORY_ROUNDS = 50
HOST = "0.0.0.0"
PORT = 8080
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings.json")
APIKEY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".apikey")
AGENTS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "agents.json")
CONVERSATIONS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "conversations.json")
PROJECTS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "projects.json")
TOKEN_STATS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "token_stats.json")
UPLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "uploads")
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp", "svg"}
# =============================================================

_SHUTDOWN_EVENT = threading.Event()

PROVIDER_MODELS = {
    "deepseek": {
        "name": "DeepSeek",
        "base_url": "https://api.deepseek.com",
        "models": ["deepseek-v4-flash", "deepseek-v4-pro", "deepseek-chat", "deepseek-reasoner"]
    },
    "openai": {
        "name": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "models": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo", "o1", "o1-mini", "o3-mini", "openai/gpt-image-2"]
    },
    "claude": {
        "name": "Claude (via API proxy)",
        "base_url": "https://api.anthropic.com/v1",
        "models": ["claude-sonnet-4-20250514", "claude-3-5-sonnet-20241022", "claude-3-haiku-20240307", "claude-3-opus-20240229"]
    },
    "gemini": {
        "name": "Google Gemini (OpenAI 兼容)",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "models": ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.0-flash", "gemini-1.5-pro", "google/gemini-2.5-flash-image"]
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

IMAGE_MODEL_KEYWORDS = ("gpt-image", "dall-e", "dall_e", "-image", "image-preview", "flux", "stable-diffusion", "sd-", "cogview", "wanx", "seedream", "kolors", "ideogram", "midjourney")


def _is_image_model(model):
    if not model:
        return False
    low = str(model).lower()
    return any(k in low for k in IMAGE_MODEL_KEYWORDS)


def _extract_message_images(message):
    if not isinstance(message, dict):
        return []
    imgs = message.get("images")
    out = []
    if isinstance(imgs, list):
        for it in imgs:
            if isinstance(it, dict):
                url = it.get("url") or it.get("image_url") or ""
                if isinstance(url, dict):
                    url = url.get("url", "")
                if url:
                    out.append(url)
            elif isinstance(it, str) and it:
                out.append(it)
    return out


def _request_image_generation(chat_cfg, messages):
    url = chat_cfg["base_url"].rstrip("/")
    if not url.endswith("/chat/completions"):
        if re.search(r"/v\d+\w*(/[\w-]+)?$", url):
            url = url + "/chat/completions"
        else:
            url = url + "/v1/chat/completions"
    headers = {
        "Authorization": "Bearer " + chat_cfg["api_key"],
        "Content-Type": "application/json"
    }
    guide = {
        "role": "system",
        "content": "You are an image generation model. For every user request, you MUST actually generate and return an image, not just describe it in text. If the user's request is in Chinese, understand it and still produce the image."
    }
    msgs = list(messages)
    if not (msgs and msgs[0].get("role") == "system"):
        msgs = [guide] + msgs
    else:
        msgs = [{"role": "system", "content": (msgs[0].get("content") or "") + "\n\n" + guide["content"]}] + msgs[1:]
    payload = {"model": chat_cfg["model"], "messages": msgs, "stream": False}
    r = requests.post(url, json=payload, headers=headers, timeout=(10, 180))
    return r


app = Flask(__name__)
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0
app.config["JSON_AS_ASCII"] = False
APP_START_TIME = str(int(time.time()))

@app.context_processor
def inject_cache_version():
    return {"cache_version": APP_START_TIME}
os.makedirs(UPLOAD_DIR, exist_ok=True)


def _default_config():
    return {
        "base_url": "",
        "api_key": "",
        "api_keys": {},
        "model": "",
        "model_id": "",
        "provider": "deepseek",
        "max_history_rounds": MAX_HISTORY_ROUNDS,
        "max_context_size_kb": 0,
        "auto_compress": False,
        "compress_threshold_kb": 128,
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
    cfg["api_key"] = cfg["api_keys"].get(cfg.get("model_id", ""), "")
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
    except Exception as e:
        print("[persist] API Key 文件写入失败:", type(e).__name__)


def _get_key_for(model_id):
    if not model_id:
        return ""
    return runtime_config.get("api_keys", {}).get(model_id, "")


def _set_key_for(model_id, key):
    if not model_id:
        return
    if "api_keys" not in runtime_config or not isinstance(runtime_config["api_keys"], dict):
        runtime_config["api_keys"] = {}
    runtime_config["api_keys"][model_id] = (key or "").strip()
    _save_api_keys(runtime_config["api_keys"])


def _del_key_for(model_id):
    if not model_id:
        return
    keys = runtime_config.get("api_keys", {})
    if isinstance(keys, dict) and model_id in keys:
        del keys[model_id]
        _save_api_keys(keys)


def _save_config(cfg):
    save_data = {}
    for k, v in cfg.items():
        if k in ("api_key", "api_keys"):
            continue
        save_data[k] = v
    _atomic_save_json(CONFIG_FILE, save_data)


def _make_default_project_agent():
    return {
        "id": str(uuid.uuid4())[:8],
        "name": "通用助手",
        "avatar": "",
        "system_prompt": "",
        "model": "",
        "provider": "",
        "base_url": "",
        "callable": False,
        "slug": "",
        "when_to_call": "",
        "created": time.time()
    }


def _load_projects():
    data = []
    if os.path.exists(PROJECTS_FILE):
        try:
            with open(PROJECTS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = []
    for proj in data:
        if not isinstance(proj.get("agents"), list) or not proj.get("agents"):
            proj["agents"] = [_make_default_project_agent()]
    return data


def _save_projects(projects):
    _atomic_save_json(PROJECTS_FILE, projects)


def _load_agents():
    if os.path.exists(AGENTS_FILE):
        try:
            with open(AGENTS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return []


def _save_agents(agents):
    _atomic_save_json(AGENTS_FILE, agents)


def _load_conversations():
    if os.path.exists(CONVERSATIONS_FILE):
        try:
            with open(CONVERSATIONS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return {c["id"]: c for c in data}
        except Exception:
            pass
    return {}


_save_lock = threading.Lock()
_conv_locks = {}
_conv_locks_guard = threading.Lock()


def _atomic_save_json(path, data, indent=2):
    try:
        with _save_lock:
            tmp = path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=indent)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, path)
    except Exception as e:
        print("[persist] 写入失败:", path, repr(e))

# 后台生成注册表：cid -> {"events":[...], "cond":Condition, "done":bool, "cancel":Event}
# 让 AI 生成脱离前端连接，切换对话/刷新页面都不会中断后台生成
ACTIVE_STREAMS = {}
_active_guard = threading.Lock()


def _get_active_stream(cid):
    with _active_guard:
        return ACTIVE_STREAMS.get(cid)


def _register_active_stream(cid, cancel_event, is_image=False):
    st = {"events": [], "cond": threading.Condition(), "done": False, "cancel": cancel_event, "is_image": bool(is_image)}
    with _active_guard:
        ACTIVE_STREAMS[cid] = st
    return st


def _push_active_event(st, ev):
    with st["cond"]:
        st["events"].append(ev)
        st["cond"].notify_all()


def _finish_active_stream(cid, st):
    with st["cond"]:
        st["done"] = True
        st["cond"].notify_all()
    with _active_guard:
        if ACTIVE_STREAMS.get(cid) is st:
            del ACTIVE_STREAMS[cid]


def _observe_active_stream(st):
    idx = 0
    while True:
        with st["cond"]:
            while idx >= len(st["events"]) and not st["done"]:
                st["cond"].wait(timeout=30)
            while idx < len(st["events"]):
                ev = st["events"][idx]
                idx += 1
                yield ev
            if st["done"] and idx >= len(st["events"]):
                return


def _get_conv_lock(cid):
    with _conv_locks_guard:
        lock = _conv_locks.get(cid)
        if lock is None:
            lock = threading.Lock()
            _conv_locks[cid] = lock
        return lock


import datetime as _dt

_token_stats_lock = threading.Lock()


def _load_token_stats():
    try:
        with open(TOKEN_STATS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict) and isinstance(data.get("daily"), dict):
            return data
    except Exception:
        pass
    return {"daily": {}}


def _save_token_stats(data):
    try:
        tmp = TOKEN_STATS_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, TOKEN_STATS_FILE)
    except Exception:
        pass


def _record_token_usage(usage):
    if not usage:
        return
    total = int(usage.get("total_tokens") or 0)
    prompt = int(usage.get("prompt_tokens") or 0)
    completion = int(usage.get("completion_tokens") or 0)
    if total <= 0:
        total = prompt + completion
    if total <= 0:
        return
    day = _dt.date.today().isoformat()
    with _token_stats_lock:
        data = _load_token_stats()
        d = data["daily"].get(day) or {"total": 0, "prompt": 0, "completion": 0}
        d["total"] += total
        d["prompt"] += prompt
        d["completion"] += completion
        data["daily"][day] = d
        _save_token_stats(data)


def _conv_token_total(conv):
    t = 0
    for m in conv.get("history", []):
        u = m.get("usage")
        if isinstance(u, dict):
            t += int(u.get("total_tokens") or 0)
    return t


def _save_conversations():
    try:
        with _save_lock:
            data = list(conversations.values())
            tmp = CONVERSATIONS_FILE + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, CONVERSATIONS_FILE)
    except Exception as e:
        print("[persist] 写入失败: conversations", repr(e))


def _allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


import web_search

runtime_config = _load_config()
agents_list = _load_agents()
conversations = _load_conversations()
projects_list = _load_projects()
current_agent_id = None


def _get_agent(agent_id):
    if not agent_id:
        return None
    for a in agents_list:
        if a["id"] == agent_id:
            return a
    for proj in projects_list:
        for a in (proj.get("agents") or []):
            if a.get("id") == agent_id:
                return a
    return None


def _get_project_agents(project_id):
    project = _get_project(project_id)
    if not project:
        return []
    return project.get("agents") or []


def _get_default_project_agent_id(project_id):
    agents = _get_project_agents(project_id)
    return agents[0]["id"] if agents else None


def _agent_belongs_to_scope(agent_id, project_id):
    if not agent_id:
        return True
    if project_id:
        return any(a.get("id") == agent_id for a in _get_project_agents(project_id))
    return any(a.get("id") == agent_id for a in agents_list)


def _get_project(project_id):
    if not project_id:
        return None
    for p in projects_list:
        if p["id"] == project_id:
            return p
    return None


def _get_system_content(agent_id=None, project_id=None):
    parts = []
    agent = _get_agent(agent_id)
    if agent and agent.get("system_prompt"):
        parts.append(agent["system_prompt"].strip())
    project = _get_project(project_id)
    if project and project.get("system_prompt") and project["system_prompt"].strip():
        parts.append("【项目背景】" + project["system_prompt"].strip())
    return "\n\n".join(parts)


def _get_chat_config(agent_id=None):
    agent = _get_agent(agent_id)
    if agent and agent.get("model"):
        base_url = agent.get("base_url", "") or runtime_config["base_url"]
        provider = agent.get("provider", "") or runtime_config["provider"]
        p = PROVIDER_MODELS.get(provider)
        if not base_url and p:
            base_url = p["base_url"]
        agent_mid = agent.get("model_id", "")
        api_key = _get_key_for(agent_mid) if agent_mid else _get_key_for(runtime_config.get("model_id", ""))
        return {
            "base_url": base_url,
            "model": agent["model"],
            "api_key": api_key
        }
    return {
        "base_url": runtime_config["base_url"],
        "model": runtime_config["model"],
        "api_key": _get_key_for(runtime_config.get("model_id", ""))
    }


def _get_callable_agents():
    return [a for a in agents_list if a.get("callable") and a.get("slug")]


def _build_callable_prompt(callable_agents):
    if not callable_agents:
        return ""
    lines = ["\n\n你可以调用以下智能体来协助完成任务："]
    for a in callable_agents:
        lines.append(f"- {a['slug']}（{a['name']}）: {a.get('when_to_call', '')}")
    lines.append("\n【重要】当需要某个智能体协助时，你必须使用 [CALL:英文标识名] 具体任务描述 [/CALL] 格式来触发实际调用。")
    lines.append("⚠️ 绝对不要自己扮演或模拟被调用智能体的回复——系统会自动执行调用并将真实结果返回给你。")
    lines.append("如果你假装是被调用智能体在说话，用户将无法获得真实的子智能体能力。")
    lines.append("【并行边界】你发起的多个调用是并行、互相独立执行的：被调用的子智能体彼此看不到对方，"
                 "前一个子智能体的产出不会自动传给后一个。因此你只应在“彼此无先后依赖、可各自独立完成”的子任务上发起调用。"
                 "如果任务存在“后一步必须基于前一步的产物”这种先后依赖（例如先出大纲再据此写正文），"
                 "不要把它拆成并行调用——这种带先后顺序的流程应由工作流模式处理，你可以直接告知用户改用工作流。")
    return "\n".join(lines)


ASK_ANSWER_PREFIX = "[[ASK_ANSWER]]"
HISTORY_SUMMARY_PREFIX = "[[HISTORY_SUMMARY]]"


def _history_bytes(history):
    try:
        stripped = []
        for m in history:
            c = m.get("content")
            if isinstance(c, list):
                blocks = []
                for b in c:
                    if isinstance(b, dict) and b.get("type") == "image_url":
                        blocks.append({"type": "image_url", "image_url": {"url": "[image]"}})
                    else:
                        blocks.append(b)
                stripped.append(dict(m, content=blocks))
            else:
                stripped.append(m)
        return len(json.dumps(stripped, ensure_ascii=False).encode("utf-8"))
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


def _friendly_upstream_error(status_code, upstream_msg, has_images=False):
    """把上游 API 的 HTTP 错误归类成 (错误码, 用户可读文案)。"""
    msg = (upstream_msg or "").strip()
    low = msg.lower()
    vision_keywords = ("image", "vision", "multimodal", "multi-modal", "modality", "image_url", "not support")
    if has_images and (status_code == 400 or any(k in low for k in vision_keywords)):
        return "E1001", "当前模型不支持图片输入。请改用支持视觉（多模态）的模型，或移除图片后重试。"
    tail = ("：" + msg) if msg else ""
    if status_code in (401, 403):
        return "E1002", f"接口鉴权失败 [{status_code}]。API Key 可能错误、已失效或无该模型权限，请到设置中检查 API Key{tail}"
    if status_code == 402:
        return "E1003", f"账户余额不足或欠费 [{status_code}]。请到对应服务商充值后重试{tail}"
    if status_code == 404:
        return "E1004", f"模型或接口地址不存在 [{status_code}]。请检查模型名称与 API 地址是否填写正确{tail}"
    if status_code == 429:
        return "E1005", f"请求过于频繁或已达额度上限 [{status_code}]。请稍等片刻再试，或检查服务商配额{tail}"
    if status_code in (408, 504):
        return "E1006", f"上游服务响应超时 [{status_code}]。可能是网络拥堵或服务繁忙，请稍后重试{tail}"
    if status_code == 400:
        return "E1007", f"请求参数被上游拒绝 [{status_code}]。可能是模型名、消息格式或参数不被支持{tail}"
    if 500 <= status_code < 600:
        return "E1008", f"上游服务出错 [{status_code}]。这是服务商一侧的问题，通常稍后重试即可恢复{tail}"
    return "E1000", f"请求失败 [{status_code}]{tail}"


def _friendly_network_error(exc):
    """把本地到上游的网络异常归类成 (错误码, 用户可读文案)。"""
    try:
        import requests as _rq
        exc_types = _rq.exceptions
    except Exception:
        exc_types = None
    name = type(exc).__name__
    detail = str(exc)[:200]
    if exc_types is not None:
        if isinstance(exc, exc_types.ConnectTimeout):
            return "E2001", "连接 API 服务器超时。请检查网络，或确认 API 地址是否可访问。"
        if isinstance(exc, exc_types.ReadTimeout):
            return "E2002", "等待 API 响应超时。模型可能生成太慢或服务繁忙，请稍后重试。"
        if isinstance(exc, exc_types.SSLError):
            return "E2003", "与 API 服务器建立安全连接失败（SSL 错误）。请检查 API 地址或网络代理设置。"
        if isinstance(exc, exc_types.ProxyError):
            return "E2004", "通过代理连接 API 失败。请检查本机代理设置。"
        if isinstance(exc, exc_types.ConnectionError):
            return "E2005", "无法连接到 API 服务器。请检查网络连接，以及 API 地址是否正确、是否可访问。"
        if isinstance(exc, exc_types.Timeout):
            return "E2006", "网络请求超时。请检查网络后重试。"
    return "E2000", f"网络请求异常（{name}）：{detail}"


def _classify_generate_error(exc):
    """流式生成过程中抛出的未预期异常 -> (错误码, 用户可读文案)。
    网络相关异常归到 E2xxx，其余归为通用 E9000。"""
    try:
        import requests as _rq
        if isinstance(exc, _rq.exceptions.RequestException):
            return _friendly_network_error(exc)
    except Exception:
        pass
    detail = str(exc)[:200]
    return "E9000", f"生成回复时发生未知错误，请重试。若反复出现可把错误码反馈给维护者。详情：{detail}"


def _lenient_json_loads(raw):
    """尽力解析可能不严格的 JSON（AI 输出常见：中文引号、尾逗号、括号未闭合）。失败返回 None。"""
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        pass
    s = raw
    s = s.replace("\u201c", '"').replace("\u201d", '"').replace("\u2018", "'").replace("\u2019", "'")
    s = re.sub(r",\s*([}\]])", r"\1", s)
    try:
        return json.loads(s)
    except Exception:
        pass
    in_str = False
    esc = False
    stack = []
    for ch in s:
        if esc:
            esc = False
            continue
        if ch == "\\":
            esc = True
            continue
        if ch == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if ch in "{[":
            stack.append(ch)
        elif ch == "}":
            if stack and stack[-1] == "{":
                stack.pop()
        elif ch == "]":
            if stack and stack[-1] == "[":
                stack.pop()
    if in_str:
        s += '"'
    closing = ""
    for opener in reversed(stack):
        closing += "}" if opener == "{" else "]"
    if closing:
        try:
            return json.loads(s + closing)
        except Exception:
            pass
    return None


def _parse_ask_block(text):
    """从回复中解析 [ASK]{json}[/ASK]，返回 (questions_list 或 None, 去掉ASK块的前置文本)。"""
    m = re.search(r"\[ASK\]([\s\S]*?)\[/ASK\]", text)
    if not m:
        return None, text
    raw = m.group(1).strip()
    data = _lenient_json_loads(raw)
    if data is None:
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


def _execute_agent_calls_stream(text, history, conv):
    pattern = r"\[CALL:(\S+?)\]([\s\S]*?)\[\/CALL\]"
    matches = re.findall(pattern, text)
    if not matches:
        return
    agent_accumulated = {}


    for slug, task_content in matches:
        task_content = task_content.strip()
        agent = None
        for a in agents_list:
            if a.get("slug") == slug and a.get("callable"):
                agent = a
                break
        agent_name = agent.get("name", slug) if agent else slug

        if not agent:
            err_msg = f"[错误: 未找到智能体 {slug}]"
            chunk_data = json.dumps({"agent_call_chunk": {"slug": slug, "content": err_msg}}, ensure_ascii=False)
            yield f"data: {chunk_data}\n\n"
            end_data = json.dumps({"agent_call_end": {"slug": slug}}, ensure_ascii=False)
            yield f"data: {end_data}\n\n"
            history.append({"role": "assistant", "content": err_msg, "ts": int(time.time()), "agent_call": {"slug": slug, "name": agent_name}})
            _save_conversations()
            escaped_slug = re.escape(slug)
            block_pattern = f"\\[CALL:{escaped_slug}\\][\\s\\S]*?\\[\\/CALL\\]"
            text = re.sub(block_pattern, "", text, count=1)
            continue

        try:
            sub_cfg = _get_chat_config(agent["id"])
            sub_history = []
            if agent.get("system_prompt"):
                sub_history.append({"role": "system", "content": agent["system_prompt"]})
            sub_kb = _build_project_kb_prompt(conv.get("project_id"))
            if sub_kb:
                sub_history.append({"role": "system", "content": sub_kb.strip()})
            sub_history.append({"role": "user", "content": task_content})

            start_data = json.dumps({"agent_call_start": {"slug": slug, "name": agent_name, "is_image": _is_image_model(sub_cfg.get("model", ""))}}, ensure_ascii=False)
            yield f"data: {start_data}\n\n"

            if _is_image_model(sub_cfg.get("model", "")):
                img_resp = _request_image_generation(sub_cfg, sub_history)
                if img_resp.status_code != 200:
                    upstream_msg = ""
                    try:
                        eb = img_resp.json()
                        eo = eb.get("error", eb) if isinstance(eb, dict) else eb
                        if isinstance(eo, dict):
                            upstream_msg = str(eo.get("message") or "")
                        elif isinstance(eo, str):
                            upstream_msg = eo
                    except Exception:
                        try:
                            upstream_msg = (img_resp.text or "")[:300]
                        except Exception:
                            upstream_msg = ""
                    result = f"[生图失败: HTTP {img_resp.status_code} - {upstream_msg}]" if upstream_msg else f"[生图失败: HTTP {img_resp.status_code}]"
                else:
                    try:
                        jd = img_resp.json()
                        message = jd["choices"][0]["message"]
                    except Exception:
                        message = {}
                        jd = {}
                    text_content = (message.get("content") or "").strip()
                    img_urls = _extract_message_images(message)
                    if not img_urls and isinstance(jd.get("data"), list):
                        for it in jd["data"]:
                            if isinstance(it, dict):
                                u = it.get("url") or ""
                                b64 = it.get("b64_json") or ""
                                if u:
                                    img_urls.append(u)
                                elif b64:
                                    img_urls.append("data:image/png;base64," + b64)
                    parts = []
                    if text_content:
                        parts.append(text_content)
                    for u in img_urls:
                        parts.append(f"![image]({u})")
                    result = "\n\n".join(parts) if parts else "[生图返回为空]"
                agent_accumulated[slug] = result
                chunk_data = json.dumps({"agent_call_chunk": {"slug": slug, "content": result}}, ensure_ascii=False)
                yield f"data: {chunk_data}\n\n"
            else:
                resp = send_chat_request(
                    sub_cfg["base_url"],
                    sub_cfg["api_key"],
                    sub_history,
                    sub_cfg["model"]
                )
                if resp.status_code != 200:
                    upstream_msg = ""
                    try:
                        err_json = resp.json()
                        err_obj = err_json.get("error", err_json)
                        if isinstance(err_obj, dict):
                            upstream_msg = str(err_obj.get("message") or "")
                        elif isinstance(err_obj, str):
                            upstream_msg = err_obj
                    except Exception:
                        try:
                            upstream_msg = (resp.text or "")[:300]
                        except Exception:
                            upstream_msg = ""
                    err_text = f"[调用失败: HTTP {resp.status_code} - {upstream_msg}]" if upstream_msg else f"[调用失败: HTTP {resp.status_code}]"
                    agent_accumulated[slug] = err_text
                    chunk_data = json.dumps({"agent_call_chunk": {"slug": slug, "content": err_text}}, ensure_ascii=False)
                    yield f"data: {chunk_data}\n\n"
                else:
                    has_content = False
                    for line in resp.iter_lines(decode_unicode=True):
                        chunk = parse_stream_chunk(line)
                        if chunk is None:
                            break
                        if chunk:
                            has_content = True
                            agent_accumulated[slug] = agent_accumulated.get(slug, "") + chunk
                            chunk_data = json.dumps({"agent_call_chunk": {"slug": slug, "content": chunk}}, ensure_ascii=False)
                            yield f"data: {chunk_data}\n\n"
                    if not has_content:
                        agent_accumulated[slug] = "[智能体无回复]"
                        chunk_data = json.dumps({"agent_call_chunk": {"slug": slug, "content": "[智能体无回复]"}}, ensure_ascii=False)
                        yield f"data: {chunk_data}\n\n"
        except Exception as e:
            err_text = f"[调用异常: {str(e)}]"
            agent_accumulated[slug] = err_text
            chunk_data = json.dumps({"agent_call_chunk": {"slug": slug, "content": err_text}}, ensure_ascii=False)
            yield f"data: {chunk_data}\n\n"

        end_data = json.dumps({"agent_call_end": {"slug": slug}}, ensure_ascii=False)
        yield f"data: {end_data}\n\n"

        sub_content = agent_accumulated.get(slug, "")
        now_ts = int(time.time())
        history.append({"role": "assistant", "content": sub_content, "ts": now_ts, "agent_call": {"slug": slug, "name": agent_name}})
        conv["updated"] = time.time()
        _save_conversations()

        escaped_slug = re.escape(slug)
        block_pattern = f"\\[CALL:{escaped_slug}\\][\\s\\S]*?\\[\\/CALL\\]"
        text = re.sub(block_pattern, "", text, count=1)

    return text

def _new_conversation(agent_id=None, project_id=None, mode=None):
    cid = str(uuid.uuid4())[:8]
    if mode not in ("chat", "blackbox", "workflow"):
        mode = "chat"
    if not _agent_belongs_to_scope(agent_id, project_id):
        agent_id = None
    if project_id and not agent_id:
        agent_id = _get_default_project_agent_id(project_id)
    system_content = _get_system_content(agent_id, project_id)
    history = []
    if system_content:
        history.append({"role": "system", "content": system_content})
    conversations[cid] = {
        "id": cid,
        "title": "新对话",
        "agent_id": agent_id,
        "project_id": project_id,
        "history": history,
        "orchestration_mode": mode,
        "created": time.time(),
        "updated": time.time(),
        "pinned": False
    }
    _save_conversations()
    return cid


def _get_conv(cid):
    return conversations.get(cid)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/__shutdown__", methods=["GET"])
def shutdown_stream():
    def generate():
        while not _SHUTDOWN_EVENT.is_set():
            yield "data: {}\n\n"
            _SHUTDOWN_EVENT.wait(timeout=1)
        yield 'data: {"close": true}\n\n'
    return Response(stream_with_context(generate()), mimetype="text/event-stream; charset=utf-8")


@app.route("/__shutdown__", methods=["POST"])
def shutdown_trigger():
    _SHUTDOWN_EVENT.set()
    def _later():
        time.sleep(1.5)
        os._exit(0)
    threading.Thread(target=_later, daemon=True).start()
    return jsonify({"status": "ok"})


@app.route("/api/providers", methods=["GET"])
def get_providers():
    result = {}
    for key, val in PROVIDER_MODELS.items():
        result[key] = {"name": val["name"], "base_url": val["base_url"], "models": val["models"]}
    return jsonify(result)


@app.route("/api/provider-key-status", methods=["GET"])
def provider_key_status():
    mid = request.args.get("id", "").strip()
    return jsonify({"has_api_key": bool(_get_key_for(mid)) if mid else False})


@app.route("/api/settings", methods=["GET"])
def get_settings():
    return jsonify({
        "provider": runtime_config["provider"],
        "base_url": runtime_config["base_url"],
        "model": runtime_config["model"],
        "has_api_key": bool(_get_key_for(runtime_config.get("model_id", ""))),
        "max_history_rounds": runtime_config["max_history_rounds"],
        "max_context_size_kb": runtime_config.get("max_context_size_kb", 0),
        "auto_compress": runtime_config.get("auto_compress", False),
        "compress_threshold_kb": runtime_config.get("compress_threshold_kb", 128),
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
        target_mid = (data.get("id") or runtime_config.get("model_id") or "").strip()
        if target_mid:
            _set_key_for(target_mid, data["api_key"])
    _save_config(runtime_config)
    return jsonify({"status": "ok"})


@app.route("/api/model", methods=["PUT"])
def switch_model():
    data = request.get_json()
    provider = data.get("provider", "")
    model = data.get("model", "")
    base_url = data.get("base_url", "")
    model_id = data.get("id", "")
    if model_id and not (provider and model):
        for m in runtime_config.get("custom_models", []):
            if m.get("id") == model_id:
                provider = m.get("provider", "")
                model = m.get("model", "")
                base_url = m.get("base_url", "") or base_url
                break
    if not model_id and provider and model:
        for m in runtime_config.get("custom_models", []):
            if m.get("provider") == provider and m.get("model") == model:
                model_id = m.get("id", "")
                break
    if provider and model:
        runtime_config["provider"] = provider
        runtime_config["model"] = model
        runtime_config["model_id"] = model_id
        runtime_config["api_key"] = _get_key_for(model_id)
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
    entry = {"id": str(uuid.uuid4())[:8], "provider": provider, "model": model, "base_url": base_url, "name": name}
    models.append(entry)
    runtime_config["custom_models"] = models
    _save_config(runtime_config)
    api_key = (data.get("api_key") or "").strip()
    if api_key:
        _set_key_for(entry["id"], api_key)
    return jsonify(entry), 201


@app.route("/api/custom-models", methods=["DELETE"])
def remove_custom_model():
    data = request.get_json()
    mid = (data.get("id") or "").strip()
    provider = data.get("provider", "")
    model = data.get("model", "")
    models = runtime_config.get("custom_models", [])
    removed_ids = []
    if mid:
        removed_ids = [m.get("id") for m in models if m.get("id") == mid]
        runtime_config["custom_models"] = [m for m in models if m.get("id") != mid]
    else:
        removed_ids = [m.get("id") for m in models if m.get("provider") == provider and m.get("model") == model]
        runtime_config["custom_models"] = [m for m in models if not (m.get("provider") == provider and m.get("model") == model)]
    _save_config(runtime_config)
    for rid in removed_ids:
        _del_key_for(rid)
    return jsonify({"status": "ok"})


@app.route("/api/custom-models", methods=["PUT"])
def update_custom_model():
    data = request.get_json()
    mid = (data.get("id") or "").strip()
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
    hit_id = ""
    for m in models:
        if (mid and m.get("id") == mid) or (not mid and m.get("provider") == old_provider and m.get("model") == old_model):
            m["provider"] = new_provider
            m["model"] = new_model
            m["base_url"] = new_base_url
            m["name"] = new_name
            hit_id = m.get("id", "")
            found = True
            break
    if not found:
        return jsonify({"error": "未找到原模型"}), 404
    runtime_config["custom_models"] = models
    _save_config(runtime_config)
    new_key = (data.get("api_key") or "").strip()
    if new_key and hit_id:
        _set_key_for(hit_id, new_key)
    return jsonify({"status": "ok"})


@app.route("/api/custom-models/reorder", methods=["POST"])
def reorder_custom_models():
    data = request.get_json() or {}
    order = data.get("order", [])
    if not isinstance(order, list):
        return jsonify({"error": "order 必须是列表"}), 400
    models = runtime_config.get("custom_models", [])
    index_map = {}
    for m in models:
        if m.get("id"):
            index_map[m["id"]] = m
        index_map[m.get("provider", "") + "|" + m.get("model", "")] = m
    reordered = []
    seen = set()
    for key in order:
        m = index_map.get(key)
        if m is not None and id(m) not in seen:
            reordered.append(m); seen.add(id(m))
    for m in models:
        if id(m) not in seen:
            reordered.append(m); seen.add(id(m))
    runtime_config["custom_models"] = reordered
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
        "model_id": data.get("model_id", ""),
        "callable": data.get("callable", False),
        "slug": data.get("slug", ""),
        "when_to_call": data.get("when_to_call", ""),
        "can_call": data.get("can_call", []),
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
    if "model_id" in data:
        agent["model_id"] = data["model_id"]
    if "can_call" in data:
        agent["can_call"] = data["can_call"]
    _save_agents(agents_list)
    return jsonify(agent)


@app.route("/api/agents/<agent_id>", methods=["DELETE"])
def delete_agent(agent_id):
    global agents_list
    agents_list = [a for a in agents_list if a["id"] != agent_id]
    for a in agents_list:
        cc = a.get("can_call")
        if isinstance(cc, list) and agent_id in cc:
            a["can_call"] = [x for x in cc if x != agent_id]
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


# ==================== 项目 API ====================

@app.route("/api/projects", methods=["GET"])
def list_projects():
    ordered = sorted(projects_list, key=lambda p: p.get("created") or 0)
    return jsonify(ordered)


@app.route("/api/projects", methods=["POST"])
def create_project():
    data = request.get_json() or {}
    name = (data.get("name") or "").strip() or "新项目"
    raw_files = data.get("files") or []
    saved_files = []
    for rf in raw_files:
        if not isinstance(rf, dict): continue
        fname = (rf.get("name") or "未命名.txt").strip()[:120]
        fcontent = rf.get("content") or ""
        if not fcontent.strip(): continue
        if len(fcontent.encode("utf-8")) > PROJECT_FILE_MAX_BYTES: continue
        saved_files.append({"id": str(uuid.uuid4())[:8], "name": fname, "content": fcontent})
    raw_agents = data.get("agents")
    if isinstance(raw_agents, list) and raw_agents:
        proj_agents = _sanitize_project_agents(raw_agents)
    else:
        proj_agents = []
    if not proj_agents:
        proj_agents = [_make_default_project_agent()]
    project = {
        "id": str(uuid.uuid4())[:8],
        "name": name[:50],
        "system_prompt": data.get("system_prompt", ""),
        "agents": proj_agents,
        "files": saved_files,
        "created": time.time(),
        "updated": time.time()
    }
    projects_list.append(project)
    _save_projects(projects_list)
    return jsonify(project), 201


@app.route("/api/projects/<project_id>", methods=["PUT"])
def update_project(project_id):
    project = _get_project(project_id)
    if not project:
        return jsonify({"error": "项目不存在"}), 404
    data = request.get_json() or {}
    if "name" in data:
        project["name"] = (data["name"] or "").strip()[:50] or project["name"]
    if "system_prompt" in data:
        project["system_prompt"] = data["system_prompt"]
    if "agents" in data and isinstance(data["agents"], list):
        sanitized = _sanitize_project_agents(data["agents"])
        if sanitized:
            project["agents"] = sanitized
    if "provider" in data:
        project["provider"] = data["provider"]
    if "model" in data:
        project["model"] = data["model"]
    if "files" in data and isinstance(data["files"], list):
        raw_files = data["files"]
        saved_files = []
        for rf in raw_files:
            if not isinstance(rf, dict): continue
            fname = (rf.get("name") or "未命名.txt").strip()[:120]
            fcontent = rf.get("content") or ""
            if not fcontent.strip(): continue
            if len(fcontent.encode("utf-8")) > PROJECT_FILE_MAX_BYTES: continue
            saved_files.append({"id": str(uuid.uuid4())[:8], "name": fname, "content": fcontent})
        project["files"] = saved_files
    project["updated"] = time.time()
    _save_projects(projects_list)
    return jsonify(project)


@app.route("/api/projects/<project_id>", methods=["DELETE"])
def delete_project(project_id):
    global projects_list
    if not _get_project(project_id):
        return jsonify({"error": "项目不存在"}), 404
    for c in conversations.values():
        if c.get("project_id") == project_id:
            c["project_id"] = None
    _save_conversations()
    projects_list = [p for p in projects_list if p["id"] != project_id]
    _save_projects(projects_list)
    return jsonify({"status": "ok"})


def _sanitize_project_agents(raw_agents):
    result = []
    for ra in raw_agents:
        if not isinstance(ra, dict):
            continue
        nm = (ra.get("name") or "").strip()
        if not nm:
            continue
        result.append({
            "id": ra.get("id") or str(uuid.uuid4())[:8],
            "name": nm[:50],
            "avatar": ra.get("avatar", ""),
            "system_prompt": ra.get("system_prompt", ""),
            "model": ra.get("model", ""),
            "provider": ra.get("provider", ""),
            "base_url": ra.get("base_url", ""),
            "callable": bool(ra.get("callable", False)),
            "slug": ra.get("slug", ""),
            "when_to_call": ra.get("when_to_call", ""),
            "created": ra.get("created") or time.time()
        })
    return result


@app.route("/api/projects/<project_id>/agents", methods=["GET"])
def list_project_agents(project_id):
    project = _get_project(project_id)
    if not project:
        return jsonify({"error": "项目不存在"}), 404
    return jsonify(project.get("agents") or [])


@app.route("/api/projects/<project_id>/agents", methods=["POST"])
def create_project_agent(project_id):
    project = _get_project(project_id)
    if not project:
        return jsonify({"error": "项目不存在"}), 404
    data = request.get_json() or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "名称不能为空"}), 400
    agent = {
        "id": str(uuid.uuid4())[:8],
        "name": name[:50],
        "avatar": data.get("avatar", ""),
        "system_prompt": data.get("system_prompt", ""),
        "model": data.get("model", ""),
        "provider": data.get("provider", ""),
        "base_url": data.get("base_url", ""),
        "callable": bool(data.get("callable", False)),
        "slug": data.get("slug", ""),
        "when_to_call": data.get("when_to_call", ""),
        "created": time.time()
    }
    if not isinstance(project.get("agents"), list):
        project["agents"] = []
    project["agents"].append(agent)
    project["updated"] = time.time()
    _save_projects(projects_list)
    return jsonify(agent), 201


@app.route("/api/projects/<project_id>/agents/<agent_id>", methods=["PUT"])
def update_project_agent(project_id, agent_id):
    project = _get_project(project_id)
    if not project:
        return jsonify({"error": "项目不存在"}), 404
    agent = next((a for a in (project.get("agents") or []) if a.get("id") == agent_id), None)
    if not agent:
        return jsonify({"error": "智能体不存在"}), 404
    data = request.get_json() or {}
    for key in ("name", "avatar", "system_prompt", "model", "provider", "base_url", "slug", "when_to_call"):
        if key in data:
            agent[key] = data[key].strip() if (key == "name" and isinstance(data[key], str)) else data[key]
    if "callable" in data:
        agent["callable"] = bool(data["callable"])
    project["updated"] = time.time()
    _save_projects(projects_list)
    return jsonify(agent)


@app.route("/api/projects/<project_id>/agents/<agent_id>", methods=["DELETE"])
def delete_project_agent(project_id, agent_id):
    project = _get_project(project_id)
    if not project:
        return jsonify({"error": "项目不存在"}), 404
    agents = project.get("agents") or []
    new_agents = [a for a in agents if a.get("id") != agent_id]
    if len(new_agents) == len(agents):
        return jsonify({"error": "智能体不存在"}), 404
    if not new_agents:
        return jsonify({"error": "项目至少保留一个智能体"}), 400
    project["agents"] = new_agents
    project["updated"] = time.time()
    _save_projects(projects_list)
    return jsonify({"status": "ok"})


PROJECT_FILE_MAX_BYTES = 1024 * 1024


@app.route("/api/projects/<project_id>/files", methods=["GET"])
def list_project_files(project_id):
    project = _get_project(project_id)
    if not project:
        return jsonify({"error": "项目不存在"}), 404
    files = project.get("files") or []
    meta = [{"id": f["id"], "name": f["name"], "size": f.get("size", len(f.get("content", "")))} for f in files]
    return jsonify(meta)


@app.route("/api/projects/<project_id>/files", methods=["POST"])
def upload_project_file(project_id):
    project = _get_project(project_id)
    if not project:
        return jsonify({"error": "项目不存在"}), 404
    data = request.get_json() or {}
    name = (data.get("name") or "未命名.txt").strip()[:120]
    content = data.get("content") or ""
    if not content.strip():
        return jsonify({"error": "文件内容为空"}), 400
    if len(content.encode("utf-8")) > PROJECT_FILE_MAX_BYTES:
        return jsonify({"error": "文件过大，单个文件请控制在 1MB 文本以内"}), 400
    if "files" not in project or not isinstance(project["files"], list):
        project["files"] = []
    f = {
        "id": str(uuid.uuid4())[:8],
        "name": name,
        "content": content,
        "size": len(content.encode("utf-8"))
    }
    project["files"].append(f)
    project["updated"] = time.time()
    _save_projects(projects_list)
    return jsonify({"id": f["id"], "name": f["name"], "size": f["size"]}), 201


@app.route("/api/projects/<project_id>/files/<file_id>", methods=["DELETE"])
def delete_project_file(project_id, file_id):
    project = _get_project(project_id)
    if not project:
        return jsonify({"error": "项目不存在"}), 404
    files = project.get("files") or []
    new_files = [f for f in files if f.get("id") != file_id]
    if len(new_files) == len(files):
        return jsonify({"error": "文件不存在"}), 404
    project["files"] = new_files
    project["updated"] = time.time()
    _save_projects(projects_list)
    return jsonify({"status": "ok"})


def _build_project_kb_prompt(project_id):
    project = _get_project(project_id)
    if not project:
        return ""
    files = project.get("files") or []
    if not files:
        return ""
    parts = ["\n\n【项目知识库】以下是本项目附带的参考资料，回答时可据此作答，但不要照搬无关内容："]
    for f in files:
        parts.append("\n\n----- 文件：" + f.get("name", "未命名") + " -----\n" + (f.get("content") or ""))
    return "".join(parts)


# ==================== 对话 API ====================

@app.route("/api/conversations", methods=["GET"])
def list_conversations():
    result = []
    ordered = sorted(conversations.values(),
                     key=lambda x: (1 if x.get("pinned") else 0,
                                    x.get("updated") or x.get("created") or 0),
                     reverse=True)
    for c in ordered:
        result.append({"id": c["id"], "title": c["title"],
                       "agent_id": c.get("agent_id"), "project_id": c.get("project_id"),
                       "pinned": bool(c.get("pinned")),
                       "orchestration_mode": c.get("orchestration_mode") or "chat",
                       "updated": c.get("updated") or c.get("created") or 0})
    return jsonify(result)


@app.route("/api/conversations", methods=["POST"])
def create_conversation():
    data = request.get_json() if request.is_json else {}
    agent_id = data.get("agent_id", current_agent_id)
    project_id = data.get("project_id")
    mode = data.get("orchestration_mode")
    cid = _new_conversation(agent_id, project_id, mode)
    conv = conversations[cid]
    return jsonify({"id": conv["id"], "title": conv["title"], "agent_id": conv.get("agent_id"), "project_id": conv.get("project_id"), "pinned": bool(conv.get("pinned")), "orchestration_mode": conv.get("orchestration_mode")})


@app.route("/api/conversations/<cid>", methods=["DELETE"])
def delete_conversation(cid):
    if cid in conversations:
        lock = _get_conv_lock(cid)
        if not lock.acquire(blocking=False):
            return jsonify({"error": "当前对话正在生成回复，请等待完成后再操作", "busy": True}), 409
        try:
            del conversations[cid]
            _save_conversations()
        finally:
            lock.release()
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


@app.route("/api/conversations/<cid>/project", methods=["PUT"])
def move_conversation_to_project(cid):
    conv = _get_conv(cid)
    if not conv:
        return jsonify({"error": "对话不存在"}), 404
    data = request.get_json() or {}
    project_id = data.get("project_id") or None
    if project_id and not _get_project(project_id):
        return jsonify({"error": "项目不存在"}), 404
    conv["project_id"] = project_id
    _save_conversations()
    return jsonify({"status": "ok", "project_id": project_id})


@app.route("/api/conversations/<cid>/messages", methods=["GET"])
def get_messages(cid):
    conv = _get_conv(cid)
    if not conv:
        return jsonify({"error": "对话不存在"}), 404
    msgs = [m for m in conv["history"] if m["role"] != "system"]
    return jsonify(msgs)


@app.route("/api/conversations/<cid>/token-total", methods=["GET"])
def get_conv_token_total(cid):
    conv = _get_conv(cid)
    if not conv:
        return jsonify({"error": "对话不存在"}), 404
    return jsonify({"conv_total": _conv_token_total(conv)})


@app.route("/api/token-stats", methods=["GET"])
def get_token_stats():
    with _token_stats_lock:
        data = _load_token_stats()
    daily = data.get("daily", {})
    today = _dt.date.today()
    today_key = today.isoformat()
    today_total = int((daily.get(today_key) or {}).get("total") or 0)

    # 当月每天
    first = today.replace(day=1)
    if today.month == 12:
        nxt = today.replace(year=today.year + 1, month=1, day=1)
    else:
        nxt = today.replace(month=today.month + 1, day=1)
    days_in_month = (nxt - first).days
    month_days = []
    for i in range(days_in_month):
        d = first + _dt.timedelta(days=i)
        k = d.isoformat()
        month_days.append({
            "date": k,
            "day": d.day,
            "total": int((daily.get(k) or {}).get("total") or 0)
        })

    # 当年每月
    year_months = []
    for m in range(1, 13):
        msum = 0
        for k, v in daily.items():
            try:
                dd = _dt.date.fromisoformat(k)
            except Exception:
                continue
            if dd.year == today.year and dd.month == m:
                msum += int((v or {}).get("total") or 0)
        year_months.append({"month": m, "total": msum})

    return jsonify({
        "today": today_key,
        "today_total": today_total,
        "month_days": month_days,
        "year_months": year_months,
        "year": today.year,
        "month": today.month
    })


@app.route("/api/conversations/<cid>/agent", methods=["PUT"])
def update_conversation_agent(cid):
    conv = _get_conv(cid)
    if not conv:
        return jsonify({"error": "对话不存在"}), 404
    data = request.get_json()
    new_agent_id = data.get("agent_id", None)
    if not _agent_belongs_to_scope(new_agent_id, conv.get("project_id")):
        return jsonify({"error": "该智能体不属于当前对话所在的项目"}), 400
    lock = _get_conv_lock(cid)
    if not lock.acquire(blocking=False):
        return jsonify({"error": "当前对话正在生成回复，请等待完成后再操作", "busy": True}), 409
    try:
        conv["agent_id"] = new_agent_id
        conv["history"] = [m for m in conv["history"] if m["role"] != "system"]
        system_content = _get_system_content(new_agent_id, conv.get("project_id"))
        if system_content:
            conv["history"].insert(0, {"role": "system", "content": system_content})
        _save_conversations()
        return jsonify({"status": "ok", "agent_id": new_agent_id})
    finally:
        lock.release()


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

    _conv_lock = _get_conv_lock(cid)
    if not _conv_lock.acquire(blocking=False):
        return jsonify({"error": "当前对话正在生成回复，请等待完成后再发送", "busy": True}), 409
    _lock_released = {"done": False}

    def _release_conv_lock():
        if not _lock_released["done"]:
            _lock_released["done"] = True
            try:
                _conv_lock.release()
            except Exception:
                pass

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

    orchestration_mode = conv.get("orchestration_mode") or "chat"
    if orchestration_mode == "chat":
        callable_agents = []
        callable_prompt = ""
    else:
        callable_agents = _get_callable_agents()
        callable_prompt = _build_callable_prompt(callable_agents)

    def _build_request_history():
        date_note = ("\n\n【当前真实日期】今天是 " + web_search._current_date_str()
                     + "（由系统提供，准确无误）。涉及今天/日期/时效的问题一律以此为准。")
        kb_prompt = _build_project_kb_prompt(conv.get("project_id"))
        extra = (callable_prompt or "") + ASK_PROMPT + date_note + kb_prompt
        last_user_idx = next((i for i in range(len(history) - 1, -1, -1) if history[i].get("role") == "user"), -1)
        recent_imgs = []
        for m in history:
            if m.get("role") == "user":
                c = m.get("content")
                if isinstance(c, list):
                    imgs = [b for b in c if isinstance(b, dict) and b.get("type") == "image_url"]
                    if imgs:
                        recent_imgs = imgs
        req_history = []
        for idx, m in enumerate(history):
            c = m.get("content")
            if isinstance(c, str) and c.startswith(ASK_ANSWER_PREFIX):
                text = c[len(ASK_ANSWER_PREFIX):]
                m = dict(m)
                if idx == last_user_idx and recent_imgs:
                    m["content"] = [{"type": "text", "text": text}] + recent_imgs
                else:
                    m["content"] = text
            elif isinstance(c, list):
                if idx == last_user_idx:
                    has_img = any(isinstance(b, dict) and b.get("type") == "image_url" for b in c)
                    if not has_img and recent_imgs:
                        m = dict(m)
                        m["content"] = list(c) + recent_imgs
                else:
                    texts = [b.get("text", "") for b in c if isinstance(b, dict) and b.get("type") == "text"]
                    has_img = any(isinstance(b, dict) and b.get("type") == "image_url" for b in c)
                    flat = "\n".join(t for t in texts if t).strip()
                    if has_img:
                        flat = (flat + "\n[图片]").strip() if flat else "[图片]"
                    m = dict(m)
                    m["content"] = flat
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
            if _is_image_model(chat_cfg["model"]):
                stream_state["request_sent"] = True
                if stream_state["cancel"].is_set():
                    mgr.rollback_user_message()
                    stream_state["saved"] = True
                    return
                yield "data: " + json.dumps({"image_loading": True}, ensure_ascii=False) + "\n\n"
                # 生图是阻塞式同步请求，放入子线程并可被中断等待：
                # 用户打断后无需等同步请求返回即可立即结束本次生成、释放对话锁。
                _img_box = {}

                def _img_worker():
                    try:
                        _img_box["resp"] = _request_image_generation(
                            chat_cfg,
                            _inject_search(_build_request_history(), search_result)
                        )
                    except Exception as _e:
                        _img_box["err"] = _e

                _img_thread = threading.Thread(target=_img_worker, daemon=True)
                _img_thread.start()
                while _img_thread.is_alive():
                    if stream_state["cancel"].is_set():
                        mgr.rollback_user_message()
                        stream_state["saved"] = True
                        return
                    _img_thread.join(timeout=0.3)
                if stream_state["cancel"].is_set():
                    mgr.rollback_user_message()
                    stream_state["saved"] = True
                    return
                if "err" in _img_box:
                    mgr.rollback_user_message()
                    stream_state["saved"] = True
                    err = json.dumps({"error": "生图请求失败：" + str(_img_box["err"])[:200]}, ensure_ascii=False)
                    yield f"data: {err}\n\n"
                    return
                img_resp = _img_box["resp"]
                if img_resp.status_code != 200:
                    mgr.rollback_user_message()
                    stream_state["saved"] = True
                    msg = ""
                    try:
                        eb = img_resp.json()
                        eo = eb.get("error", eb) if isinstance(eb, dict) else eb
                        if isinstance(eo, dict):
                            msg = eo.get("message", "") or ""
                        elif isinstance(eo, str):
                            msg = eo
                    except Exception:
                        msg = (img_resp.text or "")[:300]
                    friendly = (f"生图失败 [{img_resp.status_code}]：{msg}" if msg
                                else f"生图失败 [{img_resp.status_code}]")
                    err = json.dumps({"error": friendly}, ensure_ascii=False)
                    yield f"data: {err}\n\n"
                    return
                try:
                    jd = img_resp.json()
                    message = jd["choices"][0]["message"]
                except Exception:
                    mgr.rollback_user_message()
                    stream_state["saved"] = True
                    err = json.dumps({"error": "生图返回格式异常"}, ensure_ascii=False)
                    yield f"data: {err}\n\n"
                    return
                text_content = message.get("content") or ""
                img_urls = _extract_message_images(message)
                if not img_urls and isinstance(jd.get("data"), list):
                    for it in jd["data"]:
                        if isinstance(it, dict):
                            u = it.get("url") or ""
                            b64 = it.get("b64_json") or ""
                            if u:
                                img_urls.append(u)
                            elif b64:
                                img_urls.append("data:image/png;base64," + b64)
                if not img_urls:
                    note = "（这次没有生成图片。该生图模型对中文指令支持有限，建议用更具体或英文的描述重试，例如：a minimalist line-art cat on white background。）"
                    text_content = (text_content.strip() + "\n\n" + note) if text_content.strip() else note.strip("（）")
                    stream_state["full_reply"] = text_content
                    ch = json.dumps({"chunk": text_content}, ensure_ascii=False)
                    yield f"data: {ch}\n\n"
                    now_ts = int(time.time())
                    history.append({"role": "assistant", "content": text_content, "ts": now_ts, "agent_id": agent_id})
                    conv["updated"] = time.time()
                    stream_state["saved"] = True
                    mgr._trim_history()
                    _save_conversations()
                    ts_data = json.dumps({"ts": now_ts}, ensure_ascii=False)
                    yield f"data: {ts_data}\n\n"
                    yield "data: [DONE]\n\n"
                    return
                if text_content:
                    stream_state["full_reply"] = text_content
                    ch = json.dumps({"chunk": text_content}, ensure_ascii=False)
                    yield f"data: {ch}\n\n"
                ev = json.dumps({"images": img_urls}, ensure_ascii=False)
                yield f"data: {ev}\n\n"
                assistant_content = [{"type": "text", "text": text_content}] if text_content else []
                for u in img_urls:
                    assistant_content.append({"type": "image_url", "image_url": {"url": u}})
                now_ts = int(time.time())
                history.append({"role": "assistant", "content": assistant_content, "ts": now_ts, "agent_id": agent_id})
                conv["updated"] = time.time()
                stream_state["saved"] = True
                mgr._trim_history()
                _save_conversations()
                ts_data = json.dumps({"ts": now_ts}, ensure_ascii=False)
                yield f"data: {ts_data}\n\n"
                yield "data: [DONE]\n\n"
                return

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
                _ucode, friendly = _friendly_upstream_error(resp.status_code, upstream_msg, bool(images))
                error_data = json.dumps({"error": friendly}, ensure_ascii=False)
                yield f"data: {error_data}\n\n"
                return

            history.append({"role": "assistant", "content": ""})
            reasoning_buf = ""
            in_reasoning = False
            turn_usage = None
            for line in resp.iter_lines(decode_unicode=True):
                if stream_state["cancel"].is_set():
                    break
                _u = parse_stream_usage(line)
                if _u:
                    turn_usage = _u
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
                clean_text = re.sub(r"\[CALL:\S+?\][\s\S]*?\[\/CALL\]", "", full_reply).strip()
                yield "data: \n\n"
                replace_data = json.dumps({"replace": clean_text}, ensure_ascii=False)
                yield f"data: {replace_data}\n\n"
                history[-1]["content"] = clean_text
                if orchestration_mode == "chat":
                    pass
                elif orchestration_mode == "blackbox":
                    _bb_before = len(history)
                    yield from _execute_agent_calls_stream(full_reply, history, conv)
                    _bb_results = []
                    for _m in history[_bb_before:]:
                        if _m.get("role") == "assistant" and _m.get("agent_call"):
                            _ac = _m.get("agent_call") or {}
                            _bb_results.append((_ac.get("name") or _ac.get("slug") or "子智能体", _msg_plain_text(_m)))
                    if _bb_results and not stream_state["cancel"].is_set():
                        yield "data: " + json.dumps({"reconcile_start": True}, ensure_ascii=False) + "\n\n"
                        _bb_sys = ("你是主控智能体。下面会给你用户的问题以及若干子智能体的执行结果，"
                                   "请你据此把各路结果忠实地整合成一份给用户的最终回答。\n"
                                   "诚实原则（最重要）：各子智能体是并行、互相独立完成的，它们之间可能并不一致。"
                                   "如果发现各结果之间存在矛盾、不衔接、或并非围绕同一对象/主题，你必须如实说明这一情况，"
                                   "分别清楚地呈现各路结果；绝对禁止编造它们之间本不存在的关联，禁止假装它们是配套的、一致的。\n"
                                   "格式要求：只输出最终回答内容本身；禁止复述本指令或任务说明；"
                                   "禁止描述你的思考过程；禁止出现“我们被要求”“用户的问题是”“某某智能体说/输出了”之类的元叙述；"
                                   "禁止解释你将要怎么做。直接开始正文。")
                        _bb_parts = ["【用户的问题】", str(user_input or ""), "", "【各子智能体的执行结果】"]
                        for _bn, _bc in _bb_results:
                            _bb_parts.append("◆ " + _bn + "：\n" + (_bc or "（无内容）"))
                        _bb_summary_req = [{"role": "system", "content": _bb_sys}, {"role": "user", "content": "\n".join(_bb_parts)}]
                        _bb_text = ""
                        try:
                            _bb_resp = send_chat_request(chat_cfg["base_url"], chat_cfg["api_key"], _bb_summary_req, chat_cfg["model"])
                            if _bb_resp.status_code == 200:
                                for _bl in _bb_resp.iter_lines(decode_unicode=True):
                                    if stream_state["cancel"].is_set():
                                        break
                                    _bc2 = parse_stream_chunk(_bl)
                                    if _bc2 is None:
                                        break
                                    if _bc2:
                                        _bb_text += _bc2
                                        yield "data: " + json.dumps({"chunk": _bc2}, ensure_ascii=False) + "\n\n"
                        except Exception:
                            _bb_text = ""
                        if _bb_text.strip():
                            history.append({"role": "assistant", "content": _bb_text, "ts": int(time.time()), "agent_id": agent_id, "reconcile": True})
                            stream_state["full_reply"] = _bb_text
                            _save_conversations()
                        else:
                            yield "data: " + json.dumps({"reconcile_error": True}, ensure_ascii=False) + "\n\n"
                else:
                    yield from _execute_agent_calls_stream(full_reply, history, conv)
                mgr._trim_history()
            else:
                mgr._trim_history()

            if runtime_config.get("auto_compress", False):
                thr_kb = runtime_config.get("compress_threshold_kb", 128)
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
            conv["updated"] = time.time()
            if history and history[-1].get("role") == "assistant":
                history[-1]["ts"] = int(time.time())
                history[-1]["agent_id"] = agent_id
                if turn_usage:
                    history[-1]["usage"] = turn_usage
            if turn_usage:
                _record_token_usage(turn_usage)
                usage_data = json.dumps({"usage": {
                    "turn": turn_usage,
                    "conv_total": _conv_token_total(conv)
                }}, ensure_ascii=False)
                yield f"data: {usage_data}\n\n"
            stream_state["saved"] = True
            _save_conversations()
            ts_data = json.dumps({"ts": int(time.time())}, ensure_ascii=False)
            yield f"data: {ts_data}\n\n"
            _release_conv_lock()
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
            _gcode, _gfriendly = _classify_generate_error(e)
            error_data = json.dumps({"error": _gfriendly}, ensure_ascii=False)
            yield f"data: {error_data}\n\n"


    active = _register_active_stream(cid, stream_state["cancel"], is_image=_is_image_model(chat_cfg["model"]))

    def _drive():
        try:
            for ev in generate():
                _push_active_event(active, ev)
        except Exception as e:
            try:
                if not stream_state["saved"]:
                    if not stream_state["full_reply"] and history and history[-1].get("role") == "assistant" and history[-1].get("content") == "":
                        history.pop()
                        mgr.rollback_user_message()
                    stream_state["saved"] = True
                    _save_conversations()
            except Exception:
                pass
            _dcode, _dfriendly = _classify_generate_error(e)
            err = json.dumps({"error": _dfriendly}, ensure_ascii=False)
            _push_active_event(active, f"data: {err}\n\n")
        finally:
            _release_conv_lock()
            _finish_active_stream(cid, active)

    threading.Thread(target=_drive, daemon=True).start()

    def observe():
        for ev in _observe_active_stream(active):
            yield ev

    resp = Response(stream_with_context(observe()), mimetype="text/event-stream; charset=utf-8")
    return resp


@app.route("/api/chat/attach/<cid>", methods=["GET"])
def chat_attach(cid):
    st = _get_active_stream(cid)
    if not st:
        return jsonify({"active": False}), 404

    def observe():
        for ev in _observe_active_stream(st):
            yield ev

    resp = Response(stream_with_context(observe()), mimetype="text/event-stream; charset=utf-8")
    return resp


@app.route("/api/chat/active/<cid>", methods=["GET"])
def chat_active(cid):
    st = _get_active_stream(cid)
    return jsonify({"active": bool(st and not st["done"]), "is_image": bool(st and st.get("is_image"))})


@app.route("/api/chat/stop/<cid>", methods=["POST"])
def chat_stop(cid):
    st = _get_active_stream(cid)
    if not st:
        return jsonify({"status": "ok", "active": False})
    st["cancel"].set()
    return jsonify({"status": "ok", "active": True})



@app.route("/api/conversations/<cid>/clear", methods=["POST"])
def clear_conversation(cid):
    conv = _get_conv(cid)
    if not conv:
        return jsonify({"error": "对话不存在"}), 404
    lock = _get_conv_lock(cid)
    if not lock.acquire(blocking=False):
        return jsonify({"error": "当前对话正在生成回复，请等待完成后再操作", "busy": True}), 409
    try:
        agent_id = conv.get("agent_id")
        conv["history"].clear()
        system_content = _get_system_content(agent_id)
        if system_content:
            conv["history"].append({"role": "system", "content": system_content})
        _save_conversations()
        return jsonify({"status": "ok"})
    finally:
        lock.release()


@app.route("/api/conversations/<cid>/retry", methods=["POST"])
def retry_conversation(cid):
    conv = _get_conv(cid)
    if not conv:
        return jsonify({"error": "对话不存在"}), 404
    lock = _get_conv_lock(cid)
    if not lock.acquire(blocking=False):
        return jsonify({"error": "当前对话正在生成回复，请等待完成后再操作", "busy": True}), 409
    try:
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
    finally:
        lock.release()


@app.route("/api/conversations/<cid>/undo", methods=["POST"])
def undo_conversation(cid):
    conv = _get_conv(cid)
    if not conv:
        return jsonify({"error": "对话不存在"}), 404
    lock = _get_conv_lock(cid)
    if not lock.acquire(blocking=False):
        return jsonify({"error": "当前对话正在生成回复，请等待完成后再操作", "busy": True}), 409
    try:
        st = _get_active_stream(cid)
        if st:
            st["cancel"].set()
            _finish_active_stream(cid, st)
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
    finally:
        lock.release()
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
            "project_id": conv.get("project_id"),
            "orchestration_mode": conv.get("orchestration_mode") or "chat",
            "pinned": bool(conv.get("pinned")),
            "created": conv.get("created", time.time()),
            "updated": conv.get("updated") or conv.get("created") or time.time(),
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
