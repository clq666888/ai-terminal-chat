import sys
import threading
import time


class Spinner:
    FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

    def __init__(self, message="AI 正在思考"):
        self.message = message
        self._stop = threading.Event()
        self._thread = None
        self._started = False

    def start(self):
        self._stop.clear()
        self._started = True
        self._thread = threading.Thread(target=self._spin, daemon=True)
        self._thread.start()

    def stop(self):
        if not self._started:
            return
        self._started = False
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=1)
            self._thread = None
        sys.stdout.write("\r\033[K")
        sys.stdout.flush()

    def _spin(self):
        i = 0
        while not self._stop.is_set():
            frame = self.FRAMES[i % len(self.FRAMES)]
            sys.stdout.write(f"\r\033[K{frame} {self.message}...")
            sys.stdout.flush()
            time.sleep(0.08)
            i += 1
