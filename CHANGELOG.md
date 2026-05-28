# Changelog

---

## [v7.0] – 2026-05-27

Complete rewrite of the original single-file script into a structured Python package.

### Added
- `s4converter/` package with separated modules: `core`, `cache`, `cli`, `gui`, `config`
- **Persistent ffprobe cache** (`ProbeCache`) — skips unchanged files on re-scans (~150× faster)
- **Per-folder markers** (`FolderMarkers`) — skips entire folders that haven't changed
- **Parallel ffprobe workers** — probes multiple files simultaneously on first scan
- **PyQt6 GUI** — tab-per-phase interface with background worker threads, inline editing, progress bars
- **CLI** with `--dry-run`, `--quick`, `--phases`, `--full-scan` flags
- **Phase 6: Stereo → Mono detection** — classifies files as `dual_mono`, `one_side`, `near_mono`, or `true_stereo` using peak dB math; saves ~50 % per converted file
- Drive preset dropdown in GUI (USB / S-4 Root / Custom)
- Per-phase help panels with thresholds and workflow tips
- `config.json` at repo root for user-editable settings (no Python required)
- `requirements.txt`

### Changed
- `NAME_LENGTH_LIMIT` raised from 50 → 70 characters
- Config split: `config.json` (user edits) + `config.py` (loader + internal constants)

---

## [v6.0] – 2025-12-31

Original single-file script (`smart_converter_v6.py`).

### Added
- 5 interactive CLI phases run sequentially with user prompts
- **Phase 1** – Non-WAV conversion (MP3, AIFF, FLAC → 48 kHz WAV; auto bit depth)
- **Phase 2** – Sample rate compliance (resample to 48 kHz, preserve bit depth)
- **Phase 3** – Bit depth optimisation (24-bit files > 10 s → 16-bit)
- **Phase 4** – Shared prefix removal (folder-targeted, auto-detect + manual fallback)
- **Phase 5** – Long filename cleanup (stems > 50 chars, suggest + manual rename)
- Smart history: remembers last run time, offers incremental scan on launch
- `NAME_LENGTH_LIMIT = 50`

---

<!-- TODO: backfill v1–v5 history from Gemini chat -->
