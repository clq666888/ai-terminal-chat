import sys
import threading
import time
import ctypes
import msvcrt

from .chat_core import parse_stream_chunk

generating = False
abort_flag = False
listener_stop = threading.Event()
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


def _inject_abort_to_main():
    try:
        ret = ctypes.pythonapi.PyThreadState_SetAsyncExc(
            ctypes.c_ulong(_main_thread_id),
            ctypes.py_object(AbortInterrupt)
        )
        if ret > 1:
            ctypes.pythonapi.PyThreadState_SetAsyncExc(
                ctypes.c_ulong(_main_thread_id), None
            )
    except Exception:
        pass


def _key_listener():
    global generating, abort_flag
    while not listener_stop.is_set():
        if not msvcrt.kbhit():
            time.sleep(0.05)
            continue

        ch = msvcrt.getch()

        if ch == b'\x11':
            abort_flag = True
            generating = False
            if _abort_callback:
                try:
                    _abort_callback()
                except Exception:
                    pass
            _inject_abort_to_main()
            sys.stdout.write("\n\n\U0001f6d1 已中断生成")
            sys.stdout.flush()
            break

        if not generating:
            continue


def start_abort_listener():
    global generating, abort_flag

    abort_flag = False
    generating = True
    listener_stop.clear()

    t = threading.Thread(target=_key_listener, daemon=True)
    t.start()


def stop_abort_listener():
    global generating

    generating = False
    listener_stop.set()


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
        self._listener = None

    def __enter__(self):
        global generating, abort_flag

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
            self._listener.join(timeout=0.3)

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
