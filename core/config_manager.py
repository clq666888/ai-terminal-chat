import os
import re

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(PROJECT_ROOT, "config.txt")

SECTION_PATTERN = re.compile(r"^\[(.+)\]\s*$")

CONFIG_SCHEMA = [
    {"key": "最大记忆轮数", "default": 50, "type": "int", "group": "对话",
     "desc": "保留多少轮历史对话，超出后丢弃早期对话", "min": 1, "max": 500},
    {"key": "最大工具调用轮数", "default": 20, "type": "int", "group": "对话",
     "desc": "单次对话最多调用工具的次数", "min": 1, "max": 200},
    {"key": "历史压缩阈值轮数", "default": 30, "type": "int", "group": "对话",
     "desc": "对话超过多少轮时自动触发压缩", "min": 1, "max": 500},
    {"key": "压缩保留最近轮数", "default": 10, "type": "int", "group": "对话",
     "desc": "压缩后保留最近多少轮对话", "min": 1, "max": 200},
    {"key": "diff保存最大轮数", "default": 10, "type": "int", "group": "对话",
     "desc": "AI 文件改动记录保留的轮数", "min": 1, "max": 100},
    {"key": "连接超时秒数", "default": 10, "type": "int", "group": "超时",
     "desc": "API 连接超时时间", "min": 1, "max": 600},
    {"key": "响应超时秒数", "default": 120, "type": "int", "group": "超时",
     "desc": "API 响应超时时间", "min": 1, "max": 3600},
    {"key": "命令执行超时秒数", "default": 30, "type": "int", "group": "超时",
     "desc": "执行命令的超时时间", "min": 1, "max": 3600},
    {"key": "单次读取文件最大行数", "default": 200, "type": "int", "group": "文件",
     "desc": "一次读取文件的最大行数", "min": 1, "max": 10000},
    {"key": "命令输出最大字符数", "default": 10000, "type": "int", "group": "文件",
     "desc": "命令输出截断的最大字符数", "min": 100, "max": 1000000},
    {"key": "搜索结果最大条数", "default": 50, "type": "int", "group": "文件",
     "desc": "搜索返回的最大结果条数", "min": 1, "max": 1000},
    {"key": "目录递归最大层级", "default": 4, "type": "int", "group": "文件",
     "desc": "列目录时递归的最大层级", "min": 1, "max": 20},
    {"key": "权限", "default": 3, "type": "int", "group": "安全",
     "desc": "工具权限等级（0-3）", "min": 0, "max": 3},
]

DEFAULTS = {item["key"]: item["default"] for item in CONFIG_SCHEMA}


def _parse_config(filepath):
    if not os.path.isfile(filepath):
        return {}
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except Exception:
        return {}

    sections = {}
    current_key = None
    current_lines = []

    for line in lines:
        m = SECTION_PATTERN.match(line.strip())
        if m:
            if current_key is not None:
                sections[current_key] = "\n".join(current_lines).strip()
            current_key = m.group(1)
            current_lines = []
        else:
            if current_key is not None:
                current_lines.append(line.rstrip("\n"))

    if current_key is not None:
        sections[current_key] = "\n".join(current_lines).strip()

    return sections


def load_config():
    sections = _parse_config(CONFIG_PATH)
    config = {}
    for key, default_val in DEFAULTS.items():
        raw = sections.get(key, "").strip()
        if raw:
            try:
                config[key] = type(default_val)(raw)
            except (ValueError, TypeError):
                config[key] = default_val
        else:
            config[key] = default_val
    return config


def get_config_path():
    return CONFIG_PATH


def get_config_schema():
    return CONFIG_SCHEMA


def save_config(config_dict):
    blocks = []
    for item in CONFIG_SCHEMA:
        key = item["key"]
        value = config_dict.get(key, item["default"])
        blocks.append("[%s]\n%s\n" % (key, value))
    content = "\n".join(blocks)
    tmp_path = CONFIG_PATH + ".tmp"
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp_path, CONFIG_PATH)
        return True, ""
    except Exception as e:
        try:
            if os.path.isfile(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass
        return False, str(e)



PROJECT_CONTEXT_FILENAME = ".polyai-context"


def load_project_context(work_dir):
    context_path = os.path.join(work_dir, PROJECT_CONTEXT_FILENAME)
    if not os.path.isfile(context_path):
        return ""
    try:
        with open(context_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except Exception:
        return ""

    sections = {}
    current_key = None
    current_lines = []

    for line in lines:
        m = SECTION_PATTERN.match(line.strip())
        if m:
            if current_key is not None:
                sections[current_key] = "\n".join(current_lines).strip()
            current_key = m.group(1)
            current_lines = []
        else:
            if current_key is not None:
                current_lines.append(line.rstrip("\n"))

    if current_key is not None:
        sections[current_key] = "\n".join(current_lines).strip()

    if not sections:
        return ""

    parts = ["\n\n--- 项目上下文（来自 .polyai-context）---"]
    for key, value in sections.items():
        if value:
            parts.append(f"\n【{key}】\n{value}")
    parts.append("\n--- 项目上下文结束 ---")
    return "\n".join(parts)


SESSIONS_DIR = os.path.join(PROJECT_ROOT, "sessions")


def get_sessions_dir():
    os.makedirs(SESSIONS_DIR, exist_ok=True)
    return SESSIONS_DIR
