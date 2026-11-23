use std::collections::{HashMap, HashSet};
use std::fs::{self, File};
use std::io::{self, Read};
use std::path::{Path, PathBuf};
use std::time::Instant;

use chrono::{Datelike, Local, NaiveDate, NaiveDateTime};
use rayon::prelude::*;
use regex::Regex;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use walkdir::WalkDir;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OperationRecord {
    pub source: String,
    pub dest: String,
    pub category: String,
    pub size: u64,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct UndoManifest {
    pub timestamp: String,
    pub action: String,
    pub operations: Vec<OperationRecord>,
}

pub struct MediaFile {
    pub path: PathBuf,
    pub size: u64,
    pub date_taken: Option<NaiveDateTime>,
    pub category: String,
}

fn compute_sha256(path: &Path) -> io::Result<String> {
    let mut file = File::open(path)?;
    let mut hasher = Sha256::new();
    let mut buffer = [0u8; 65536];

    loop {
        let count = file.read(&mut buffer)?;
        if count == 0 {
            break;
        }
        hasher.update(&buffer[..count]);
    }
    Ok(format!("{:x}", hasher.finalize()))
}

fn extract_exif_date(path: &Path) -> Option<NaiveDateTime> {
    let file = File::open(path).ok()?;
    let mut bufreader = io::BufReader::new(&file);
    let exifreader = exif::Reader::new();
    let exif = exifreader.read_from_container(&mut bufreader).ok()?;

    if let Some(field) = exif.get_field(exif::Tag::DateTimeOriginal, exif::In::PRIMARY) {
        let val_str = field.display_value().to_string();
        // Typically "YYYY-MM-DD HH:MM:SS" or "YYYY:MM:DD HH:MM:SS"
        let clean = val_str.replace(':', "-");
        if clean.len() >= 19 {
            if let Ok(dt) = NaiveDateTime::parse_from_str(&clean[..19], "%Y-%m-%d %H-%M-%S") {
                return Some(dt);
            }
        }
    }
    None
}

fn extract_date_from_filename(filename: &str) -> Option<NaiveDateTime> {
    // WhatsApp pattern: IMG-20231104-WA0001
    let wa_re = Regex::new(r"(?:IMG|VID)-\d{8}-WA").unwrap();
    if wa_re.is_match(filename) {
        let digits_re = Regex::new(r"(\d{4})(\d{2})(\d{2})").unwrap();
        if let Some(caps) = digits_re.captures(filename) {
            let y: i32 = caps[1].parse().ok()?;
            let m: u32 = caps[2].parse().ok()?;
            let d: u32 = caps[3].parse().ok()?;
            return NaiveDate::from_ymd_opt(y, m, d)?.and_hms_opt(0, 0, 0);
        }
    }

    // Generic Date: 2024-05-12 or 20240512
    let gen_re = Regex::new(r"(20\d{2})[-_]?(0[1-9]|1[0-2])[-_]?(0[1-9]|[12]\d|3[01])").unwrap();
    if let Some(caps) = gen_re.captures(filename) {
        let y: i32 = caps[1].parse().ok()?;
        let m: u32 = caps[2].parse().ok()?;
        let d: u32 = caps[3].parse().ok()?;
        return NaiveDate::from_ymd_opt(y, m, d)?.and_hms_opt(0, 0, 0);
    }

    None
}

fn classify_file(path: &Path) -> String {
    let name_lower = path.file_name().unwrap_or_default().to_string_lossy().to_lowercase();
    let ext = path.extension().unwrap_or_default().to_string_lossy().to_lowercase();

    if ["mp4", "mov", "mkv", "avi", "webm"].contains(&ext.as_str()) {
        return "Videos".to_string();
    }
    if name_lower.contains("wa") || name_lower.contains("whatsapp") || name_lower.contains("telegram") {
        return "WhatsApp & Social".to_string();
    }
    if name_lower.contains("screenshot") || name_lower.contains("screen shot") || name_lower.contains("screencap") {
        return "Screenshots".to_string();
    }

    "Camera Originals".to_string()
}

fn main() {
    let args: Vec<String> = std::env::args().collect();

    println!("============================================================");
    println!(" ⚡ Lensort — Ultra-Fast Native Photo Sorter (Rust)");
    println!("============================================================");

    if args.len() < 2 || args[1] == "--help" || args[1] == "-h" {
        println!("Usage:");
        println!("  lensort <source_folder> [--action copy|move|dry-run] [--dest <dest_folder>]");
        println!("  lensort --undo <manifest.json>\n");
        println!("Examples:");
        println!("  lensort C:\\Users\\...\\Pictures --action dry-run");
        println!("  lensort C:\\Users\\...\\Downloads --action copy --dest D:\\Sorted_Photos");
        return;
    }

    // Handle Undo
    if args[1] == "--undo" {
        if args.len() < 3 {
            eprintln!("Error: Please specify the manifest file to undo.");
            return;
        }
        undo_session(&args[2]);
        return;
    }

    let source_dir = PathBuf::from(&args[1]);
    if !source_dir.is_dir() {
        eprintln!("Error: Source directory does not exist: {:?}", source_dir);
        return;
    }

    let mut action = "dry-run".to_string();
    let mut dest_dir = source_dir.join("Organized_Gallery");

    let mut i = 2;
    while i < args.len() {
        if args[i] == "--action" && i + 1 < args.len() {
            action = args[i + 1].clone();
            i += 2;
        } else if args[i] == "--dest" && i + 1 < args.len() {
            dest_dir = PathBuf::from(&args[i + 1]);
            i += 2;
        } else {
            i += 1;
        }
    }

    println!("🔍 Scanning: {:?}", source_dir);
    println!("📂 Destination: {:?}", dest_dir);
    println!("⚙️  Action Mode: {}", action.to_uppercase());

    let start_time = Instant::now();

    let extensions = ["jpg", "jpeg", "png", "webp", "heic", "mp4", "mov", "mkv", "avi", "webm"];

    // 1. Parallel Directory Walk
    let raw_files: Vec<PathBuf> = WalkDir::new(&source_dir)
        .into_iter()
        .filter_map(|e| e.ok())
        .filter(|e| e.file_type().is_file())
        .map(|e| e.into_path())
        .filter(|p| {
            if let Some(ext) = p.extension() {
                extensions.contains(&ext.to_string_lossy().to_lowercase().as_str())
            } else {
                false
            }
        })
        .collect();

    println!("📊 Found {} media files.", raw_files.len());

    // 2. Parallel Metadata & Date Extraction
    let media_files: Vec<MediaFile> = raw_files
        .par_iter()
        .map(|path| {
            let size = fs::metadata(path).map(|m| m.len()).unwrap_or(0);
            let filename = path.file_name().unwrap_or_default().to_string_lossy();
            let mut date = extract_exif_date(path);
            if date.is_none() {
                date = extract_date_from_filename(&filename);
            }
            let category = classify_file(path);
            MediaFile {
                path: path.clone(),
                size,
                date_taken: date,
                category,
            }
        })
        .collect();

    // 3. Two-Stage Duplicate Detection (Size Grouping + Multithreaded SHA-256)
    println!("⚡ Detecting exact duplicates...");
    let mut size_map: HashMap<u64, Vec<&MediaFile>> = HashMap::new();
    for f in &media_files {
        if f.size > 0 {
            size_map.entry(f.size).or_default().push(f);
        }
    }

    let candidate_duplicates: Vec<&MediaFile> = size_map
        .into_values()
        .filter(|g| g.len() > 1)
        .flatten()
        .collect();

    let hashed_files: Vec<(&MediaFile, String)> = candidate_duplicates
        .par_iter()
        .filter_map(|f| {
            compute_sha256(&f.path).ok().map(|hash| (*f, hash))
        })
        .collect();

    let mut hash_groups: HashMap<String, Vec<&MediaFile>> = HashMap::new();
    for (f, hash) in hashed_files {
        hash_groups.entry(hash).or_default().push(f);
    }

    let mut duplicate_paths: HashSet<PathBuf> = HashSet::new();
    let mut saved_bytes = 0u64;

    for (_hash, files) in hash_groups {
        if files.len() > 1 {
            // Keep first as original, mark the rest as duplicates
            for dup in &files[1..] {
                duplicate_paths.insert(dup.path.clone());
                saved_bytes += dup.size;
            }
        }
    }

    println!("✅ Exact Duplicates Found: {} ({:.2} MB reclaimable)",
        duplicate_paths.len(),
        saved_bytes as f64 / 1_048_576.0
    );

    // 4. Execution / Dry Run Plan
    let month_names = [
        "01 - January", "02 - February", "03 - March", "04 - April",
        "05 - May", "06 - June", "07 - July", "08 - August",
        "09 - September", "10 - October", "11 - November", "12 - December"
    ];

    let mut operations = Vec::new();

    for f in &media_files {
        let is_dup = duplicate_paths.contains(&f.path);
        let filename = f.path.file_name().unwrap_or_default();

        let target_dir = if is_dup {
            dest_dir.join("_Duplicates").join("Exact")
        } else {
            let (year, month_folder) = if let Some(dt) = f.date_taken {
                (dt.year().to_string(), month_names[(dt.month() - 1) as usize])
            } else {
                ("Unknown_Date".to_string(), "Unsorted")
            };

            match f.category.as_str() {
                "Screenshots" => dest_dir.join("Screenshots").join(&year),
                "Videos" => dest_dir.join("Videos").join(&year),
                "WhatsApp & Social" => dest_dir.join("WhatsApp & Social").join(&year).join(month_folder),
                _ => dest_dir.join("Camera Originals").join(&year).join(month_folder),
            }
        };

        let target_file = target_dir.join(filename);

        operations.push(OperationRecord {
            source: f.path.to_string_lossy().to_string(),
            dest: target_file.to_string_lossy().to_string(),
            category: f.category.clone(),
            size: f.size,
        });
    }

    let elapsed = start_time.elapsed();
    println!("⚡ Total Analysis Time: {:.2?}", elapsed);

    // Output sample preview
    println!("\n📁 Sample Destination Preview (Top 5 files):");
    for op in operations.iter().take(5) {
        println!("  • {} -> {}", Path::new(&op.source).file_name().unwrap().to_string_lossy(), op.dest);
    }

    if action == "dry-run" {
        println!("\n⚠️  DRY RUN MODE: No files were changed.");
        println!("To move or copy files, re-run with: --action copy  OR  --action move");
        return;
    }

    // Execute Copy or Move
    println!("\n🚀 Executing {} operations...", action.to_uppercase());
    for op in &operations {
        let src = Path::new(&op.source);
        let dst = Path::new(&op.dest);
        if let Some(parent) = dst.parent() {
            let _ = fs::create_dir_all(parent);
        }
        if action == "copy" {
            let _ = fs::copy(src, dst);
        } else if action == "move" {
            let _ = fs::rename(src, dst);
        }
    }

    // Write undo manifest
    let manifest_name = format!(".sort_manifest_{}.json", Local::now().format("%Y%m%d_%H%M%S"));
    let manifest_path = dest_dir.join(manifest_name);
    let manifest = UndoManifest {
        timestamp: Local::now().to_rfc3339(),
        action: action.clone(),
        operations,
    };

    if let Ok(file) = File::create(&manifest_path) {
        let _ = serde_json::to_writer_pretty(file, &manifest);
        println!("✅ Manifest saved: {:?}", manifest_path);
        println!("To undo: lensort --undo {:?}", manifest_path);
    }
}

fn undo_session(manifest_path_str: &str) {
    let path = Path::new(manifest_path_str);
    let file = match File::open(path) {
        Ok(f) => f,
        Err(e) => {
            eprintln!("Error opening manifest: {}", e);
            return;
        }
    };

    let manifest: UndoManifest = match serde_json::from_reader(file) {
        Ok(m) => m,
        Err(e) => {
            eprintln!("Error parsing manifest JSON: {}", e);
            return;
        }
    };

    println!("🔄 Reverting {} operations (Action was: {})...", manifest.operations.len(), manifest.action);
    let mut success = 0;

    for op in manifest.operations.iter().rev() {
        let src = Path::new(&op.source);
        let dst = Path::new(&op.dest);

        if dst.exists() {
            if manifest.action == "move" {
                if let Some(parent) = src.parent() {
                    let _ = fs::create_dir_all(parent);
                }
                if fs::rename(dst, src).is_ok() {
                    success += 1;
                }
            } else if manifest.action == "copy" {
                if fs::remove_file(dst).is_ok() {
                    success += 1;
                }
            }
        }
    }

    println!("✅ Undo complete! Restored {} files.", success);
}
