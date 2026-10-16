<div align="center">

# WordUp Vocabulary Importer

Turn Knowledge Map screenshots into a reviewed vocabulary list, then add words to WordUp through its desktop interface.

![Windows 10/11](https://img.shields.io/badge/Windows-10%20%2F%2011-0078D4?style=flat-square)
![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-3776AB?style=flat-square)
![OCR: local](https://img.shields.io/badge/OCR-local-8B5CF6?style=flat-square)

[What's built](#whats-built) &middot; [Quick start](#quick-start) &middot; [Import workflow](#import-workflow) &middot; [Build](#build-the-exe) &middot; [Troubleshooting](#troubleshooting)

</div>

WordUp Vocabulary Importer is a Windows desktop app built with **PySide6**, **OpenCV**, and **RapidOCR**. It extracts words from screenshots, gives you an editable review table, and automates the **Should Learn** action in the Microsoft Store WordUp app.

**Purple and white/light tiles are extracted. Cyan Already Know tiles are counted and ignored.** OCR runs locally, and the packaged EXE includes the OCR models without requiring Python or a separate Tesseract installation.

## What's built

| Area | Implemented features |
| --- | --- |
| Screenshot input | Add individual images or folders, or drag and drop PNG, JPG, JPEG, and WEBP files. |
| Word extraction | Detect purple and white/light tiles, read them in row order, cache results, and merge duplicates across overlapping screenshots. |
| Review table | Edit words inline; add, delete, filter, sort, select, or exclude entries. Low-confidence OCR results are highlighted for review. |
| Word lists | Load and export TXT, CSV, and JSON lists, with source and confidence metadata where supported. |
| WordUp automation | Connect to WordUp, inspect its UI, test one word, dry-run a batch, and import selected words using UI Automation with an OCR fallback. |
| Session controls | Pause, resume, stop safely, retry failed words, and recover interrupted sessions from saved checkpoints. |
| Reporting | Track per-word results and attempts, keep an append-only history, and export CSV reports. |
| Diagnostics and packaging | Save masks, tile overlays, and OCR crops; calibrate fallback navigation; build a standalone Windows EXE. |

## Quick start

You need **Windows 10 or 11 (x64)** and the **Microsoft Store WordUp app**. Keep WordUp open in an unlocked desktop session during imports.

### Run from source

Install **Python 3.11+**, then run these commands from the project folder:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

### Run a packaged build

If you already have a built copy, launch `WordUpVocabularyImporter.exe`. Python is only needed to run from source or build the executable; see [Build the EXE](#build-the-exe).

## Import workflow

1. **Add your screenshots.** Use **Add Screenshot(s)**, **Add Folder**, or drag and drop. You can also choose **Load TXT/CSV/JSON** to start with an existing word list.
2. **Analyze and review.** Select **Analyze Screenshots**, check the extracted words, and edit or deselect every amber low-confidence entry. Remove anything you do not want to import.
3. **Connect to WordUp.** Open WordUp, select **Connect**, then **Inspect UI** to save its current accessibility tree.
4. **Test one word.** Leave **Dry Run** enabled, highlight one row, and select **Test One Selected Word**. This checks navigation and the word detail screen without clicking **Should Learn**.
5. **Dry-run a small batch.** Check the **Import** boxes for your chosen words and select **Start Import**. Review the results before continuing.
6. **Import the reviewed words.** Turn off **Dry Run**, select **Start Import**, and confirm the batch. Words verified during the dry run remain eligible for the real import.

> **Dry Run is enabled by default.** Screenshot analysis and import are separate actions; analyzing images never starts an import.

Default fallback coordinates are included for the reference narrow WordUp layout. If the one-word test cannot navigate, use **Advanced > Fallback Calibration** as described below.

## Safety and import controls

The importer works through WordUp's visible interface. It uses **Windows UI Automation first**, with an isolated, window-relative keyboard and OCR fallback for custom-rendered controls. It does not edit WordUp's files, databases, registry data, or binaries.

Before clicking **Should Learn**, it checks that:

- WordUp is the foreground window.
- The detail screen contains an exact, normalized match for the requested word.
- The **Should Learn** label is present.
- Exactly one action target is identified.

A failed check prevents the action. The importer never selects **Already Know**, recognizes words already marked **Should Learn**, and records clicks without an observable result as `CLICKED_UNVERIFIED`.

Use **Pause/Resume** or **Stop Safely** to control a running batch. **Retry Failed** processes only selected `NOT_FOUND`, `AMBIGUOUS`, or `FAILED` rows. **Mark Completed** and **Skip** let you resolve entries manually.

**Emergency stop:** `Ctrl+Shift+Q` or `Esc` requests a stop while the importer has focus. PyAutoGUI's upper-left-corner fail-safe remains enabled for fallback actions. Progress is checkpointed after each processed word, and interrupted sessions are offered for review on the next launch.

## Build the EXE

Build on **Windows x64**. From the project folder, run:

```powershell
.\build.ps1
```

The script creates `.venv` if needed, installs dependencies, runs the tests, and invokes PyInstaller. The output is:

```text
dist/WordUpVocabularyImporter.exe
```

To package an already prepared environment directly:

```powershell
.\.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean WordUpVocabularyImporter.spec
```

The [PyInstaller spec](WordUpVocabularyImporter.spec) bundles the default configuration and RapidOCR model data. PyInstaller builds for the host platform; use Windows to produce the Windows executable.

## Development

The code separates the desktop UI, extraction pipeline, automation, and persistence:

```text
app/           PySide6 interface, application controller, and shared state
extraction/    Color masks, tile detection, preprocessing, OCR, and normalization
automation/    WordUp connection, search, verification, and fallback controls
storage/       Word lists, session checkpoints, history, and reports
utils/         Configuration, logging, paths, and exceptions
tests/         Unit and regression tests
tools/         Extraction diagnostics and smoke-test helpers
main.py        Application entry point
config.json    Distributed defaults
```

Run the test suite in your virtual environment:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Tests cover color segmentation, white-tile preprocessing, tile filtering and reading order, normalization, deduplication, word-list formats, session persistence, GUI selection, window filtering, search navigation, and action verification. They use synthetic inputs and test doubles rather than automating the live WordUp app.

Additional development tools are listed in [requirements-dev.txt](requirements-dev.txt). Private reference screenshots are not included in the repository.

## Technical reference

<details>
<summary><strong>Extraction and word-list formats</strong></summary>

OpenCV creates separate masks for purple, cyan, and white/light tile backgrounds. Contours are filtered by image-relative area, aspect ratio, and mask fill to reject small indicators and unrelated interface elements. Purple and white tiles are combined in reading order and passed to OCR; cyan tiles are excluded.

Duplicates are merged using Unicode-normalized, case-insensitive comparison while retaining source filenames. Uncertain text is flagged rather than spell-corrected, preserving spaces, apostrophes, hyphens, and unusual vocabulary for review.

| Format | Input | Export |
| --- | --- | --- |
| TXT | One word per line. | Selected words, one per line. |
| CSV | Words from the first column; an optional `word`, `text`, or `vocabulary` header is recognized. | Selected words with confidence, source, and review status. |
| JSON | A list, or an object containing a `words` list. Entries may be strings or objects with `word` or `text`. | Selected words with their stored metadata. |

</details>

<details>
<summary><strong>Configuration and local data</strong></summary>

[config.json](config.json) defines the window-title pattern, OCR settings, tile-detection thresholds, timeouts, retries, word delay, fallback coordinates, logging, and debug output. User overrides are saved under:

```text
%LOCALAPPDATA%/WordUpVocabularyImporter/
  config.json                User overrides and fallback calibration
  history.jsonl              Append-only import history
  logs/wordup_importer.log    Rotating application log
  logs/wordup_ui_tree.txt     Latest UI Automation inspection
  sessions/                  Resume checkpoints
  cache/                     Screenshot extraction cache
  debug/                     Optional extraction artifacts
  reports/                   Report directory
```

Use **Advanced > Show runtime paths** to find the current locations. Delete the user `config.json` to restore the distributed defaults.

RapidOCR is the default local OCR backend. The optional Tesseract adapter requires both `pytesseract` and a Tesseract installation; these are not included in the standard dependencies.

</details>

<details>
<summary><strong>UI inspection and fallback calibration</strong></summary>

**Inspect UI** records control types, names, automation IDs, classes, rectangles, and availability. To inspect WordUp without launching the importer GUI:

```powershell
.\.venv\Scripts\python.exe inspect_wordup.py
```

Locators use runtime control names and types rather than assuming fixed automation IDs.

If navigation fails, open **Advanced > Fallback Calibration**. Navigate WordUp to the relevant screen, select **Capture in 3 seconds**, then hover over the requested control. Each point is stored as a proportion of the WordUp window. Navigation uses the Search icon, search field, and Back points; the **Should Learn** click still requires live label detection and word verification.

A changed WordUp layout or display scaling may require recalibration. Keep WordUp visible and unlocked; automation cannot operate through the lock screen or a disconnected desktop session.

</details>

<details>
<summary><strong>Extraction diagnostics</strong></summary>

Enable **Save extraction debug images** before analyzing screenshots to save:

```text
debug/<source_stem>_<hash_prefix>/
  original.png
  purple_mask.png
  white_mask.png
  cyan_mask.png
  detected_tiles.png
  ocr_results.json
  crops/tile_001.png
```

For a purple/cyan segmentation check without OCR, run from the project folder:

```powershell
.\.venv\Scripts\python.exe -m tools.analyze_tiles path\to\knowledge-map.jpg --output debug-output
```

Use the GUI's extraction debug output to inspect white-tile detection as well. Review the overlay and masks before adjusting the color or geometry thresholds.

</details>

<details>
<summary><strong>Import results and reports</strong></summary>

| Result | Meaning |
| --- | --- |
| `PENDING` | Waiting to be processed. |
| `UPDATED` | The action was clicked and a subsequent UI change was observed. |
| `ALREADY_SHOULD_LEARN` | The word was recognized as already selected for learning. |
| `CLICKED_UNVERIFIED` | A click occurred, but no confirming UI change was observed. |
| `DRY_RUN_OK` | Navigation and detail verification passed without clicking the action. |
| `NOT_FOUND` | No exact matching word was found. |
| `AMBIGUOUS` | Multiple matching targets prevented a safe selection. |
| `FAILED` | Processing failed; inspect the recorded error. |
| `SKIPPED` | The entry was skipped. |

History records include the timestamp, session ID, word, result, attempts, sources, confidence, and error. **Export Report** writes the current table's per-word results to CSV.

</details>

## Troubleshooting

| Problem | What to check |
| --- | --- |
| WordUp is not detected | Open the Microsoft Store app. Keep WordUp and the importer at the same privilege level. |
| Search navigation fails | Run **Inspect UI**, check `logs/wordup_ui_tree.txt`, then recalibrate the fallback navigation points. |
| OCR is unavailable | Reinstall `requirements.txt`. For packaged builds, check whether antivirus quarantined ONNX Runtime or model files. |
| Words are missing or incorrect | Review the highlighted entries and enable extraction debug images. Inspect masks and overlays before tuning thresholds. |
| An action is refused | Bring WordUp forward and check that the exact word and a single **Should Learn** target are visible. |
| The result is `CLICKED_UNVERIFIED` | Check the word's state in WordUp before retrying; the click may have succeeded without an observable UI change. |
| Automation stops after focus loss | Unlock the desktop and bring WordUp forward before retrying the affected entries. |

WordUp's interface and accessibility tree can change between versions. OCR confidence is advisory, so review extracted words and verify the one-word dry run before a batch import.
