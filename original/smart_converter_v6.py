import os
import json
import subprocess
import sys
import re
import time
from pathlib import Path
from typing import Optional, Dict, List, Tuple

# === CONFIG ===
BASE_DIR = Path("/Volumes/S-4/SAMPLES")

DELETE_ORIGINAL = True               # Phase 1: delete non-WAV source after conversion
COPY_METADATA = True
THRESHOLD_SECONDS = 10.0             # > 10s -> 16-bit WAV; <=10s -> 24-bit iff source > 16-bit

# WAV codecs for target bit depths
WAV_CODEC_16 = "pcm_s16le"
WAV_CODEC_24 = "pcm_s24le"

FORCE_AR = "48000" # Torso S-4 Native Sample Rate
FORCE_AC = None

# Renaming Config
NAME_LENGTH_LIMIT = 50  # Phase 5: Long name limit (Increased to 50)
MIN_PREFIX_LENGTH = 8   # Phase 4: Minimum length to consider a "prefix"
MIN_GROUP_SIZE = 3      # Phase 4: How many files must share a prefix to flag it
PREFIX_SKIP_LENGTH = 30 # Phase 4: If files with prefix are shorter than this, ignore prefix

LAST_RUN_FILE = BASE_DIR / ".last_run"

# --- Helper Classes & Functions ---

class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def format_bytes(size):
    power = 2**10
    n = 0
    power_labels = {0 : '', 1: 'KB', 2: 'MB', 3: 'GB', 4: 'TB'}
    while size > power:
        size /= power
        n += 1
    return f"{size:.2f} {power_labels[n]}"

def is_hidden_or_appledouble(p: Path) -> bool:
    return p.name.startswith(".") or p.name.startswith("._")

def get_last_run_time() -> float:
    if LAST_RUN_FILE.exists():
        try:
            with open(LAST_RUN_FILE, 'r') as f:
                return float(f.read().strip())
        except:
            return 0.0
    return 0.0

def update_last_run_time():
    try:
        with open(LAST_RUN_FILE, 'w') as f:
            f.write(str(time.time()))
    except Exception as e:
        print(f"{Colors.RED}Warning: Could not save run time to {LAST_RUN_FILE}: {e}{Colors.ENDC}")

def ffprobe_json(src: Path) -> Optional[dict]:
    try:
        res = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-select_streams", "a:0",
                "-show_entries",
                "format=duration:stream=bits_per_sample,bits_per_raw_sample,sample_fmt,sample_rate,channels",
                "-of", "json",
                str(src)
            ],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        if res.returncode != 0 or not res.stdout.strip():
            return None
        return json.loads(res.stdout)
    except Exception:
        return None

def extract_audio_info(info: dict):
    """Extracts duration, bit depth, sample rate, channels."""
    fmt = info.get("format", {})
    streams = info.get("streams", [])
    stream = streams[0] if streams else {}

    try: duration = float(fmt.get("duration", 0))
    except: duration = 0.0

    try: sr = int(stream.get("sample_rate", 44100))
    except: sr = 44100
    
    try: ch = int(stream.get("channels", 2))
    except: ch = 2

    bits = 16 
    for k in ("bits_per_sample", "bits_per_raw_sample"):
        v = stream.get(k)
        if v:
            try: bits = int(v); break
            except: pass
    
    if bits == 16:
        sfmt = (stream.get("sample_fmt") or "").lower()
        if "flt" in sfmt or "32" in sfmt: bits = 32
        elif "dbl" in sfmt or "64" in sfmt: bits = 64
        elif "24" in sfmt: bits = 24

    return duration, bits, sr, ch

def decide_best_practice_bits(duration_s: float, src_bits: int) -> int:
    if duration_s > THRESHOLD_SECONDS: return 16
    return 24 if src_bits > 16 else 16

def run_ffmpeg(cmd):
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return res.returncode == 0
    except:
        return False

def convert_to_wav(src: Path, dst: Path, target_bits: int) -> bool:
    cmd = ["ffmpeg", "-y", "-i", str(src)]
    if COPY_METADATA: cmd += ["-map_metadata", "0"]
    if FORCE_AR: cmd += ["-ar", FORCE_AR]
    if FORCE_AC: cmd += ["-ac", FORCE_AC]
    cmd += ["-f", "wav", "-c:a", WAV_CODEC_24 if target_bits >= 24 else WAV_CODEC_16, str(dst)]
    return run_ffmpeg(cmd)

def suggest_short_name(name):
    """Generates shorter name suggestions."""
    stem = Path(name).stem
    suffix = Path(name).suffix
    suggestions = []

    # 1. Strip spaces/punctuation
    s1 = re.sub(r'[_\-\s]+', '', stem)
    suggestions.append(s1 + suffix)

    # 2. Keep numbers + word following (e.g. "89 Tekno")
    match = re.search(r'(\d+)\s*([a-zA-Z]+)', stem)
    if match:
        suggestions.append(f"{match.group(1)}{match.group(2)}{suffix}")

    # 3. Last 15 chars
    if len(stem) > 15:
        suggestions.append("..." + stem[-15:] + suffix)
    
    # 4. Initials + Number
    words = re.findall(r'[A-Za-z0-9]+', stem)
    initials = "".join([w[0] if w[0].isalpha() else w for w in words])
    suggestions.append(initials + suffix)

    return list(set(suggestions))

# === PHASES ===

def phase_1_non_wav_conversion(cutoff_time: float):
    print(f"\n{Colors.HEADER}=== PHASE 1: Converting Non-WAV Files ==={Colors.ENDC}")
    converted_count = 0
    for root, _, files in os.walk(BASE_DIR):
        for name in files:
            src = Path(root) / name
            if is_hidden_or_appledouble(src): continue
            
            # Timestamp Check
            if cutoff_time > 0 and src.stat().st_mtime <= cutoff_time:
                continue

            if src.suffix.lower() == ".wav": continue

            info = ffprobe_json(src)
            if not info: continue
            
            dur, bits, _, _ = extract_audio_info(info)
            target_bits = decide_best_practice_bits(dur, bits)
            dst = src.with_suffix(".wav")

            if dst.exists(): continue

            if convert_to_wav(src, dst, target_bits):
                converted_count += 1
                print(f"✅ Converted: {src.name} -> WAV (48kHz, {target_bits}-bit)")
                if DELETE_ORIGINAL:
                    try: os.remove(src)
                    except: pass
    
    if converted_count == 0: print("No new non-WAV files found.")
    else: print(f"Phase 1 Complete: {converted_count} files converted.")

def phase_2_sample_rate_check(cutoff_time: float):
    print(f"\n{Colors.HEADER}=== PHASE 2: Sample Rate Compliance (48kHz) ==={Colors.ENDC}")
    ask = input(f"{Colors.YELLOW}Scan existing WAVs for non-48000Hz files? (yes/no): {Colors.ENDC}").strip().lower()
    if ask != 'yes': return

    print("Scanning...")
    files_to_fix = []
    
    for root, _, files in os.walk(BASE_DIR):
        for name in files:
            p = Path(root) / name
            if is_hidden_or_appledouble(p): continue
            
            # Timestamp Check
            if cutoff_time > 0 and p.stat().st_mtime <= cutoff_time:
                continue

            if p.suffix.lower() != ".wav": continue

            info = ffprobe_json(p)
            if not info: continue
            _, bits, sr, _ = extract_audio_info(info)
            
            if sr != 48000:
                target_bits = 24 if bits > 16 else 16
                files_to_fix.append({ "path": p, "sr": sr, "target_bits": target_bits })

    if not files_to_fix:
        print(f"{Colors.GREEN}All scanned WAV files are 48kHz.{Colors.ENDC}")
        return

    print(f"{Colors.BLUE}Found {len(files_to_fix)} files that are NOT 48kHz.{Colors.ENDC}")
    confirm = input(f"{Colors.YELLOW}Convert these {len(files_to_fix)} files to 48kHz? (yes/no): {Colors.ENDC}").strip().lower()
    if confirm == 'yes':
        count = 0
        for item in files_to_fix:
            src = item['path']
            tmp = src.with_name(src.stem + ".__tmp__.wav")
            if convert_to_wav(src, tmp, item['target_bits']):
                try: os.replace(tmp, src); count += 1
                except: 
                    if tmp.exists(): os.remove(tmp)
        print(f"{Colors.GREEN}Phase 2 Complete: {count} files resampled.{Colors.ENDC}")

def phase_3_bit_depth_optimization(cutoff_time: float):
    print(f"\n{Colors.HEADER}=== PHASE 3: Bit Depth Optimization ==={Colors.ENDC}")
    ask = input(f"{Colors.YELLOW}Scan existing WAVs for bit-depth optimization? (yes/no): {Colors.ENDC}").strip().lower()
    if ask != 'yes': return

    print("Scanning...")
    files_by_folder = {}
    total_savings = 0
    total_files = 0
    
    for root, _, files in os.walk(BASE_DIR):
        folder_candidates = []
        for name in files:
            p = Path(root) / name
            if is_hidden_or_appledouble(p): continue
            
            # Timestamp Check
            if cutoff_time > 0 and p.stat().st_mtime <= cutoff_time:
                continue

            if p.suffix.lower() != ".wav": continue

            info = ffprobe_json(p)
            if not info: continue
            dur, current_bits, sr, ch = extract_audio_info(info)
            best_bits = decide_best_practice_bits(dur, current_bits)
            
            if current_bits > best_bits:
                current_size = p.stat().st_size
                est_new_size = dur * sr * ch * (best_bits / 8) + 44
                savings = current_size - est_new_size
                if savings > 1024:
                    folder_candidates.append({ "path": p, "target": best_bits, "savings": savings })
                    total_savings += savings
                    total_files += 1
        
        if folder_candidates:
            files_by_folder[root] = folder_candidates

    if total_files == 0:
        print(f"{Colors.GREEN}All scanned files are optimized.{Colors.ENDC}")
        return

    # Print Summary by Folder
    print(f"{Colors.BLUE}Found {total_files} files to optimize. Total Savings: {format_bytes(total_savings)}{Colors.ENDC}")
    for folder, items in files_by_folder.items():
        try: rel_folder = Path(folder).relative_to(BASE_DIR)
        except: rel_folder = folder
        folder_savings = sum(x['savings'] for x in items)
        print(f"\n📂 {Colors.BOLD}{rel_folder}{Colors.ENDC} ({len(items)} files, {format_bytes(folder_savings)})")
        for x in items[:3]:
            print(f"  - {x['path'].name}")
        if len(items) > 3: print(f"  ... and {len(items)-3} more")

    confirm = input(f"\n{Colors.YELLOW}Convert all {total_files} files to 16-bit? (yes/no): {Colors.ENDC}").strip().lower()
    if confirm == 'yes':
        count = 0
        for folder, items in files_by_folder.items():
            for item in items:
                src = item['path']
                tmp = src.with_name(src.stem + ".__tmp__.wav")
                if convert_to_wav(src, tmp, item['target']):
                    try: os.replace(tmp, src); count += 1
                    except: 
                        if tmp.exists(): os.remove(tmp)
        print(f"{Colors.GREEN}Phase 3 Complete: {count} files optimized.{Colors.ENDC}")

def phase_4_prefix_cleanup(cutoff_time: float):
    print(f"\n{Colors.HEADER}=== PHASE 4: Common Prefix Removal ==={Colors.ENDC}")
    ask = input(f"{Colors.YELLOW}Start interactive prefix cleanup? (yes/no): {Colors.ENDC}").strip().lower()
    if ask != 'yes': return

    while True:
        target_path_str = input(f"\n{Colors.BLUE}Enter full folder path to scan (or 'q' to quit): {Colors.ENDC}").strip()
        if target_path_str.lower() == 'q':
            break
            
        # --- PATH CLEANING ---
        # 1. Remove surrounding quotes (both single and double)
        target_path_str = target_path_str.strip('\'"')
        # 2. Unescape backslashes if present (e.g. Joy\ O -> Joy O)
        #    Some terminals add backslashes before spaces when drag-dropping folders.
        target_path_str = target_path_str.replace('\\ ', ' ')
        # 3. Expand User Path (~)
        target_path = Path(target_path_str).expanduser().resolve()

        if not target_path.exists() or not target_path.is_dir():
            print(f"{Colors.RED}Invalid folder path: {target_path}{Colors.ENDC}")
            continue

        print(f"Scanning {target_path}...")
        
        files = [f for f in target_path.iterdir() if f.is_file() and not f.name.startswith('.')]
        if not files:
            print("Folder is empty or has no visible files.")
            continue
            
        files.sort(key=lambda x: x.name)
        file_names = [f.name for f in files]
        
        # --- Attempt Auto-Detection ---
        detected_prefix = ""
        
        # Simple Clustering attempt (look for longest common prefix of first 3 files or just common prefix of all)
        if len(file_names) >= 2:
            # Try to find a meaningful prefix
            # 1. Check strict common prefix
            p = os.path.commonprefix(file_names)
            
            # 2. Refine
            separators = [' - ', '_', ' ', '-']
            clean_prefix = ""
            for sep in separators:
                if sep in p:
                    clean_prefix = p.rsplit(sep, 1)[0] + sep
                    break
            
            if not clean_prefix and '_' in p:
                 clean_prefix = p.rsplit('_', 1)[0] + '_'
                 
            if len(clean_prefix) >= MIN_PREFIX_LENGTH:
                detected_prefix = clean_prefix

        # --- Report & Action ---
        if detected_prefix:
            count = sum(1 for f in file_names if f.startswith(detected_prefix))
            print(f"{Colors.GREEN}Detected Prefix:{Colors.ENDC} '{detected_prefix}' (Affects {count} files)")
            print(f"Example: {file_names[0]} -> {file_names[0][len(detected_prefix):]}")
            
            choice = input(f"{Colors.YELLOW}Strip this prefix? (yes/no/manual): {Colors.ENDC}").strip().lower()
        else:
            print(f"{Colors.YELLOW}No obvious long prefix detected automatically.{Colors.ENDC}")
            choice = "manual"

        prefix_to_strip = ""
        
        if choice == 'yes':
            prefix_to_strip = detected_prefix
        elif choice == 'manual':
            prefix_to_strip = input(f"{Colors.BLUE}Enter prefix to strip exactly (case sensitive): {Colors.ENDC}")
        
        # --- Execute Strip ---
        if prefix_to_strip:
            count = 0
            for f_path in files:
                f_name = f_path.name
                if f_name.startswith(prefix_to_strip):
                    new_name = f_name[len(prefix_to_strip):]
                    # Avoid empty names or names that become just extensions
                    if not new_name or new_name == f_path.suffix:
                        print(f"Skipping {f_name}: Result would be empty.")
                        continue
                        
                    new_full_path = target_path / new_name
                    if new_full_path.exists():
                        print(f"Skipping {f_name}: Target {new_name} exists.")
                    else:
                        try:
                            f_path.rename(new_full_path)
                            count += 1
                        except Exception as e:
                            print(f"Error renaming {f_name}: {e}")
            
            print(f"{Colors.GREEN}Done! Renamed {count} files.{Colors.ENDC}")
        else:
            print("Operation cancelled for this folder.")
            
        ask_again = input(f"\n{Colors.YELLOW}Clean another folder? (yes/no): {Colors.ENDC}").strip().lower()
        if ask_again != 'yes':
            break

def phase_5_long_name_cleanup(cutoff_time: float):
    print(f"\n{Colors.HEADER}=== PHASE 5: Long Filename Cleanup ==={Colors.ENDC}")
    ask = input(f"{Colors.YELLOW}Scan for filenames longer than {NAME_LENGTH_LIMIT} chars? (yes/no): {Colors.ENDC}").strip().lower()
    if ask != 'yes': return

    for root, dirs, files in os.walk(BASE_DIR):
        for f_name in files:
            if f_name.startswith('.'): continue
            
            f_path = Path(root) / f_name
            
            # Timestamp Check
            if cutoff_time > 0 and f_path.stat().st_mtime <= cutoff_time:
                continue

            if len(Path(f_name).stem) > NAME_LENGTH_LIMIT:
                print(f"\n{Colors.RED}Long Name ({len(f_path.stem)} chars):{Colors.ENDC} {f_name}")
                print(f"Location: {Path(root).relative_to(BASE_DIR)}")
                
                sug = suggest_short_name(f_name)
                print("Suggestions:")
                for i, s in enumerate(sug): print(f"  {i+1}. {s}")
                
                print(f"  {Colors.BOLD}Type number (1-{len(sug)}), new name, or [Enter] to skip.{Colors.ENDC}")
                choice = input(f"{Colors.YELLOW}   Input: {Colors.ENDC}").strip()
                
                new_name = ""
                if choice.isdigit() and 1 <= int(choice) <= len(sug):
                    new_name = sug[int(choice)-1]
                elif choice:
                    new_name = choice
                    if not new_name.endswith(f_path.suffix): new_name += f_path.suffix
                
                if new_name:
                    new_path = f_path.with_name(new_name)
                    if new_path.exists():
                        print("   ⚠️ Target exists, skipping.")
                    else:
                        try: f_path.rename(new_path); print(f"   ✅ Renamed: {new_name}")
                        except Exception as e: print(f"   ❌ Error: {e}")

def main():
    if not BASE_DIR.exists():
        print(f"Error: {BASE_DIR} not found.")
        return

    last_run = get_last_run_time()
    cutoff_time = 0.0

    if last_run > 0:
        readable_date = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(last_run))
        print(f"{Colors.BLUE}Last run was at: {readable_date}{Colors.ENDC}")
        ask = input(f"{Colors.YELLOW}Scan ONLY files modified after last run? (yes/no): {Colors.ENDC}").strip().lower()
        if ask == 'yes':
            cutoff_time = last_run
            print(f"{Colors.GREEN}Scanning only for new files...{Colors.ENDC}")
        else:
            print(f"{Colors.YELLOW}Scanning entire library...{Colors.ENDC}")
    else:
        print("First run detected (or history deleted). Scanning full library.")

    try:
        phase_1_non_wav_conversion(cutoff_time)
        phase_2_sample_rate_check(cutoff_time)
        phase_3_bit_depth_optimization(cutoff_time)
        phase_4_prefix_cleanup(cutoff_time)
        phase_5_long_name_cleanup(cutoff_time)
    finally:
        # Always update last run time on exit if at least Phase 1 completed partially
        update_last_run_time()
    
    print(f"\n{Colors.BOLD}All phases finished.{Colors.ENDC}")

if __name__ == "__main__":
    main()