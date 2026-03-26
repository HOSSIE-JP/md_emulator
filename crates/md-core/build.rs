use std::fs;
use std::path::{Path, PathBuf};
use std::process::Command;
use std::time::{SystemTime, UNIX_EPOCH};

fn main() {
    let manifest_dir = PathBuf::from(std::env::var("CARGO_MANIFEST_DIR").unwrap());
    let workspace_root = manifest_dir.join("../..");
    let build_secs = newest_source_mtime(&workspace_root)
        .and_then(|mtime| mtime.duration_since(UNIX_EPOCH).ok())
        .map(|duration| duration.as_secs())
        .unwrap_or_else(|| {
            SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .unwrap()
                .as_secs()
        });

    let build_timestamp = format_utc_timestamp(build_secs);
    let git_sha = git_short_sha(&workspace_root).unwrap_or_else(|| "nogit".to_string());
    let git_dirty = git_dirty_state(&workspace_root).unwrap_or(false);

    println!("cargo:rustc-env=BUILD_TIMESTAMP={build_timestamp}");
    println!("cargo:rustc-env=BUILD_GIT_SHA={git_sha}");
    println!("cargo:rustc-env=BUILD_GIT_DIRTY={}", if git_dirty { "dirty" } else { "clean" });

    register_git_rerun_files(&workspace_root);
}

fn newest_source_mtime(workspace_root: &Path) -> Option<SystemTime> {
    let mut newest = None;
    for relative in [
        Path::new("Cargo.toml"),
        Path::new("package.json"),
        Path::new("docs"),
        Path::new("frontend"),
        Path::new("crates"),
    ] {
        let path = workspace_root.join(relative);
        visit_path(&path, &mut newest);
    }
    newest
}

fn visit_path(path: &Path, newest: &mut Option<SystemTime>) {
    let Some(name) = path.file_name().and_then(|name| name.to_str()) else {
        return;
    };

    if matches!(name, ".git" | "target" | "node_modules" | "pkg") {
        return;
    }

    if path.is_dir() {
        if let Ok(entries) = fs::read_dir(path) {
            for entry in entries.flatten() {
                visit_path(&entry.path(), newest);
            }
        }
        return;
    }

    if let Ok(metadata) = fs::metadata(path) {
        println!("cargo:rerun-if-changed={}", path.display());
        if let Ok(modified) = metadata.modified() {
            if newest.map(|current| modified > current).unwrap_or(true) {
                *newest = Some(modified);
            }
        }
    }
}

fn register_git_rerun_files(workspace_root: &Path) {
    let git_dir = workspace_root.join(".git");
    let head_path = git_dir.join("HEAD");
    if head_path.exists() {
        println!("cargo:rerun-if-changed={}", head_path.display());
        if let Ok(head) = fs::read_to_string(&head_path) {
            if let Some(reference) = head.strip_prefix("ref: ").map(str::trim) {
                let ref_path = git_dir.join(reference);
                if ref_path.exists() {
                    println!("cargo:rerun-if-changed={}", ref_path.display());
                }
            }
        }
    }

    let index_path = git_dir.join("index");
    if index_path.exists() {
        println!("cargo:rerun-if-changed={}", index_path.display());
    }
}

fn git_short_sha(workspace_root: &Path) -> Option<String> {
    let output = Command::new("git")
        .arg("rev-parse")
        .arg("--short=12")
        .arg("HEAD")
        .current_dir(workspace_root)
        .output()
        .ok()?;
    if !output.status.success() {
        return None;
    }
    let sha = String::from_utf8(output.stdout).ok()?;
    Some(sha.trim().to_string())
}

fn git_dirty_state(workspace_root: &Path) -> Option<bool> {
    let output = Command::new("git")
        .args(["status", "--porcelain", "--untracked-files=no"])
        .current_dir(workspace_root)
        .output()
        .ok()?;
    if !output.status.success() {
        return None;
    }
    Some(!output.stdout.is_empty())
}

fn format_utc_timestamp(secs: u64) -> String {
    let s = secs as i64;
    let day_secs = s % 86400;
    let h = day_secs / 3600;
    let m = (day_secs % 3600) / 60;
    let sec = day_secs % 60;

    let mut days = s / 86400;
    let mut y: i64 = 1970;
    loop {
        let leap = (y % 4 == 0 && y % 100 != 0) || y % 400 == 0;
        let ydays = if leap { 366 } else { 365 };
        if days < ydays {
            break;
        }
        days -= ydays;
        y += 1;
    }

    let leap = (y % 4 == 0 && y % 100 != 0) || y % 400 == 0;
    let mdays = [31, if leap { 29 } else { 28 }, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
    let mut mo = 0usize;
    for (index, month_days) in mdays.iter().enumerate() {
        if days < *month_days {
            break;
        }
        days -= *month_days;
        mo = index + 1;
    }

    let mo = mo + 1;
    let d = days + 1;
    format!("{y:04}{mo:02}{d:02}-{h:02}{m:02}{sec:02}")
}
