import sys

if sys.platform == "win32":
    from .terminal_windows import *
    from . import terminal_windows as _platform_mod
else:
    from .terminal_linux import *
    from . import terminal_linux as _platform_mod


def get_abort_flag():
    return _platform_mod.abort_flag


def set_abort_flag(value):
    _platform_mod.abort_flag = value
