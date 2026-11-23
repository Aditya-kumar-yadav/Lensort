# 📸 Lensort

> **Bring Focus to Your Chaotic Gallery.**  
> Next-Gen Smart Photo, Screenshot, WhatsApp & Video Organizer for Any PC.  
> Automatically detects EXIF dates, camera models, GPS coordinates (offline reverse-geocoding), identifies duplicates (exact & visual similarity), and organizes chaotic folders into intuitive structures.

---

## ✨ Features at a Glance

1. **Exact Date & Timeline Sorting (EXIF Metadata):**
   - Extracts capture timestamps from EXIF tags (`DateTimeOriginal`, `CreateDate`).
   - Smart fallbacks: WhatsApp filenames (`IMG-YYYYMMDD-WA....`), Android screenshot timestamps, iOS dates, and filesystem timestamps.
   - Automatically builds:
     ```
     📁 Camera Originals/
        📁 2024/
           📁 01 - January/
           📁 05 - May/
     ```

2. **Source & Type Separation:**
   - 📱 **Screenshots** $\to$ Detects via filename regex + 16:9 / 19.5:9 / 20:9 phone aspect ratios + absence of camera EXIF.
   - 💬 **WhatsApp & Social** $\to$ Identifies WhatsApp, Telegram, Instagram, Reddit, and meme naming conventions.
   - 📷 **Camera Originals** $\to$ Genuine photos preserving camera Make/Model (`Sony ILCE-7M4`, `Apple iPhone 15 Pro`, `Canon EOS`, etc.).
   - 🎥 **Videos** $\to$ Separate videos into dedicated timeline folders (`.mp4`, `.mov`, `.mkv`, `.avi`, `.webm`).
   - 📄 **Documents & Scans** $\to$ Invoices, bills, receipts, identity documents.

3. **Offline GPS Reverse Geocoding (Trips & Vacations):**
   - Reads GPS latitude & longitude embedded in EXIF.
   - **100% Offline:** Uses a built-in KD-Tree / Haversine database of global cities and Indian tourist destinations (Goa, Manali, Shimla, Delhi, Paris, Tokyo, Dubai, etc.).
   - **Zero API keys needed, zero internet needed**, runs in flight mode without rate limits!
   - Builds:
     ```
     📁 Trips/
        📁 Goa_2024/
        📁 Manali_2023/
        📁 Paris_2022/
     ```

4. **Multi-Stage Duplicate & Similar Image Detection:**
   - **Exact Duplicates:** Fast file-size grouping + chunked SHA-256 hashing.
   - **Perceptual (Visual) Duplicates:** Difference Hash (**dHash**) with Hamming distance comparison. Finds compressed or resized WhatsApp duplicates vs original DSLR/phone photos!
   - Actions: Isolate duplicates safely into `_Duplicates/` folder, skip, or reclaim disk space.

5. **Safe by Default (Dry-Run & 1-Click Rollback):**
   - **Dry Run Mode:** Previews every change in a beautiful terminal table without modifying any files on disk.
   - **1-Click Undo / Rollback:** Every move or copy writes an audit manifest (`.sort_manifest_<timestamp>.json`). Run `python main.py --undo <manifest>` to instantly restore every file back to its original location!
   - **Zero-Space Hardlinks:** Supports `--action hardlink` to organize files instantly on NTFS/ext4/APFS without consuming extra disk space.

---

## 🚀 Quick Start

### 1. Requirements
- Python 3.9+
- Dependencies: `Pillow`, `rich` (installed via `pip install -r requirements.txt`)

```bash
git clone https://github.com/your-username/Gallery_shorter.git
cd Gallery_shorter
pip install -r requirements.txt
```

### 2. Try the Live Demo
Test with synthetic photos, WhatsApp media, and duplicates in 5 seconds:
```bash
python demo.py
```

---

## 🛠️ Usage & Examples

### 1. Safe Preview (Dry Run - Default)
Scan your messy `Downloads` or `Pictures` folder without moving anything:
```bash
python main.py "C:\Users\Username\Downloads"
```

### 2. Safe Copy (Preserves Original Files)
Copy media into a clean organized folder structure:
```bash
python main.py "C:\Users\Username\Pictures" --dest "D:\Clean_Gallery" --action copy
```

### 3. Fast Move (Cleans Up Messy Folder)
Move files directly to organize your chaotic drive:
```bash
python main.py "C:\Users\Username\Downloads" --dest "C:\Users\Username\Pictures" --action move
```

### 4. Group by Trips & Vacations (GPS-based)
Group GPS photos into `Trips/City_Year`:
```bash
python main.py "C:\Users\Username\Pictures" --mode trips --action copy
```

### 5. 1-Click Undo / Rollback
Made a mistake? Easily restore everything using the session manifest:
```bash
python main.py --undo "D:\Clean_Gallery\.sort_manifest_20261123_183000.json"
```

### 6. Desktop GUI (Zero-Setup Graphical Mode)
Prefer a visual window with click-to-browse, live preview table, and visual duplicate badges?
```bash
python gui.py
# or
python main.py -g
```

### 7. Blazing-Fast Pure Rust CLI (`luminasort-rs`)
For scanning 10,000+ to 100,000+ files in seconds:
```bash
# Using the pre-compiled native binary in root:
.\luminasort-rs.exe "C:\Users\Username\Pictures" --action dry-run

# Or compile from source:
cd rust_engine
cargo build --release
```

---

## ⚙️ CLI Reference

| Flag | Description | Default |
|---|---|---|
| `source` | Source directory to scan | Positional argument |
| `-d`, `--dest` | Destination directory | `<source>/Organized_Gallery` |
| `-a`, `--action` | `dry-run`, `copy`, `move`, `hardlink` | `dry-run` |
| `-m`, `--mode` | `source-date`, `date-only`, `source-only`, `trips`, `custom` | `source-date` |
| `--pattern` | Custom format string (e.g. `{source}/{year}/{month_name}`) | `{source}/{year}/{month} - {month_name}` |
| `--no-dedup` | Disable exact duplicate detection | False |
| `--no-similar`| Disable visual (pHash/dHash) duplicate detection | False |
| `--dup-action`| `isolate` (move to `_Duplicates`), `skip`, or `delete` | `isolate` |
| `--no-geo` | Disable offline reverse geocoding | False |
| `--undo` | Path to `.sort_manifest_*.json` to rollback | None |
| `-i`, `--interactive` | Launch step-by-step interactive questionnaire | False |

---

## 📦 How to Compile into a Standalone `.exe` (For Any PC)

To distribute this to friends or family without needing Python installed:

```bash
pip install pyinstaller
pyinstaller --onefile --name "LuminaSort" main.py
```

The resulting `dist/LuminaSort.exe` can be copied to a USB drive or downloaded on any Windows PC and run with zero installation!

---

## 🧪 Running Automated Tests

Run the full end-to-end test suite (EXIF, GPS, WhatsApp, Screenshots, Dedup, Undo):
```bash
python test_sorter.py
```
Output:
```
Ran 3 tests in 0.274s
OK
```

---

## 📜 License
MIT License. Free for personal, open-source, and commercial use.
