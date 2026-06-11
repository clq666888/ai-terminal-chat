import sys
import os
import atexit
import threading
import time
import termios
import tty
import select
import ctypes

from .chat_core import parse_stream_chunk

generating = False
abort_flag = False
listener_stop = threading.Event()
_old_termios_global = None
_listener_global = None
_abort_callback = None
_main_thread_id = threading.main_thread().ident


class AbortInterrupt(BaseException):
    pass


def set_abort_callback(cb):
    global _abort_callback
    _abort_callback = cb


def clear_abort_callback():
    global _abort_callback
    _abort_callback = None

_initial_termios = None


def _save_initial_termios():
    global _initial_termios
    try:
        fd = sys.stdin.fileno()
        _initial_termios = termios.tcgetattr(fd)
    except Exception:
        pass


def _restore_terminal():
    try:
        sys.stdout.write("\033[0m")
        sys.stdout.flush()
    except Exception:
        pass
    if _initial_termios:
        try:
            termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, _initial_termios)
        except Exception:
            pass


_save_initial_termios()
atexit.register(_restore_terminal)


def _inject_abort_to_main():
    try:
        ret = ctypes.pythonapi.PyThreadState_SetAsyncExc(
            ctypes.c_ulong(_main_thread_id),
            ctypes.py_object(AbortInterrupt)
        )
        if ret == 0:
            pass
        elif ret > 1:
            ctypes.pythonapi.PyThreadState_SetAsyncExc(
                ctypes.c_ulong(_main_thread_id), None
            )
    except Exception:
        pass


def _key_listener():
    global generating, abort_flag
    while not listener_stop.is_set():
        r, _, _ = select.select([sys.stdin], [], [], 0.1)
        if not r:
            continue
        try:
            ch = sys.stdin.read(1)
        except Exception:
            break

        if ch == '\x11':
            abort_flag = True
            generating = False
            if _abort_callback:
                try:
                    _abort_callback()
                except Exception:
                    pass
            sys.stdout.write("\n\n\U0001f6d1 已中断生成")
            sys.stdout.flush()
            break

        if not generating:
            continue


def start_abort_listener():
    global generating, abort_flag, _old_termios_global, _listener_global

    abort_flag = False
    generating = True
    listener_stop.clear()

    if not sys.stdin.isatty():
        return

    fd = sys.stdin.fileno()
    _old_termios_global = termios.tcgetattr(fd)
    tty.setcbreak(fd)
    new_attr = termios.tcgetattr(fd)
    new_attr[0] &= ~(termios.IXON | termios.IXOFF)
    termios.tcsetattr(fd, termios.TCSANOW, new_attr)

    _listener_global = threading.Thread(target=_key_listener, daemon=True)
    _listener_global.start()


def stop_abort_listener():
    global generating, _old_termios_global, _listener_global

    generating = False
    listener_stop.set()

    if _listener_global:
        try:
            _listener_global.join(timeout=0.5)
        except (AbortInterrupt, BaseException):
            pass
        _listener_global = None

    if _old_termios_global:
        try:
            termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, _old_termios_global)
            termios.tcflush(sys.stdin, termios.TCIOFLUSH)
        except Exception:
            pass
        _old_termios_global = None


def pause_listener():
    global generating
    generating = False


def resume_listener():
    global generating
    if abort_flag:
        return
    generating = True


def is_aborted():
    return abort_flag


class TerminalManager:
    def __init__(self):
        self._old_termios = None
        self._listener = None

    def __enter__(self):
        global generating, abort_flag

        fd = sys.stdin.fileno()
        self._old_termios = termios.tcgetattr(fd)
        tty.setcbreak(fd)
        new_attr = termios.tcgetattr(fd)
        new_attr[0] &= ~(termios.IXON | termios.IXOFF)
        termios.tcsetattr(fd, termios.TCSANOW, new_attr)

        abort_flag = False
        generating = True
        listener_stop.clear()

        self._listener = threading.Thread(target=_key_listener, daemon=True)
        self._listener.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        global generating

        generating = False
        listener_stop.set()

        if self._listener:
            try:
                self._listener.join(timeout=0.5)
            except (AbortInterrupt, BaseException):
                pass

        if self._old_termios:
            termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, self._old_termios)
            termios.tcflush(sys.stdin, termios.TCIOFLUSH)

        return False


def stream_output(response, ai_name):
    global abort_flag
    full_reply = ""
    sys.stdout.write(f"{ai_name}: ")
    sys.stdout.flush()

    for line in response.iter_lines(decode_unicode=True):
        if abort_flag:
            break
        content = parse_stream_chunk(line)
        if content is None:
            break
        if content:
            if abort_flag:
                break
            sys.stdout.write(content)
            sys.stdout.flush()
            full_reply += content

    sys.stdout.write("\n")
    return None if abort_flag else full_reply
