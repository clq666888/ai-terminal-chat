import sys
import os
import signal
import time

from .chat_core import parse_stream_chunk

abort_flag = False
_abort_callback = None
_prev_sigint = None


class AbortInterrupt(BaseException):
    pass


def _sigint_handler(signum, frame):
    global abort_flag
    abort_flag = True
    if _abort_callback:
        try:
            _abort_callback()
        except Exception:
            pass


def set_abort_callback(cb):
    global _abort_callback
    _abort_callback = cb


def clear_abort_callback():
    global _abort_callback
    _abort_callback = None


def start_abort_listener():
    global abort_flag, _prev_sigint
    abort_flag = False
    _prev_sigint = signal.signal(signal.SIGINT, _sigint_handler)


def stop_abort_listener():
    global _prev_sigint
    if _prev_sigint is not None:
        try:
            signal.signal(signal.SIGINT, _prev_sigint)
        except Exception:
            pass
        _prev_sigint = None


def pause_listener():
    pass


def resume_listener():
    pass


def is_aborted():
    return abort_flag


class TerminalManager:
    def __init__(self):
        pass

    def __enter__(self):
        start_abort_listener()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        stop_abort_listener()
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
