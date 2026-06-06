import sys
import threading
import time
import termios
import tty
import select

from chat_core import parse_stream_chunk

generating = False
abort_flag = False
listener_stop = threading.Event()


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

        if not generating:
            continue

        if ch == '\x11':
            abort_flag = True
            generating = False
            sys.stdout.write("\n\n🛑 已中断生成")
            sys.stdout.flush()
            break


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
            self._listener.join(timeout=0.3)

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
