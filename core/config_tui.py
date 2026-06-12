import sys

from .config_manager import get_config_schema, load_config, save_config


CSI = "\033["


def _supported():
    return sys.stdin.isatty() and sys.stdout.isatty()


class _KeyReader:
    def __enter__(self):
        self._win = sys.platform == "win32"
        if self._win:
            return self
        import termios
        import tty
        self._fd = sys.stdin.fileno()
        self._old = termios.tcgetattr(self._fd)
        tty.setcbreak(self._fd)
        return self

    def __exit__(self, *exc):
        if not self._win:
            import termios
            termios.tcsetattr(self._fd, termios.TCSADRAIN, self._old)
        return False

    def read_key(self):
        if self._win:
            return self._read_win()
        return self._read_posix()

    def _read_posix(self):
        import os
        import select

        def _getch():
            return os.read(self._fd, 1).decode("utf-8", "ignore")

        ch = _getch()
        if ch == "\x1b":
            ready, _, _ = select.select([self._fd], [], [], 0.05)
            if not ready:
                return "esc"
            seq = _getch()
            if seq == "[":
                code = _getch()
                return {"A": "up", "B": "down", "C": "right", "D": "left"}.get(code, "esc")
            return "esc"
        if ch in ("\r", "\n"):
            return "enter"
        if ch == "\t":
            return "tab"
        if ch == "\x03":
            return "ctrl_c"
        return ch

    def _read_win(self):
        import msvcrt
        ch = msvcrt.getwch()
        if ch in ("\x00", "\xe0"):
            code = msvcrt.getwch()
            return {"H": "up", "P": "down", "M": "right", "K": "left"}.get(code, "esc")
        if ch == "\r":
            return "enter"
        if ch == "\t":
            return "tab"
        if ch == "\x1b":
            return "esc"
        if ch == "\x03":
            return "ctrl_c"
        return ch


def _group_order(schema):
    groups = []
    for item in schema:
        g = item.get("group", "其他")
        if g not in groups:
            groups.append(g)
    return groups


def _step_value(item, value, direction):
    vtype = item.get("type", "int")
    if vtype == "int":
        step = 1
        new_val = value + direction * step
        lo = item.get("min")
        hi = item.get("max")
        if lo is not None and new_val < lo:
            new_val = lo
        if hi is not None and new_val > hi:
            new_val = hi
        return new_val
    if vtype == "enum":
        choices = item.get("choices", [])
        if not choices:
            return value
        try:
            idx = choices.index(value)
        except ValueError:
            idx = 0
        idx = (idx + direction) % len(choices)
        return choices[idx]
    return value


def _display_value(item, value):
    if item.get("type") == "enum":
        choices = item.get("choices", [])
        labels = item.get("labels")
        if labels and value in choices:
            return f"{labels[choices.index(value)]} ({value})"
    return str(value)


def _render_tabs(all_tabs, cur_tab_idx, focus, dirty):
    out = []
    out.append(CSI + "2J" + CSI + "H")
    title = "⚙️  配置中心"
    if dirty:
        title += "  *（有未保存修改）"
    out.append(title)
    out.append("")
    tabs = []
    for i, g in enumerate(all_tabs):
        if i == cur_tab_idx:
            if focus == "tabs":
                tabs.append(f"{CSI}7m {g} {CSI}0m")
            else:
                tabs.append(f"{CSI}1m[{g}]{CSI}0m")
        else:
            tabs.append(f" {g} ")
    out.append("  ".join(tabs))
    out.append("─" * 60)
    return out


def _render_config(all_tabs, cur_tab_idx, items, cur_item_idx, values, focus, dirty):
    out = _render_tabs(all_tabs, cur_tab_idx, focus, dirty)
    key_width = max((len(it["key"]) for it in items), default=10)
    for i, it in enumerate(items):
        active = focus == "items" and i == cur_item_idx
        pointer = "▶ " if active else "  "
        key = it["key"].ljust(key_width)
        val = _display_value(it, values[it["key"]])
        line = f"{pointer}{key}   {val}"
        if active:
            line = f"{CSI}1m{line}{CSI}0m"
        out.append(line)
        if active:
            desc = it.get("desc", "")
            if desc:
                out.append(f"{CSI}2m     {desc}{CSI}0m")
    out.append("─" * 60)
    if focus == "tabs":
        hint = "←→ 切换分类   ↓ 进入配置   Enter 保存退出   Esc 放弃退出"
    else:
        hint = "↑↓ 选择（顶部↑返回分类）   ←→ 改值   Enter 保存退出   Esc 放弃退出"
    out.append(f"{CSI}2m{hint}{CSI}0m")
    sys.stdout.write("\n".join(out) + "\n")
    sys.stdout.flush()


def _render_agent_list(all_tabs, cur_tab_idx, agents, cur_idx, current_id, focus, dirty):
    out = _render_tabs(all_tabs, cur_tab_idx, focus, dirty)
    if not agents:
        out.append("  （没有找到智能体配置文件，请在 agents/ 目录下创建 .txt）")
    else:
        for i, a in enumerate(agents):
            active = focus == "items" and i == cur_idx
            pointer = "▶ " if active else "  "
            marker = f"{CSI}2m  ◀ 当前{CSI}0m" if a["id"] == current_id else ""
            model = a["model"] if a["model"] else "全局"
            line = f"{pointer}{a['name']} (@{a['id']})   {model}"
            if active:
                line = f"{CSI}1m{line}{CSI}0m"
            out.append(line + marker)
    out.append("─" * 60)
    if focus == "tabs":
        hint = "←→ 切换分类   ↓ 进入列表   Esc 退出"
    else:
        hint = "↑↓ 选择（顶部↑返回分类）   Enter 查看详情   Esc 退出"
    out.append(f"{CSI}2m{hint}{CSI}0m")
    sys.stdout.write("\n".join(out) + "\n")
    sys.stdout.flush()


def _render_agent_detail(agent):
    out = []
    out.append(CSI + "2J" + CSI + "H")
    out.append(f"📄 智能体详情: {agent['name']} (@{agent['id']})")
    out.append("─" * 60)
    path = agent.get("file", "")
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        content = f"（无法读取文件: {e}）"
    for line in content.split("\n"):
        out.append("  " + line)
    out.append("─" * 60)
    out.append(f"{CSI}2m只读查看   Esc / Enter 返回列表{CSI}0m")
    sys.stdout.write("\n".join(out) + "\n")
    sys.stdout.flush()


def open_config_tui(current_agent_id=None):
    if not _supported():
        return False, None, "当前终端不支持交互式配置（需要真实 TTY），请直接编辑 config.txt"

    from .agent_manager import list_agents

    schema = get_config_schema()
    values = dict(load_config())
    groups = _group_order(schema)
    all_tabs = groups + ["智能体"]
    agent_tab_idx = len(groups)
    cur_tab_idx = 0
    cur_item_idx = 0
    agent_idx = 0
    agent_mode = "list"
    focus = "tabs"
    dirty = False
    tab_count = len(all_tabs)

    try:
        sys.stdout.write(CSI + "?25l")
        with _KeyReader() as kr:
            while True:
                if cur_tab_idx == agent_tab_idx:
                    agents = list_agents()
                    if agent_idx >= len(agents):
                        agent_idx = max(0, len(agents) - 1)
                    if agent_mode == "detail" and agents:
                        _render_agent_detail(agents[agent_idx])
                        key = kr.read_key()
                        if key in ("esc", "enter", "ctrl_c"):
                            agent_mode = "list"
                        continue
                    _render_agent_list(all_tabs, cur_tab_idx, agents, agent_idx, current_agent_id, focus, dirty)
                    key = kr.read_key()
                    if key in ("esc", "ctrl_c"):
                        return False, None, None
                    if focus == "tabs":
                        if key == "left":
                            cur_tab_idx = (cur_tab_idx - 1) % tab_count
                            cur_item_idx = 0
                            agent_mode = "list"
                            continue
                        if key == "right":
                            cur_tab_idx = (cur_tab_idx + 1) % tab_count
                            cur_item_idx = 0
                            agent_mode = "list"
                            continue
                        if key == "down" and agents:
                            focus = "items"
                            agent_idx = 0
                            continue
                        continue
                    else:
                        if key == "up":
                            if agent_idx == 0:
                                focus = "tabs"
                            else:
                                agent_idx -= 1
                            continue
                        if key == "down" and agents:
                            if agent_idx < len(agents) - 1:
                                agent_idx += 1
                            continue
                        if key == "enter" and agents:
                            agent_mode = "detail"
                            continue
                        continue

                items = [it for it in schema if it.get("group") == groups[cur_tab_idx]]
                if cur_item_idx >= len(items):
                    cur_item_idx = max(0, len(items) - 1)
                _render_config(all_tabs, cur_tab_idx, items, cur_item_idx, values, focus, dirty)
                key = kr.read_key()

                if key in ("esc", "ctrl_c"):
                    return False, None, None
                if key == "enter":
                    ok, err = save_config(values)
                    if ok:
                        return True, values, None
                    return False, None, err
                if focus == "tabs":
                    if key == "left":
                        cur_tab_idx = (cur_tab_idx - 1) % tab_count
                        cur_item_idx = 0
                        continue
                    if key == "right":
                        cur_tab_idx = (cur_tab_idx + 1) % tab_count
                        cur_item_idx = 0
                        continue
                    if key == "down" and items:
                        focus = "items"
                        cur_item_idx = 0
                        continue
                    continue
                else:
                    if key == "up":
                        if cur_item_idx == 0:
                            focus = "tabs"
                        else:
                            cur_item_idx -= 1
                        continue
                    if key == "down":
                        if cur_item_idx < len(items) - 1:
                            cur_item_idx += 1
                        continue
                    if key in ("left", "right"):
                        it = items[cur_item_idx]
                        direction = -1 if key == "left" else 1
                        old = values[it["key"]]
                        new_val = _step_value(it, old, direction)
                        if new_val != old:
                            values[it["key"]] = new_val
                            dirty = True
                        continue
    finally:
        sys.stdout.write(CSI + "?25h")
        sys.stdout.write(CSI + "0m")
        sys.stdout.flush()
