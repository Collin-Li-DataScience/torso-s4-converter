# Torso S-4 Smart Sample Converter (Ultimate v6)

A Python utility to standardize, optimize, and organize sample libraries for the Torso S-4.

---

## Overview

This tool scans your sample folder (e.g., `/Volumes/S-4/SAMPLES`) and ensures all audio files are compatible with the Torso S-4's native requirements while optimizing for storage space and organization.

It operates in **5 interactive phases** and tracks your **last run time** to optionally scan only new files, saving you time.

---

## Requirements

- **Python 3** installed on your system.
- **FFmpeg** installed and accessible in your system PATH.
  *(Mac users: `brew install ffmpeg`)*

---

## Key Features

- **Smart History:** Remembers when you last ran the script. On launch, it asks if you want to scan *only* new files added since then.
- **Interactive Cleaning:** Phase 4 lets you target specific folders for cleanup and manually input prefixes to strip if auto-detection misses them.
- **Improved Limits:** Filename length limit set to 50 characters to better match S-4 display capabilities.

---

## How It Works

### Phase 1: Non-WAV Conversion (Automatic)

**Goal:** Standardize new files.

Scans for any audio file that is *not* a WAV (MP3, AIFF, FLAC, etc.) and converts it immediately.

- **Format:** Converted to 48 kHz WAV.
- **Bit Depth:** Applies "Best Practice" rules automatically (16-bit for long files, 24-bit for short HQ files).
- **Originals:** Deleted automatically if conversion succeeds (configurable).

---

### Phase 2: Sample Rate Compliance (Interactive)

**Goal:** Ensure native playback performance.

The script asks if you want to scan existing WAV files for non-48 kHz sample rates (e.g., 44.1 kHz).

- **Why?** The Torso S-4 runs natively at 48 kHz. Mismatched files force the CPU to resample in real-time.
- **Action:** If you approve, it resamples them to 48 kHz while preserving their current bit depth quality.
- **Trade-off:** Converting 44.1 kHz to 48 kHz increases file size by ~9 %, but this is necessary for CPU efficiency.
- **IMPORTANT — Project Compatibility:** Modifying a file in-place (same name/path) will **NOT** break the file link in your S-4 projects. However, because resampling changes the total number of samples in the file, precise start/end points or loop markers saved in existing projects *might* drift slightly if the S-4 stores them as absolute sample values.

---

### Phase 3: Bit Depth Optimization (Interactive)

**Goal:** Save disk space without audible loss.

The script asks if you want to scan for files that are larger than necessary (e.g., 24-bit field recordings).

- **Rule:** If a file is > 10 seconds long, it suggests reducing it to 16-bit.
- **Savings:** 24-bit files are 50 % larger than 16-bit. This phase can reclaim gigabytes of space on your S-4.

---

### Phase 4: Common Prefix Removal (Interactive Folder Mode)

**Goal:** Clean up sample names in specific folders.

You enter a folder path to scan. The script detects common prefixes (e.g., `"Loopmasters - Dubstep - ..."`).

- **Auto-Detection:** Suggests a prefix to strip.
- **Manual Mode:** If detection fails, you can type the exact prefix to remove manually.
- **Result:** `"Loopmasters - Dubstep - Kick 01.wav"` becomes `"Kick 01.wav"`.
- **Safety:** Ignores groups where all files are already short enough (under 30 chars).

---

### Phase 5: Long Filename Cleanup (Interactive)

**Goal:** Fix display issues on the S-4 screen.

Scans for individual files with names longer than **50 characters**.

- **Action:** Suggests shorter names (e.g., removing spaces, using initials, or keeping only the number/suffix) or allows manual renaming.
- **Flexibility:** You can choose a suggestion by number or type a completely new name.

---

## Configuration

Open `smart_converter_v6.py` in a text editor to change these settings at the top of the file:

```python
# === CONFIG ===
BASE_DIR = Path("/Volumes/S-4/SAMPLES")  # Target folder
DELETE_ORIGINAL = True                   # Delete MP3s after converting?
THRESHOLD_SECONDS = 10.0                 # Definition of "Long" file
FORCE_AR = "48000"                       # Native S-4 Rate
NAME_LENGTH_LIMIT = 50                   # Phase 5: Long name limit
```

---

## Usage

Run the script via your terminal:

```bash
python3 smart_converter_v6.py
```

Follow the on-screen prompts to proceed through the phases.

---

*Generated for Torso S-4 Workflow Optimization.*
