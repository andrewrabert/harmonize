use std::path::Path;
use std::process::Command;

pub fn get_metadata(path: &Path) -> serde_json::Value {
    let output = Command::new("ffprobe")
        .args([
            "-i",
            &path.to_string_lossy(),
            "-v",
            "quiet",
            "-show_streams",
            "-show_format",
            "-of",
            "json",
        ])
        .output()
        .expect("failed to run ffprobe");
    assert!(output.status.success(), "ffprobe failed");
    serde_json::from_slice(&output.stdout).expect("invalid json from ffprobe")
}
