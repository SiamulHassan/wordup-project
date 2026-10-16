"""End-to-end packaged GUI test: add one screenshot and wait for extracted words."""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

from pywinauto import Desktop


def main() -> int:
    executable = Path(sys.argv[1]).resolve()
    screenshot = Path(sys.argv[2]).resolve()
    expected_fragments = (sys.argv[3:] or
                          ["Purple tiles: 63", "Unique: 63"])
    process = subprocess.Popen([str(executable)])
    window = None
    try:
        window = Desktop(backend="uia").window(title="WordUp Vocabulary Importer")
        window.wait("visible enabled", timeout=45)
        time.sleep(5)
        window.set_focus()
        time.sleep(0.5)
        window.child_window(title="Add Screenshot(s)", control_type="Button").click_input()
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
        filename = next(control for control in window.descendants(control_type="Edit") if (control.element_info.name or "").strip() == "File name:")
        filename.set_edit_text(str(screenshot))
        open_button = next(control for control in window.descendants(control_type="Button") if (control.element_info.name or "").strip() == "Open")
        time.sleep(0.5)
        open_button.click_input()
        window.wait("visible enabled", timeout=15)
        window.child_window(title="Analyze Screenshots", control_type="Button").click_input()
        deadline = time.monotonic() + 150
        while time.monotonic() < deadline:
            for control in window.descendants(control_type="Text"):
                text = (control.window_text() or "").strip()
                if all(fragment in text for fragment in expected_fragments):
                    print("PACKAGED_EXTRACTION_OK", text)
                    return 0
            time.sleep(0.5)
        print("PACKAGED_EXTRACTION_TIMEOUT")
        return 1
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
