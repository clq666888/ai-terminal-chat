import os
import re

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
AGENTS_DIR = os.path.join(PROJECT_ROOT, "agents")

SECTION_PATTERN = re.compile(r"^\[(.+)\]\s*$")

PROVIDER_URLS = {
    "deepseek": "https://api.deepseek.com",
    "openai": "https://api.openai.com/v1",
    "claude": "https://api.anthropic.com/v1",
    "moonshot": "https://api.moonshot.cn/v1",
    "zhipu": "https://open.bigmodel.cn/api/paas/v4",
    "qwen": "https://dashscope.aliyuncs.com/compatible-mode/v1",
}


def _parse_sections(filepath):
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except Exception:
        return None

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


def _resolve_api_key(sections):
    direct_key = sections.get("API Key", "").strip()
    if direct_key:
        return direct_key

    key_file = sections.get("API Key 文件", "").strip()
    if key_file:
        try:
            with open(os.path.expanduser(key_file), "r", encoding="utf-8") as f:
                key = f.read().strip()
            if key:
                return key
        except Exception:
            pass

    return ""


def _build_agent_dict(sections, filepath):
    if "标识名" not in sections or not sections["标识名"]:
        return None

    provider = sections.get("服务商", "").strip().lower()
    api_url = sections.get("API地址", "").strip()
    if not api_url and provider in PROVIDER_URLS:
        api_url = PROVIDER_URLS[provider]

    temp_str = sections.get("温度", "").strip()
    temperature = None
    if temp_str:
        try:
            temperature = float(temp_str)
        except ValueError:
            pass

    return {
        "name": sections.get("名称", sections["标识名"]),
        "id": sections["标识名"],
        "system_prompt": sections.get("系统提示词", ""),
        "provider": provider,
        "api_url": api_url,
        "api_key": _resolve_api_key(sections),
        "model": sections.get("模型", "").strip(),
        "temperature": temperature,
        "allowed_tools": _parse_tool_list(sections.get("可用工具", "")),
        "callable": sections.get("可被调用", "否").strip() in ("是", "yes", "true", "1"),
        "when_to_call": sections.get("何时调用", ""),
        "file": filepath,
    }


def _parse_tool_list(text):
    if not text.strip():
        return []
    items = [t.strip() for t in re.split(r"[,，、\s]+", text) if t.strip()]
    return items


def get_global_agent():
    gpath = os.path.join(AGENTS_DIR, "global.txt")
    if not os.path.isfile(gpath):
        return None
    sections = _parse_sections(gpath)
    if sections is None:
        return None
    return _build_agent_dict(sections, gpath)


def list_agents():
    if not os.path.isdir(AGENTS_DIR):
        return []
    agents = []
    for fname in sorted(os.listdir(AGENTS_DIR)):
        if not fname.endswith(".txt"):
            continue
        fpath = os.path.join(AGENTS_DIR, fname)
        agent_sections = _parse_sections(fpath)
        if agent_sections is None:
            continue
        agent = _build_agent_dict(agent_sections, fpath)
        if agent:
            agents.append(agent)
    return agents


def get_agent(agent_id):
    agents = list_agents()
    for a in agents:
        if a["id"] == agent_id:
            return a
    return None


def filter_tools(all_tools, allowed_tool_names):
    if not allowed_tool_names:
        return all_tools
    return [t for t in all_tools if t["function"]["name"] in allowed_tool_names]


def print_agent_list(agents, current_id=None):
    print("\n📋 可用智能体:")
    print("─" * 40)
    for i, a in enumerate(agents, 1):
        marker = " ◀ 当前" if a["id"] == current_id else ""
        tools_str = ", ".join(a["allowed_tools"]) if a["allowed_tools"] else "全部"
        model_str = a["model"] if a["model"] else "全局"
        provider_str = a["provider"] if a["provider"] else "全局"
        print(f"  {i}. {a['name']} (@{a['id']}){marker}")
        print(f"     模型: {provider_str}/{model_str}")
        print(f"     工具: {tools_str}")
        if a["when_to_call"]:
            print(f"     用途: {a['when_to_call']}")
    print("─" * 40)
    print("  切换: @标识名 | 列表: agents | 返回: 回车")
