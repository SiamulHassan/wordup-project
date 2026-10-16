# WordUp Vocabulary Importer

A Windows 10/11 desktop utility that reads WordUp Knowledge Map screenshots, extracts only the
purple **Should Learn** tiles, lets you review every OCR result, and safely transfers selected words
through the visible WordUp Windows interface. Cyan **Already Know** tiles are measured and ignored.

The importer never edits WordUp files, databases, registry data, or binaries. It uses Windows UI
Automation first and an isolated, window-relative keyboard/OCR fallback only where WordUp exposes
custom-rendered controls.

## Safety model

Before a real action, all of these conditions must pass:

1. WordUp is the foreground window.
2. The current screen contains an exact, normalized match for the requested headword.
3. The detail screen exposes or visibly contains `Should Learn`.
4. Exactly one safe target is identified.

If any check fails, no action is clicked. `Already Know` is never used. A click whose effect cannot
be observed is honestly recorded as `CLICKED_UNVERIFIED`.

## Requirements

- Windows 10 or 11, x64
- Python 3.11+ for development only
- The Microsoft Store WordUp app open for inspection/import
- A normal desktop session (automation cannot run on a locked desktop)

The packaged EXE does not require Python. `rapidocr-onnxruntime` supplies local OCR without a
separate Tesseract installation. The OCR adapter can also use a configured Tesseract executable.

## Development setup

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python main.py
```

Application data is saved below `%LOCALAPPDATA%\WordUpVocabularyImporter`:

- `config.json` — user overrides and fallback calibration
- `logs/wordup_importer.log` — rotating operational log
- `logs/wordup_ui_tree.txt` — latest UIA inspection
- `sessions/` — atomic resume checkpoints
- `cache/` — screenshot-hash extraction cache
- `debug/` — optional masks, overlays, crops, and OCR results
- `history.jsonl` — append-only import history

## Recommended first run

1. Launch the importer.
2. Add or drag Knowledge Map screenshots.
3. Select **Analyze Screenshots**.
4. Review every word; edit or deselect all amber low-confidence entries.
5. Open WordUp and select **Connect**.
6. Select **Inspect UI** to capture the actual UI Automation tree.
7. Select one row and run **Test One Selected Word** with Dry Run enabled. The supplied narrow
   WordUp layout is pre-calibrated.
8. Only if navigation fails, open **Advanced → Fallback Calibration** and recapture the points.
9. Dry-run a small group, then disable Dry Run and confirm the real import.

Screenshot processing and WordUp automation never start automatically after each other. Review is a
mandatory stage.

## Screenshot input and detection

Use **Add Screenshot(s)**, **Add Folder**, drag-and-drop, **Remove Selected**, or **Clear All**.
PNG, JPG, JPEG, and WEBP are supported. Multiple or overlapping screenshots are safe: results are
deduplicated after OCR using Unicode-normalized, case-insensitive comparison while retaining all
source filenames.

The supplied reference screenshot has dominant tile colors near:

- purple: RGB `(176, 32, 248)`, OpenCV HSV hue approximately `140`
- cyan: RGB `(48, 192, 208)`, OpenCV HSV hue approximately `93`

Defaults in `config.json` allow compression and rendering variation around those values. The
pipeline converts BGR to HSV, creates separate purple/cyan masks, closes small JPEG gaps, finds
external contours, and filters by image-relative area, aspect ratio, and mask fill. These filters
exclude navigation icons, tiny indicators, and the bottom `Range 601–700` markers. Purple crops are
sorted by row and then left-to-right; OCR runs only on purple crops.

Enable **Save extraction debug images** before analyzing to write:

```text
debug/<screenshot_hash>/
  original.png
  purple_mask.png
  cyan_mask.png
  detected_tiles.png
  ocr_results.json
  crops/tile_001.png
```

For segmentation-only diagnostics:

```powershell
python tools\analyze_tiles.py path\to\knowledge-map.jpg --output debug-output
```

## OCR review and word lists

The review table supports inline word editing, row deletion, manual additions, filtering, sorting,
selection toggles, and duplicate removal. Low-confidence text, digits, and unsafe punctuation are
flagged rather than spell-corrected. Legitimate spaces, apostrophes, hyphens, and unusual vocabulary
are preserved.

Use **Load TXT/CSV/JSON** to bypass screenshots entirely. TXT uses one word per line; CSV reads the
first column; JSON accepts either a list or `{ "words": [...] }`. Exports retain confidence, sources,
and status where the format permits.

## WordUp connection and UI inspection

The importer finds external top-level windows matching `.*WordUp.*` and excludes its own process.
It connects through `pywinauto`'s UIA backend. **Bring to Front** verifies focus; **Inspect UI** logs
each discovered control's type, name, automation ID, class, rectangle, enabled state, and visibility.

The standalone diagnostic is useful before launching the GUI:

```powershell
python inspect_wordup.py
```

No automation ID is assumed in source. Locators combine runtime names and control types; IDs are
recorded for diagnostics and can be adopted only after a real inspection proves stable.

## Dry run, single-word test, and bulk import

- **Dry Run** navigates, searches, selects an exact result, and verifies the detail headword without
  clicking `Should Learn`.
- **Test One Selected Word** exercises just one table row.
- **Start Import** processes selected `PENDING` rows after explicit confirmation.
- **Pause/Resume** blocks at safe checkpoints; **Stop Safely** ends at the next safe boundary.
- `Ctrl+Shift+Q` and Escape request an emergency stop. PyAutoGUI's upper-left-corner fail-safe is
  left enabled.
- **Retry Failed** targets only selected `NOT_FOUND`, `AMBIGUOUS`, or `FAILED` rows.
- **Mark Completed** and **Skip** provide manual resolution without restarting a session.

Search and detail transitions use polling with configurable timeouts rather than fixed sleep chains.
A failure is retried per word and never aborts the remaining queue. Progress is checkpointed after
every completed word. On the next launch, an interrupted pending session is offered for review.

## Controlled fallback calibration

The distributed configuration contains relative points measured from the supplied narrow WordUp
screenshots, so manual calibration is not part of the normal first run. The points only navigate to
Search and focus its field; all consequential checks still use live OCR.

If a WordUp redesign or different layout prevents the one-word dry run from navigating, open
**Advanced → Fallback Calibration**. For each requested control, navigate WordUp to the relevant
screen, select Capture, and hover the pointer over that control for three seconds. Coordinates are
stored as proportions of the live WordUp window, not as absolute screen pixels.

The fallback still requires OCR-based exact headword and button-label verification. Calibration does
not weaken the four action safety conditions. Display scaling or a WordUp redesign may require
recalibration.

## Reports and statuses

Every history record contains timestamp, word, result, attempts, sources, confidence, and error.
Final CSV reports can be exported from the GUI. Results are:

- `UPDATED`
- `ALREADY_SHOULD_LEARN`
- `CLICKED_UNVERIFIED`
- `DRY_RUN_OK`
- `NOT_FOUND`
- `AMBIGUOUS`
- `FAILED`
- `SKIPPED`

## Configuration

`config.json` contains defaults for the title regex, OCR threshold/backend, HSV ranges, contour
geometry, timeouts, retry count, word delay, fallback confidence, logging, and debug output. GUI
settings persist as user overrides under Local AppData. Delete that user configuration to restore
distributed defaults.

## Testing

Unit tests do not automate WordUp. They cover purple/cyan segmentation, tile filtering and reading
order, conservative normalization, case-insensitive deduplication, portable word lists, and atomic
session save/load.

```powershell
python -m pytest -q
```

To validate against a private reference screenshot, run `tools/analyze_tiles.py` and visually inspect
the overlay. Screenshot fixtures are intentionally not distributed by default.

## Building the standalone EXE

Run:

```powershell
.\build.ps1
```

or manually:

```powershell
python -m PyInstaller --noconfirm --clean WordUpVocabularyImporter.spec
```

The output is `dist\WordUpVocabularyImporter.exe`. The spec collects RapidOCR's model data and
submodules plus the default configuration. Build on Windows x64 for Windows x64; PyInstaller is not a
cross-compiler.

## Troubleshooting

- **WordUp not detected:** open the Microsoft Store WordUp app and verify its title contains
  `WordUp`; do not run either process elevated unless both use the same privilege level.
- **Search is not found:** run UI inspection, review `wordup_ui_tree.txt`, then calibrate the search
  icon/box if WordUp uses a custom canvas.
- **OCR backend unavailable:** reinstall `requirements.txt`. In a packaged build, ensure antivirus
  did not quarantine ONNX Runtime or model resources.
- **Wrong/missing screenshot words:** enable extraction debug output. Tune HSV limits gradually and
  verify cyan remains absent from the purple mask.
- **Clicks are refused:** this is a safety outcome. Confirm focus, exact headword visibility, and an
  unambiguous `Should Learn` label; inspect/recalibrate rather than disabling verification.
- **Locked desktop or focus loss:** unlock the session and bring WordUp forward. Automation never
  types into an unverified foreground application.

## Known limitations

- WordUp is external software and its accessibility tree can change. UI inspection and calibration
  are therefore runtime steps, not hard-coded assumptions.
- A click may be `CLICKED_UNVERIFIED` if WordUp exposes no observable semantic or visual state change.
- OCR confidence is advisory and review remains mandatory.
- Global emergency shortcuts are active while the importer has focus; PyAutoGUI's corner fail-safe
  remains available during fallback actions.
- The importer cannot operate through the Windows lock screen or a disconnected interactive session.
#   w o r d u p - p r o j e c t  
 