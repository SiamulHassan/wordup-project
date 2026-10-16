"""Standalone diagnostic for discovering WordUp's actual UIA structure."""

from __future__ import annotations

from automation.ui_inspector import UIInspector
from automation.wordup_window import WordUpWindow
from utils.config import load_config
from utils.logger import configure_logging
from utils.paths import ensure_runtime_dirs


def main() -> int:
    paths = ensure_runtime_dirs()
    config = load_config()
    configure_logging(paths["logs"], str(config.get("logging.level", "INFO")))
    target = WordUpWindow(str(config.get("wordup.window_title_regex", ".*WordUp.*")))
    windows = target.discover()
    if not windows:
        print("No WordUp window found. Open WordUp and run this utility again.")
        return 1
    for item in windows:
        print(f"handle={item.handle} pid={item.process_id} title={item.title!r} rect={item.rectangle}")
    target.connect()
    output = paths["logs"] / "wordup_ui_tree.txt"
    lines = UIInspector().inspect(target, output)
    print(f"Saved {len(lines)} UIA tree lines to: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
