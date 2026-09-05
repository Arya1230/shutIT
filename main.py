"""
main.py - Entry point. Wires hotkey listener + GUI together.
"""

import threading
import keyboard
import mic_logic
from ui import App


def _hotkey_thread(app: App):
    """Runs keyboard listener in background; posts toggle to GUI thread."""
    def _on_hotkey():
        app.after(0, app._toggle)

    keyboard.add_hotkey(mic_logic.HOTKEY, _on_hotkey)
    keyboard.wait()   # blocks the thread forever


if __name__ == "__main__":
    app = App()
    t = threading.Thread(target=_hotkey_thread, args=(app,), daemon=True)
    t.start()
    app.mainloop()
