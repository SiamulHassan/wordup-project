from __future__ import annotations

from types import SimpleNamespace

from PySide6.QtCore import Qt

from app.gui_impl import WordTableModel
from app.state import DetectedWord
from automation.search_controller import screen_result_candidates


def test_checkbox_accepts_integer_qt_state_after_deselect() -> None:
    model = WordTableModel()
    model.replace([DetectedWord("Inevitable", selected=False)])
    index = model.index(0, 0)
    assert model.setData(index, Qt.CheckState.Checked.value, Qt.CheckStateRole)
    assert model.words[0].selected is True
    assert model.setData(index, Qt.CheckState.Unchecked, Qt.CheckStateRole)
    assert model.words[0].selected is False


def test_search_field_echo_is_not_treated_as_a_result() -> None:
    query_echo = SimpleNamespace(bbox=(200, 125, 303, 147))
    result = SimpleNamespace(bbox=(46, 199, 154, 222))
    assert screen_result_candidates([query_echo, result], 972) == [result]
