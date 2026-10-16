from __future__ import annotations

from automation.wordup_window import is_wordup_app_window


def test_exact_wordup_title_is_accepted() -> None:
    assert is_wordup_app_window("WordUp", "FLUTTER_RUNNER_WIN32_WINDOW")


def test_flutter_wordup_variant_is_accepted() -> None:
    assert is_wordup_app_window(
        "WordUp - Learn English Words", "FLUTTER_RUNNER_WIN32_WINDOW"
    )


def test_unrelated_project_window_is_rejected() -> None:
    assert not is_wordup_app_window(
        "wordup-exe - Visual Studio Code", "Chrome_WidgetWin_1"
    )
