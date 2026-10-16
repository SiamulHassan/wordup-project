"""Verify the packaged screenshot chooser opens, closes, and returns control to the GUI."""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

from pywinauto import Desktop


def main() -> int:
    process = subprocess.Popen([str(Path(sys.argv[1]).resolve())])
    window = None
    try:
        window = Desktop(backend="uia").window(title="WordUp Vocabulary Importer")
        window.wait("visible enabled", timeout=40)
        time.sleep(5)
        window.set_focus()
        time.sleep(0.5)
        button = window.child_window(title="Add Screenshot(s)", control_type="Button")
        button.wait("visible enabled", timeout=10)
        button.click_input()
        deadline = time.monotonic() + 20
        dialog = None
        while time.monotonic() < deadline and dialog is None:
            dialog = next((control for control in window.descendants(control_type="Window")
                           if control.window_text() == "Add Knowledge Map screenshots"
                           and control.is_visible() and control.is_enabled()), None)
            if dialog is None:
                time.sleep(0.25)
        if dialog is None:
            raise TimeoutError("Packaged screenshot dialog did not appear.")
        print(f"DIALOG_OK title={dialog.window_text()!r} enabled={dialog.is_enabled()}")
        dialog.type_keys("{ESC}")
        window.wait("visible enabled", timeout=10)
        print("MAIN_WINDOW_RESPONSIVE_AFTER_CANCEL")
        window.close()
        time.sleep(2)
        return 0
    finally:
        if window is not None:
            try:
                window.type_keys("{ESC}")
                window.close()
            except Exception:
                pass
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()


if __name__ == "__main__":
    raise SystemExit(main())
