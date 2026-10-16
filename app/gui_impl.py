"""PySide6 review, diagnostics, and import user interface."""

from __future__ import annotations

import logging
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from PySide6.QtCore import (QAbstractTableModel, QModelIndex, QObject, QPoint, QSize,
                            QSortFilterProxyModel, Qt, QThread, QTimer, Signal, Slot)
from PySide6.QtGui import (QAction, QColor, QCursor, QDragEnterEvent, QDropEvent, QIcon,
                           QImageReader, QKeySequence, QPixmap, QShortcut)
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QCheckBox, QDialog, QFileDialog,
                               QFormLayout, QGridLayout, QGroupBox, QHBoxLayout, QHeaderView,
                               QLabel, QLineEdit, QListWidget, QListWidgetItem, QMainWindow,
                               QMenu, QMessageBox, QProgressBar, QPushButton, QSpinBox,
                               QSplitter, QTableView, QTextEdit, QToolButton, QVBoxLayout, QWidget)

from app.controller import AppController
from app.state import DetectedWord, ExtractionStats, ImportResult, ReviewStatus, SessionState
from extraction.screenshot_loader import SUPPORTED_EXTENSIONS, discover_images
from extraction.word_normalizer import deduplicate, normalize_display
from storage.history import HistoryStore

LOGGER = logging.getLogger(__name__)


class WordTableModel(QAbstractTableModel):
    HEADERS = ("Import", "Word", "Confidence", "Source", "Review", "Result")

    def __init__(self) -> None:
        super().__init__()
        self.words: list[DetectedWord] = []

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.words)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.HEADERS)

    def headerData(self, section: int, orientation: Qt.Orientation,
                   role: int = Qt.DisplayRole) -> Any:
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self.HEADERS[section]
        return super().headerData(section, orientation, role)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:
        if not index.isValid():
            return None
        word = self.words[index.row()]
        column = index.column()
        if role == Qt.CheckStateRole and column == 0:
            return Qt.Checked if word.selected else Qt.Unchecked
        if role in {Qt.DisplayRole, Qt.EditRole}:
            values = (
                "",
                word.text,
                f"{word.confidence:.0%}",
                word.source_display,
                word.review_status.value,
                word.result.value,
            )
            return values[column]
        if role == Qt.BackgroundRole and word.review_status == ReviewStatus.LOW_CONFIDENCE:
            return QColor("#fff0c7")
        if role == Qt.ForegroundRole:
            if word.result in {ImportResult.FAILED, ImportResult.NOT_FOUND, ImportResult.AMBIGUOUS}:
                return QColor("#a81d1d")
            if word.result in {ImportResult.UPDATED, ImportResult.ALREADY_SHOULD_LEARN,
                               ImportResult.DRY_RUN_OK}:
                return QColor("#126b38")
        if role == Qt.ToolTipRole and word.error:
            return word.error
        return None

    def flags(self, index: QModelIndex) -> Qt.ItemFlags:
        flags = super().flags(index) | Qt.ItemIsEnabled | Qt.ItemIsSelectable
        if index.column() == 0:
            flags |= Qt.ItemIsUserCheckable
        if index.column() == 1:
            flags |= Qt.ItemIsEditable
        return flags

    def setData(self, index: QModelIndex, value: Any, role: int = Qt.EditRole) -> bool:
        if not index.isValid():
            return False
        word = self.words[index.row()]
        if index.column() == 0 and role == Qt.CheckStateRole:
            raw_state = value.value if isinstance(value, Qt.CheckState) else int(value)
            word.selected = raw_state == Qt.CheckState.Checked.value
            word.review_status = (ReviewStatus.READY
                                  if word.review_status == ReviewStatus.EXCLUDED
                                  else word.review_status)
        elif index.column() == 1 and role == Qt.EditRole:
            normalized = normalize_display(str(value))
            if not normalized:
                return False
            word.text = normalized
            word.review_status = ReviewStatus.MANUAL
        else:
            return False
        self.dataChanged.emit(index, index, [role])
        return True

    def replace(self, words: list[DetectedWord]) -> None:
        self.beginResetModel()
        self.words = words
        self.endResetModel()

    def refresh(self) -> None:
        if self.words:
            self.dataChanged.emit(self.index(0, 0), self.index(len(self.words) - 1,
                                                             self.columnCount() - 1))


class WordFilterProxy(QSortFilterProxyModel):
    def filterAcceptsRow(self, source_row: int, parent: QModelIndex) -> bool:
        pattern = self.filterRegularExpression().pattern().casefold()
        if not pattern:
            return True
        model = self.sourceModel()
        word = model.words[source_row]
        return pattern in " ".join((word.text, word.source_display, word.review_status.value,
                                    word.result.value)).casefold()


class ExtractionWorker(QObject):
    progress = Signal(int, int, str)
    completed = Signal(object, object)
    failed = Signal(str)
    finished = Signal()

    def __init__(self, controller: AppController, paths: list[Path], debug: bool) -> None:
        super().__init__()
        self.controller = controller
        self.paths = paths
        self.debug = debug

    @Slot()
    def run(self) -> None:
        try:
            words, stats = self.controller.extract(
                self.paths, self.debug,
                lambda done, total, text: self.progress.emit(done, total, text),
            )
            self.completed.emit(words, stats)
        except Exception as exc:
            LOGGER.exception("Screenshot extraction failed")
            self.failed.emit(str(exc))
        finally:
            self.finished.emit()


class ImportWorker(QObject):
    progress = Signal(int, int, str)
    word_done = Signal(int, str)
    failed = Signal(str)
    completed = Signal(bool)

    def __init__(self, controller: AppController, indices: list[int], dry_run: bool) -> None:
        super().__init__()
        self.controller = controller
        self.indices = indices
        self.dry_run = dry_run

    @Slot()
    def run(self) -> None:
        engine = self.controller.engine
        session = self.controller.session
        if engine is None or session is None:
            self.failed.emit("WordUp is not connected or the import session was not created.")
            self.completed.emit(False)
            return
        engine.reset_control()
        clean = True
        try:
            for position, index in enumerate(self.indices, start=1):
                if engine.stop_event.is_set():
                    clean = False
                    break
                word = session.words[index]
                self.progress.emit(position - 1, len(self.indices), f"Current word: {word.text}")
                result = engine.process_word(word, self.dry_run,
                                             lambda message: self.progress.emit(
                                                 position - 1, len(self.indices), message))
                self.controller.persist_word(index)
                self.word_done.emit(index, result.value)
            self.progress.emit(len(self.indices), len(self.indices),
                               "Import complete" if clean else "Stopped safely")
        except Exception as exc:
            clean = False
            LOGGER.exception("Import worker failed")
            self.failed.emit(str(exc))
        finally:
            self.controller.finish_session(clean)
            self.completed.emit(clean)


class LogEmitter(QObject):
    message = Signal(str)


class QtLogHandler(logging.Handler):
    def __init__(self, emitter: LogEmitter) -> None:
        super().__init__()
        self.emitter = emitter
        self.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s  %(message)s", "%H:%M:%S"))

    def emit(self, record: logging.LogRecord) -> None:
        self.emitter.message.emit(self.format(record))


class CalibrationDialog(QDialog):
    """Capture fallback points as proportions of the live WordUp window."""

    POINTS = (
        ("search_icon", "Search icon"),
        ("search_box", "Search text box"),
        ("should_learn", "Should Learn button"),
        ("back", "Back button"),
    )

    def __init__(self, controller: AppController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.controller = controller
        self.setWindowTitle("Window-relative fallback calibration")
        self.setMinimumWidth(520)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            "For each point, open the appropriate WordUp screen, click Capture, then place the mouse "
            "over the requested control. Its position is recorded after three seconds."
        ))
        self.form = QFormLayout()
        self.labels: dict[str, QLabel] = {}
        calibration = controller.config.get("automation.calibration", {})
        for key, title in self.POINTS:
            row = QHBoxLayout()
            label = QLabel(self._display(calibration.get(key)))
            self.labels[key] = label
            button = QPushButton("Capture in 3 seconds")
            button.clicked.connect(lambda checked=False, point=key: self.capture(point))
            row.addWidget(label, 1)
            row.addWidget(button)
            self.form.addRow(title, row)
        layout.addLayout(self.form)
        close = QPushButton("Done")
        close.clicked.connect(self.accept)
        layout.addWidget(close)

    @staticmethod
    def _display(value: Any) -> str:
        if isinstance(value, dict) and "x" in value and "y" in value:
            return f"{float(value['x']):.3f}, {float(value['y']):.3f} of WordUp window"
        return "Not calibrated"

    def capture(self, key: str) -> None:
        if self.controller.target.window is None:
            QMessageBox.warning(self, "Connect first", "Connect to WordUp before calibration.")
            return
        self.hide()
        QTimer.singleShot(3000, lambda: self._finish_capture(key))

    def _finish_capture(self, key: str) -> None:
        cursor = QCursor.pos()
        left, top, right, bottom = self.controller.target.rectangle()
        if not (left <= cursor.x() <= right and top <= cursor.y() <= bottom):
            self.show()
            QMessageBox.warning(self, "Outside WordUp", "The mouse was outside the WordUp window.")
            return
        value = {
            "x": (cursor.x() - left) / max(right - left, 1),
            "y": (cursor.y() - top) / max(bottom - top, 1),
        }
        calibration = dict(self.controller.config.get("automation.calibration", {}))
        calibration[key] = value
        self.controller.config.set("automation.calibration", calibration)
        self.controller.config.save()
        self.labels[key].setText(self._display(value))
        self.show()
        self.activateWindow()


class MainWindow(QMainWindow):
    IMAGE_FILTER = "Images (*.png *.jpg *.jpeg *.webp)"
    WORD_FILTER = "Word lists (*.txt *.csv *.json)"

    def __init__(self, controller: AppController) -> None:
        super().__init__()
        self.controller = controller
        self.setWindowTitle("WordUp Vocabulary Importer")
        self.resize(1380, 880)
        self.setAcceptDrops(True)
        self.model = WordTableModel()
        self.proxy = WordFilterProxy()
        self.proxy.setSourceModel(self.model)
        self.proxy.setDynamicSortFilter(True)
        self.stats = ExtractionStats()
        self.extract_thread: QThread | None = None
        self.import_thread: QThread | None = None
        self.extract_worker: ExtractionWorker | None = None
        self.import_worker: ImportWorker | None = None
        self._build_menu()
        self._build_ui()
        self._install_logging()
        self._install_shortcuts()
        QTimer.singleShot(300, self._offer_resume)

    def _build_menu(self) -> None:
        advanced = self.menuBar().addMenu("Advanced")
        inspect_action = QAction("Inspect WordUp UIA Tree", self)
        inspect_action.triggered.connect(self.inspect_ui)
        advanced.addAction(inspect_action)
        calibration_action = QAction("Fallback Calibration…", self)
        calibration_action.triggered.connect(lambda: CalibrationDialog(self.controller, self).exec())
        advanced.addAction(calibration_action)
        open_logs = QAction("Show runtime paths", self)
        open_logs.triggered.connect(self.show_runtime_paths)
        advanced.addAction(open_logs)

    def _build_ui(self) -> None:
        central = QWidget()
        root = QVBoxLayout(central)
        title_row = QHBoxLayout()
        title = QLabel("WordUp Vocabulary Importer")
        title.setStyleSheet("font-size: 22px; font-weight: 700; color: #43145d")
        title_row.addWidget(title)
        title_row.addStretch()
        self.connection_badge = QLabel("WordUp not detected")
        self.connection_badge.setStyleSheet("padding: 6px 12px; background: #f5d8d8; border-radius: 8px")
        title_row.addWidget(self.connection_badge)
        root.addLayout(title_row)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self._screenshot_panel())
        splitter.addWidget(self._vocabulary_panel())
        splitter.addWidget(self._automation_panel())
        splitter.setSizes([310, 720, 330])
        root.addWidget(splitter, 1)

        progress_group = QGroupBox("Progress / Log")
        progress_layout = QVBoxLayout(progress_group)
        status_row = QHBoxLayout()
        self.current_status = QLabel("Ready — add screenshots or import a word list")
        self.progress_label = QLabel("0 / 0")
        status_row.addWidget(self.current_status, 1)
        status_row.addWidget(self.progress_label)
        progress_layout.addLayout(status_row)
        self.progress_bar = QProgressBar()
        progress_layout.addWidget(self.progress_bar)
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumHeight(145)
        progress_layout.addWidget(self.log_view)
        root.addWidget(progress_group)
        self.setCentralWidget(central)

    def _screenshot_panel(self) -> QWidget:
        group = QGroupBox("1. Screenshot Input")
        layout = QVBoxLayout(group)
        hint = QLabel("Drop PNG, JPG, JPEG, or WEBP Knowledge Map screenshots here.")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        self.screenshot_list = QListWidget()
        self.screenshot_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.screenshot_list.setIconSize(QSize(84, 60))
        layout.addWidget(self.screenshot_list, 1)
        row = QGridLayout()
        add = QPushButton("Add Screenshot(s)")
        add.clicked.connect(self.add_screenshots)
        folder = QPushButton("Add Folder")
        folder.clicked.connect(self.add_folder)
        remove = QPushButton("Remove Selected")
        remove.clicked.connect(self.remove_screenshots)
        clear = QPushButton("Clear All")
        clear.clicked.connect(self.screenshot_list.clear)
        row.addWidget(add, 0, 0)
        row.addWidget(folder, 0, 1)
        row.addWidget(remove, 1, 0)
        row.addWidget(clear, 1, 1)
        layout.addLayout(row)
        self.debug_check = QCheckBox("Save extraction debug images")
        layout.addWidget(self.debug_check)
        analyze = QPushButton("Analyze Screenshots")
        analyze.setStyleSheet("padding: 9px; font-weight: 700; background: #a91ff0; color: white")
        analyze.clicked.connect(self.analyze)
        self.analyze_button = analyze
        layout.addWidget(analyze)
        return group

    def _vocabulary_panel(self) -> QWidget:
        group = QGroupBox("2. Extraction Preview & Vocabulary Review")
        layout = QVBoxLayout(group)
        self.stats_label = QLabel("Screenshots: 0  •  Purple tiles: 0  •  "
                                  "White tiles: 0  •  Cyan ignored: 0  •  Unique: 0  •  Review: 0")
        layout.addWidget(self.stats_label)
        filter_row = QHBoxLayout()
        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText("Search/filter words, sources, or statuses")
        self.filter_edit.textChanged.connect(self.proxy.setFilterFixedString)
        filter_row.addWidget(self.filter_edit, 1)
        add_word = QPushButton("Add Word")
        add_word.clicked.connect(self.add_manual_word)
        delete = QPushButton("Delete Selected")
        delete.clicked.connect(self.delete_selected_words)
        filter_row.addWidget(add_word)
        filter_row.addWidget(delete)
        layout.addLayout(filter_row)
        self.table = QTableView()
        self.table.setModel(self.proxy)
        self.table.setSortingEnabled(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        layout.addWidget(self.table, 1)
        controls = QHBoxLayout()
        for title, callback in (
            ("Select All", lambda: self.set_all_selected(True)),
            ("Deselect All", lambda: self.set_all_selected(False)),
            ("Remove Duplicates", self.remove_duplicates),
            ("Mark Completed", self.mark_completed),
            ("Skip", self.mark_skipped),
        ):
            button = QPushButton(title)
            button.clicked.connect(callback)
            controls.addWidget(button)
        layout.addLayout(controls)
        io_row = QHBoxLayout()
        load = QPushButton("Load TXT/CSV/JSON")
        load.clicked.connect(self.load_word_list)
        export = QPushButton("Export Word List")
        export.clicked.connect(self.export_word_list)
        report = QPushButton("Export Report")
        report.clicked.connect(self.export_report)
        io_row.addWidget(load)
        io_row.addWidget(export)
        io_row.addWidget(report)
        layout.addLayout(io_row)
        return group

    def _automation_panel(self) -> QWidget:
        group = QGroupBox("3. WordUp Connection & Import")
        layout = QVBoxLayout(group)
        workflow = QLabel(
            "Recommended: Connect → Test One Word → Dry Run → Real Import. "
            "Use calibration only if navigation fails."
        )
        workflow.setWordWrap(True)
        layout.addWidget(workflow)
        refresh = QPushButton("Refresh / Detect WordUp")
        refresh.clicked.connect(self.refresh_wordup)
        connect = QPushButton("Connect")
        connect.clicked.connect(self.connect_wordup)
        front = QPushButton("Bring to Front")
        front.clicked.connect(self.bring_front)
        inspect = QPushButton("Inspect UI")
        inspect.clicked.connect(self.inspect_ui)
        layout.addWidget(refresh)
        layout.addWidget(connect)
        layout.addWidget(front)
        layout.addWidget(inspect)
        layout.addSpacing(10)
        self.dry_run = QCheckBox("Dry Run — never click Should Learn")
        self.dry_run.setChecked(bool(self.controller.config.get("automation.dry_run", True)))
        self.dry_run.setStyleSheet("font-weight: 700; color: #8a3a00")
        layout.addWidget(self.dry_run)
        test = QPushButton("Test One Selected Word")
        test.clicked.connect(self.test_one_word)
        layout.addWidget(test)
        self.start_button = QPushButton("Start Import")
        self.start_button.setStyleSheet("padding: 10px; font-weight: 700; background: #31b8cc; color: white")
        self.start_button.clicked.connect(self.start_import)
        layout.addWidget(self.start_button)
        self.pause_button = QPushButton("Pause")
        self.pause_button.clicked.connect(self.toggle_pause)
        self.pause_button.setEnabled(False)
        layout.addWidget(self.pause_button)
        stop = QPushButton("Stop Safely")
        stop.clicked.connect(self.stop_import)
        layout.addWidget(stop)
        retry = QPushButton("Retry Failed")
        retry.clicked.connect(self.retry_failed)
        layout.addWidget(retry)
        layout.addStretch()
        self.counts_label = QLabel("Success: 0\nAlready set: 0\nNot found: 0\nFailed: 0\nRemaining: 0")
        layout.addWidget(self.counts_label)
        emergency = QLabel("Emergency stop: Ctrl+Shift+Q (PyAutoGUI corner fail-safe also remains enabled)")
        emergency.setWordWrap(True)
        emergency.setStyleSheet("color: #8f1717")
        layout.addWidget(emergency)
        return group

    def _install_logging(self) -> None:
        self.log_emitter = LogEmitter()
        self.log_emitter.message.connect(self.log_view.append)
        self.qt_log_handler = QtLogHandler(self.log_emitter)
        logging.getLogger().addHandler(self.qt_log_handler)

    def _install_shortcuts(self) -> None:
        emergency = QShortcut(QKeySequence("Ctrl+Shift+Q"), self)
        emergency.activated.connect(self.emergency_stop)
        escape = QShortcut(QKeySequence(Qt.Key_Escape), self)
        escape.activated.connect(self.stop_import)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        paths: list[Path] = []
        for url in event.mimeData().urls():
            paths.extend(discover_images(Path(url.toLocalFile())))
        self._add_image_paths(paths)
        event.acceptProposedAction()

    def _add_image_paths(self, paths: list[Path]) -> None:
        existing = {self.screenshot_list.item(i).data(Qt.UserRole)
                    for i in range(self.screenshot_list.count())}
        for path in paths:
            resolved = str(path.resolve())
            if resolved in existing or path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                continue
            item = QListWidgetItem(path.name)
            reader = QImageReader(resolved)
            reader.setAutoTransform(True)
            source_size = reader.size()
            if source_size.isValid():
                reader.setScaledSize(source_size.scaled(QSize(84, 60), Qt.KeepAspectRatio))
            preview = reader.read()
            if not preview.isNull():
                item.setIcon(QIcon(QPixmap.fromImage(preview)))
            item.setData(Qt.UserRole, resolved)
            item.setToolTip(resolved)
            self.screenshot_list.addItem(item)
            existing.add(resolved)

    @Slot()
    def add_screenshots(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(
            self, "Add Knowledge Map screenshots", "", self.IMAGE_FILTER,
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        self._add_image_paths([Path(item) for item in files])

    @Slot()
    def add_folder(self) -> None:
        directory = QFileDialog.getExistingDirectory(
            self, "Add screenshot folder", "",
            QFileDialog.Option.ShowDirsOnly | QFileDialog.Option.DontUseNativeDialog,
        )
        if directory:
            self._add_image_paths(discover_images(Path(directory)))

    @Slot()
    def remove_screenshots(self) -> None:
        for item in self.screenshot_list.selectedItems():
            self.screenshot_list.takeItem(self.screenshot_list.row(item))

    def screenshot_paths(self) -> list[Path]:
        return [Path(self.screenshot_list.item(i).data(Qt.UserRole))
                for i in range(self.screenshot_list.count())]

    @Slot()
    def analyze(self) -> None:
        paths = self.screenshot_paths()
        if not paths:
            QMessageBox.information(self, "No screenshots", "Add one or more screenshots first.")
            return
        self.analyze_button.setEnabled(False)
        self.progress_bar.setRange(0, len(paths))
        thread = QThread(self)
        worker = ExtractionWorker(self.controller, paths, self.debug_check.isChecked())
        LOGGER.info("Starting extraction for %s screenshot(s)", len(paths))
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(self.update_progress)
        worker.completed.connect(self.extraction_completed)
        worker.failed.connect(lambda text: QMessageBox.critical(self, "Extraction failed", text))
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._extraction_thread_finished)
        self.extract_thread = thread
        self.extract_worker = worker
        thread.start()

    @Slot()
    def _extraction_thread_finished(self) -> None:
        self.analyze_button.setEnabled(True)
        self.extract_worker = None
        self.extract_thread = None

    @Slot(object, object)
    def extraction_completed(self, words: list[DetectedWord], stats: ExtractionStats) -> None:
        self.stats = stats
        self.model.replace(words)
        self._update_stats()
        self.current_status.setText("Review extracted words and correct highlighted entries before import.")
        LOGGER.info("Extracted %s unique words from %s purple and %s white tiles; "
                    "ignored %s cyan tiles", stats.unique_words, stats.purple_tiles,
                    stats.white_tiles, stats.cyan_tiles)

    def _update_stats(self) -> None:
        self.stats.unique_words = len(self.model.words)
        self.stats.low_confidence = sum(
            word.review_status == ReviewStatus.LOW_CONFIDENCE for word in self.model.words
        )
        self.stats_label.setText(
            f"Screenshots: {self.stats.screenshots}  •  Purple tiles: {self.stats.purple_tiles}  •  "
            f"White tiles: {self.stats.white_tiles}  •  "
            f"Cyan ignored: {self.stats.cyan_tiles}  •  Unique: {self.stats.unique_words}  •  "
            f"Review: {self.stats.low_confidence}"
        )
        self._update_counts()

    def _selected_source_rows(self) -> list[int]:
        return sorted({self.proxy.mapToSource(index).row()
                       for index in self.table.selectionModel().selectedRows()})

    @Slot()
    def add_manual_word(self) -> None:
        self.model.replace(self.model.words + [DetectedWord(
            text="New word", confidence=1.0, review_status=ReviewStatus.MANUAL,
            sources=["Manual entry"]
        )])
        self._update_stats()
        source_index = self.model.index(len(self.model.words) - 1, 1)
        self.table.edit(self.proxy.mapFromSource(source_index))

    @Slot()
    def delete_selected_words(self) -> None:
        rows = set(self._selected_source_rows())
        if rows:
            self.model.replace([word for index, word in enumerate(self.model.words) if index not in rows])
            self._update_stats()

    def set_all_selected(self, selected: bool) -> None:
        for word in self.model.words:
            word.selected = selected
        self.model.refresh()
        self._update_counts()

    @Slot()
    def remove_duplicates(self) -> None:
        self.model.replace(deduplicate(self.model.words))
        self._update_stats()

    def _set_selected_result(self, result: ImportResult) -> None:
        for row in self._selected_source_rows():
            self.model.words[row].result = result
        self.model.refresh()
        self._update_counts()

    def mark_completed(self) -> None:
        self._set_selected_result(ImportResult.ALREADY_SHOULD_LEARN)

    def mark_skipped(self) -> None:
        self._set_selected_result(ImportResult.SKIPPED)

    @Slot()
    def load_word_list(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self, "Load word list", "", self.WORD_FILTER,
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if not filename:
            return
        try:
            self.model.replace(deduplicate(self.model.words +
                                           self.controller.load_word_list(Path(filename))))
            self._update_stats()
        except Exception as exc:
            QMessageBox.critical(self, "Could not load word list", str(exc))

    @Slot()
    def export_word_list(self) -> None:
        filename, _ = QFileDialog.getSaveFileName(
            self, "Export reviewed words", "words.csv", self.WORD_FILTER,
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if filename:
            try:
                self.controller.save_word_list(self.model.words, Path(filename))
            except Exception as exc:
                QMessageBox.critical(self, "Export failed", str(exc))

    @Slot()
    def export_report(self) -> None:
        filename, _ = QFileDialog.getSaveFileName(
            self, "Export final report", "report.csv", "CSV report (*.csv)",
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if filename:
            HistoryStore.export_report(self.model.words, Path(filename))

    @Slot()
    def refresh_wordup(self) -> None:
        try:
            windows = self.controller.discover_wordup()
            if windows:
                self.connection_badge.setText(f"WordUp detected ✓  ({len(windows)} window)")
                self.connection_badge.setStyleSheet(
                    "padding: 6px 12px; background: #d7f3df; border-radius: 8px")
            else:
                self.connection_badge.setText("WordUp not detected")
        except Exception as exc:
            self.connection_badge.setText("Detection failed")
            LOGGER.warning("WordUp discovery failed: %s", exc)

    @Slot()
    def connect_wordup(self) -> None:
        try:
            summary = self.controller.connect_wordup()
            self.connection_badge.setText(f"Connected ✓  {summary.title}")
            self.connection_badge.setStyleSheet(
                "padding: 6px 12px; background: #d7f3df; border-radius: 8px")
            LOGGER.info("Connected to WordUp")
        except Exception as exc:
            QMessageBox.warning(self, "WordUp not connected", str(exc))

    @Slot()
    def bring_front(self) -> None:
        try:
            self.controller.target.bring_to_front()
        except Exception as exc:
            QMessageBox.warning(self, "Could not activate WordUp", str(exc))

    @Slot()
    def inspect_ui(self) -> None:
        try:
            output = self.controller.inspect_wordup()
            QMessageBox.information(self, "UI inspection complete", f"Saved UIA tree to:\n{output}")
            LOGGER.info("Saved WordUp UIA tree to %s", output)
        except Exception as exc:
            QMessageBox.warning(self, "Inspection failed", str(exc))

    def _ready_indices(self, retry_only: bool = False) -> list[int]:
        retry_states = {ImportResult.NOT_FOUND, ImportResult.AMBIGUOUS, ImportResult.FAILED}
        eligible_states = {ImportResult.PENDING}
        if not self.dry_run.isChecked():
            eligible_states.add(ImportResult.DRY_RUN_OK)
        return [index for index, word in enumerate(self.model.words)
                if word.selected and (word.result in retry_states if retry_only
                                      else word.result in eligible_states)]

    @Slot()
    def test_one_word(self) -> None:
        checked = [index for index, word in enumerate(self.model.words) if word.selected]
        rows = self._selected_source_rows()
        if len(checked) == 1:
            test_indices = checked
        elif len(rows) == 1:
            test_indices = rows
        else:
            QMessageBox.information(
                self, "Select one word",
                "Check exactly one Import box, or highlight one row when multiple boxes are checked."
            )
            return
        self._begin_import(test_indices, dry_run=self.dry_run.isChecked(), require_confirmation=False)

    @Slot()
    def start_import(self) -> None:
        indices = self._ready_indices()
        if not indices:
            QMessageBox.information(self, "Nothing pending", "Select at least one pending word.")
            return
        self._begin_import(indices, self.dry_run.isChecked(), require_confirmation=True)

    @Slot()
    def retry_failed(self) -> None:
        indices = self._ready_indices(retry_only=True)
        if not indices:
            QMessageBox.information(self, "No failed words", "No selected failed words are available.")
            return
        for index in indices:
            self.model.words[index].result = ImportResult.PENDING
            self.model.words[index].error = ""
        self._begin_import(indices, self.dry_run.isChecked(), require_confirmation=True)

    def _begin_import(self, indices: list[int], dry_run: bool,
                      require_confirmation: bool) -> None:
        if self.import_thread is not None and self.import_thread.isRunning():
            QMessageBox.information(self, "Import active", "Pause or stop the current import first.")
            return
        if self.controller.engine is None:
            self.connect_wordup()
        if self.controller.engine is None:
            return
        low_review = [self.model.words[index].text for index in indices
                      if self.model.words[index].review_status == ReviewStatus.LOW_CONFIDENCE]
        if low_review:
            choice = QMessageBox.warning(
                self, "Review required",
                f"{len(low_review)} selected words are still marked for OCR review. "
                "Edit or deselect them before automation.", QMessageBox.Ok)
            return
        if require_confirmation:
            title = self.controller.target.window.window_text()
            answer = QMessageBox.question(
                self, "Confirm import",
                f"You are about to process {len(indices)} words in WordUp.\n\n"
                f"WordUp window: {title}\nDry Run: {'ON — no clicks' if dry_run else 'OFF — will click Should Learn'}\n\n"
                "Continue?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                return
        words = self.model.words
        session = self.controller.start_session(words, dry_run)
        self._launch_import_thread(indices, dry_run, session)

    def _launch_import_thread(self, indices: list[int], dry_run: bool,
                              session: SessionState) -> None:
        self.controller.session = session
        thread = QThread(self)
        worker = ImportWorker(self.controller, indices, dry_run)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(self.update_progress)
        worker.word_done.connect(self.word_completed)
        worker.failed.connect(lambda text: QMessageBox.critical(self, "Import error", text))
        worker.completed.connect(self.import_completed)
        worker.completed.connect(thread.quit)
        worker.completed.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._import_thread_finished)
        self.import_thread = thread
        self.import_worker = worker
        self.progress_bar.setRange(0, len(indices))
        self.start_button.setEnabled(False)
        self.pause_button.setEnabled(True)
        thread.start()

    @Slot()
    def _import_thread_finished(self) -> None:
        self.import_worker = None
        self.import_thread = None

    @Slot(int, int, str)
    def update_progress(self, done: int, total: int, text: str) -> None:
        self.progress_bar.setRange(0, max(total, 1))
        self.progress_bar.setValue(done)
        self.progress_label.setText(f"{done} / {total}")
        self.current_status.setText(text)
        if text:
            LOGGER.info(text)

    @Slot(int, str)
    def word_completed(self, index: int, result: str) -> None:
        self.model.refresh()
        self._update_counts()

    @Slot(bool)
    def import_completed(self, clean: bool) -> None:
        self.start_button.setEnabled(True)
        self.pause_button.setEnabled(False)
        self.pause_button.setText("Pause")
        self.model.refresh()
        self._update_counts()
        counts = Counter(word.result for word in self.model.words if word.selected)
        QMessageBox.information(
            self, "Import Complete" if clean else "Import Stopped",
            f"Total: {sum(counts.values())}\n"
            f"Updated: {counts[ImportResult.UPDATED]}\n"
            f"Already Should Learn: {counts[ImportResult.ALREADY_SHOULD_LEARN]}\n"
            f"Dry-run verified: {counts[ImportResult.DRY_RUN_OK]}\n"
            f"Not Found: {counts[ImportResult.NOT_FOUND]}\n"
            f"Ambiguous: {counts[ImportResult.AMBIGUOUS]}\n"
            f"Failed: {counts[ImportResult.FAILED]}",
        )

    @Slot()
    def toggle_pause(self) -> None:
        engine = self.controller.engine
        if engine is None:
            return
        if engine.pause_event.is_set():
            engine.pause()
            self.pause_button.setText("Resume")
            self.current_status.setText("Paused")
        else:
            engine.resume()
            self.pause_button.setText("Pause")
            self.current_status.setText("Resuming…")

    @Slot()
    def stop_import(self) -> None:
        if self.controller.engine is not None:
            self.controller.engine.stop()
            self.current_status.setText("Stopping at the next safe checkpoint…")

    def emergency_stop(self) -> None:
        self.stop_import()
        QMessageBox.warning(self, "Emergency stop", "Automation stop requested immediately.")

    def _update_counts(self) -> None:
        counts = Counter(word.result for word in self.model.words)
        success = counts[ImportResult.UPDATED] + counts[ImportResult.DRY_RUN_OK]
        remaining = counts[ImportResult.PENDING]
        self.counts_label.setText(
            f"Success: {success}\nAlready set: {counts[ImportResult.ALREADY_SHOULD_LEARN]}\n"
            f"Not found: {counts[ImportResult.NOT_FOUND]}\nFailed: {counts[ImportResult.FAILED]}\n"
            f"Remaining: {remaining}"
        )

    def _offer_resume(self) -> None:
        session = self.controller.resumable_session()
        if session is None:
            return
        answer = QMessageBox.question(
            self, "Resume Previous Session",
            f"An interrupted session from {session.updated_at} contains {len(session.words)} words. Resume it?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes,
        )
        if answer == QMessageBox.Yes:
            self.controller.session = session
            self.model.replace(session.words)
            self._update_stats()

    def show_runtime_paths(self) -> None:
        text = "\n".join(f"{key}: {value}" for key, value in self.controller.paths.items())
        QMessageBox.information(self, "Runtime data locations", text)

    def closeEvent(self, event: Any) -> None:
        if self.import_thread is not None and self.import_thread.isRunning():
            self.stop_import()
            QMessageBox.information(self, "Stopping import",
                                    "The import is stopping safely. Close again when it finishes.")
            event.ignore()
            return
        logging.getLogger().removeHandler(self.qt_log_handler)
        event.accept()


def run_application() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("WordUp Vocabulary Importer")
    app.setOrganizationName("WordUp Vocabulary Importer")
    app.setStyleSheet("""
        QGroupBox { font-weight: 700; margin-top: 8px; }
        QGroupBox::title { subcontrol-origin: margin; left: 8px; padding: 0 4px; }
        QPushButton { padding: 6px 9px; }
        QLineEdit { padding: 6px; }
    """)
    try:
        controller = AppController()
        window = MainWindow(controller)
        window.show()
        return app.exec()
    except Exception as exc:
        logging.exception("Application startup failed")
        QMessageBox.critical(None, "WordUp Vocabulary Importer", f"Startup failed:\n{exc}")
        return 1
