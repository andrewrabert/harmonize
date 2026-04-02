use std::path::Path;
use std::process::Command;

pub fn generate_silence(seconds: u32, dest: &Path) {
    let status = Command::new("ffmpeg")
        .args([
            "-f",
            "lavfi",
            "-v",
            "quiet",
            "-i",
            "anullsrc=channel_layout=stereo:sample_rate=44100",
            "-t",
            &seconds.to_string(),
        ])
        .arg(dest.as_os_str())
        .status()
        .expect("failed to run ffmpeg");
    assert!(status.success(), "ffmpeg failed to generate silence");
}
