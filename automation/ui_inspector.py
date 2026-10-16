"""Dump the real UI Automation tree without assuming control identifiers."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from automation.wordup_window import WordUpWindow


def _describe(control: object, depth: int) -> str:
    info = control.element_info
    rect = getattr(info, "rectangle", None)
    rectangle = ""
    if rect is not None:
        rectangle = f"({rect.left},{rect.top},{rect.right},{rect.bottom})"
    try:
        enabled = control.is_enabled()
    except Exception:
        enabled = "?"
    try:
        visible = control.is_visible()
    except Exception:
        visible = "?"
    return (
        f"{'  ' * depth}control_type={info.control_type!r} name={info.name!r} "
        f"automation_id={info.automation_id!r} class_name={info.class_name!r} "
        f"rectangle={rectangle} enabled={enabled} visible={visible}"
    )


class UIInspector:
    def inspect(self, target: WordUpWindow, output: Path) -> list[str]:
        if target.window is None:
            target.connect()
        lines = [
            f"WordUp UI Automation tree captured {datetime.now().isoformat()}",
            f"Window handle: {target.handle}",
            "",
        ]
        stack: list[tuple[object, int]] = [(target.window, 0)]
        while stack:
            control, depth = stack.pop()
            try:
                lines.append(_describe(control, depth))
                children = list(control.children())
            except Exception as exc:
                lines.append(f"{'  ' * depth}<inspection error: {exc}>")
                continue
            stack.extend((child, depth + 1) for child in reversed(children))
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text("\n".join(lines), encoding="utf-8")
        return lines
