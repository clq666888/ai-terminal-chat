import os
import re

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(SCRIPT_DIR, "config.txt")

SECTION_PATTERN = re.compile(r"^\[(.+)\]\s*$")

DEFAULTS = {
    "最大记忆轮数": 50,
    "最大工具调用轮数": 20,
    "连接超时秒数": 10,
    "响应超时秒数": 120,
    "单次读取文件最大行数": 200,
    "命令执行超时秒数": 30,
    "命令输出最大字符数": 10000,
    "搜索结果最大条数": 50,
    "目录递归最大层级": 4,
    "历史压缩阈值轮数": 30,
    "压缩保留最近轮数": 10,
}


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
