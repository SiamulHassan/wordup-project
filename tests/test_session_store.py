from __future__ import annotations

from app.state import DetectedWord, ImportResult
from storage.session_store import SessionStore


def test_session_round_trip(tmp_path) -> None:
    store = SessionStore(tmp_path)
    session = store.create([DetectedWord("Inevitable")], dry_run=True)
    session.words[0].result = ImportResult.DRY_RUN_OK
    path = store.save(session)
    loaded = store.load(path)
    assert loaded.session_id == session.session_id
    assert loaded.words[0].text == "Inevitable"
    assert loaded.words[0].result == ImportResult.DRY_RUN_OK


def test_latest_resumable_ignores_clean_session(tmp_path) -> None:
    store = SessionStore(tmp_path)
    session = store.create([DetectedWord("Scale")], dry_run=True)
    session.stopped_cleanly = True
    store.save(session)
    assert store.latest_resumable() is None
