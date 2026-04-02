mod helpers;

use std::fs;
use std::path::Path;
use std::process::Command;

fn harmonize_bin() -> Command {
    Command::new(env!("CARGO_BIN_EXE_harmonize"))
}

fn write_config(
    dir: &Path,
    source_dir: &Path,
    target_dir: &Path,
    converters: &str,
    mappings: &str,
    extra: &str,
) -> std::path::PathBuf {
    let config_path = dir.join("harmonize.toml");
    let content = format!(
        r#"[harmonize]
source = "{}"
target = "{}"
{extra}

{converters}

{mappings}
"#,
        source_dir.display(),
        target_dir.display()
    );
    fs::write(&config_path, content).unwrap();
    config_path
}

#[test]
fn test_copies_other_file_type() {
    let tmp = tempfile::tempdir().unwrap();
    let source_dir = tmp.path().join("source");
    fs::create_dir(&source_dir).unwrap();
    let target_dir = tmp.path().join("target");
    let text_file = source_dir.join("other.txt");
    fs::write(&text_file, "test file").unwrap();

    let config_path = write_config(tmp.path(), &source_dir, &target_dir, "", "", "");

    let output = harmonize_bin()
        .args(["--config", &config_path.to_string_lossy()])
        .output()
        .unwrap();
    assert!(output.status.success(), "harmonize failed: {:?}", output);
    assert_eq!(output.stdout, b"");

    let stderr = String::from_utf8_lossy(&output.stderr);
    assert_eq!(
        stderr,
        format!(
            "Scanning \"{}\"\nScanned 1 items\nCopying {}\nProcessing complete\n",
            source_dir.display(),
            text_file.display()
        )
    );

    assert_eq!(
        fs::read_to_string(&text_file).unwrap(),
        fs::read_to_string(target_dir.join("other.txt")).unwrap()
    );
}

#[test]
fn test_converts_flac_to_opus() {
    let tmp = tempfile::tempdir().unwrap();
    let source_dir = tmp.path().join("source");
    fs::create_dir(&source_dir).unwrap();
    let target_dir = tmp.path().join("target");
    let audio_file = source_dir.join("audio.flac");
    helpers::ffmpeg::generate_silence(1, &audio_file);

    let config_path = write_config(
        tmp.path(),
        &source_dir,
        &target_dir,
        r#"[converters.opus]
command = ["ffmpeg", "-y", "-i", "{input}", "-c:a", "libopus", "-b:a", "128k", "{output}"]"#,
        r#"[mappings]
".flac" = { converter = "opus", output_ext = ".opus" }"#,
        "",
    );

    let output = harmonize_bin()
        .args(["--config", &config_path.to_string_lossy()])
        .output()
        .unwrap();
    assert!(output.status.success(), "harmonize failed: {:?}", output);
    assert_eq!(output.stdout, b"");

    let stderr = String::from_utf8_lossy(&output.stderr);
    assert_eq!(
        stderr,
        format!(
            "Scanning \"{}\"\nScanned 1 items\nConverting {}\nProcessing complete\n",
            source_dir.display(),
            audio_file.display()
        )
    );

    let metadata = helpers::ffprobe::get_metadata(&target_dir.join("audio.opus"));
    assert_eq!(metadata["format"]["format_name"], "ogg");
    assert_eq!(metadata["streams"].as_array().unwrap().len(), 1);
    assert_eq!(metadata["streams"][0]["codec_name"], "opus");
    let duration: f64 = metadata["format"]["duration"]
        .as_str()
        .unwrap()
        .parse()
        .unwrap();
    assert!((1.0..=1.1).contains(&duration), "duration: {duration}");
}

#[test]
fn test_converts_flac_to_mp3() {
    let tmp = tempfile::tempdir().unwrap();
    let source_dir = tmp.path().join("source");
    fs::create_dir(&source_dir).unwrap();
    let target_dir = tmp.path().join("target");
    let audio_file = source_dir.join("audio.flac");
    helpers::ffmpeg::generate_silence(1, &audio_file);

    let config_path = write_config(
        tmp.path(),
        &source_dir,
        &target_dir,
        r#"[converters.mp3]
command = ["ffmpeg", "-y", "-i", "{input}", "-c:a", "libmp3lame", "-q:a", "0", "{output}"]"#,
        r#"[mappings]
".flac" = { converter = "mp3", output_ext = ".mp3" }"#,
        "",
    );

    let output = harmonize_bin()
        .args(["--config", &config_path.to_string_lossy()])
        .output()
        .unwrap();
    assert!(output.status.success(), "harmonize failed: {:?}", output);
    assert_eq!(output.stdout, b"");

    let stderr = String::from_utf8_lossy(&output.stderr);
    assert_eq!(
        stderr,
        format!(
            "Scanning \"{}\"\nScanned 1 items\nConverting {}\nProcessing complete\n",
            source_dir.display(),
            audio_file.display()
        )
    );

    let metadata = helpers::ffprobe::get_metadata(&target_dir.join("audio.mp3"));
    assert_eq!(metadata["format"]["format_name"], "mp3");
    assert_eq!(metadata["streams"].as_array().unwrap().len(), 1);
    assert_eq!(metadata["streams"][0]["codec_name"], "mp3");
    let duration: f64 = metadata["format"]["duration"]
        .as_str()
        .unwrap()
        .parse()
        .unwrap();
    assert!((1.0..=1.1).contains(&duration), "duration: {duration}");
}

#[test]
fn test_multiple_mixed_audio_and_other_files() {
    let tmp = tempfile::tempdir().unwrap();
    let source_dir = tmp.path().join("source");
    fs::create_dir(&source_dir).unwrap();
    let target_dir = tmp.path().join("target");

    let text_file = source_dir.join("other.txt");
    fs::write(&text_file, "test file").unwrap();

    for duration in 1..=3u32 {
        helpers::ffmpeg::generate_silence(duration, &source_dir.join(format!("{duration}.flac")));
    }

    let config_path = write_config(
        tmp.path(),
        &source_dir,
        &target_dir,
        r#"[converters.mp3]
command = ["ffmpeg", "-y", "-i", "{input}", "-c:a", "libmp3lame", "-q:a", "0", "{output}"]"#,
        r#"[mappings]
".flac" = { converter = "mp3", output_ext = ".mp3" }"#,
        "",
    );

    let output = harmonize_bin()
        .args(["--config", &config_path.to_string_lossy()])
        .output()
        .unwrap();
    assert!(output.status.success(), "harmonize failed: {:?}", output);
    assert_eq!(output.stdout, b"");

    let stderr = String::from_utf8_lossy(&output.stderr);
    let lines: Vec<&str> = stderr.lines().collect();
    assert_eq!(lines[0], format!("Scanning \"{}\"", source_dir.display()));
    assert_eq!(lines[1], "Scanned 4 items");

    let mut middle: Vec<&str> = lines[2..6].to_vec();
    middle.sort();
    assert_eq!(
        middle,
        vec![
            &format!("Converting {}", source_dir.join("1.flac").display()),
            &format!("Converting {}", source_dir.join("2.flac").display()),
            &format!("Converting {}", source_dir.join("3.flac").display()),
            &format!("Copying {}", source_dir.join("other.txt").display()),
        ]
    );
    assert_eq!(lines[6], "Processing complete");

    for duration in 1..=3u32 {
        let metadata =
            helpers::ffprobe::get_metadata(&target_dir.join(format!("{duration}.mp3")));
        assert_eq!(metadata["format"]["format_name"], "mp3");
        assert_eq!(metadata["streams"].as_array().unwrap().len(), 1);
        assert_eq!(metadata["streams"][0]["codec_name"], "mp3");
        let dur: f64 = metadata["format"]["duration"]
            .as_str()
            .unwrap()
            .parse()
            .unwrap();
        assert!(
            (duration as f64..=duration as f64 + 0.1).contains(&dur),
            "duration: {dur}"
        );
    }

    assert_eq!(
        fs::read_to_string(&text_file).unwrap(),
        fs::read_to_string(target_dir.join("other.txt")).unwrap()
    );
}

#[test]
fn test_dry_run() {
    let tmp = tempfile::tempdir().unwrap();
    let source_dir = tmp.path().join("source");
    fs::create_dir(&source_dir).unwrap();
    let target_dir = tmp.path().join("target");
    fs::write(source_dir.join("other.txt"), "test file").unwrap();

    let config_path = write_config(tmp.path(), &source_dir, &target_dir, "", "", "");

    let output = harmonize_bin()
        .args(["--config", &config_path.to_string_lossy(), "--dry-run"])
        .output()
        .unwrap();
    assert!(output.status.success(), "harmonize failed: {:?}", output);
    assert_eq!(output.stdout, b"");

    let stderr = String::from_utf8_lossy(&output.stderr);
    assert!(stderr.contains("Would copy"));
    assert!(!target_dir.join("other.txt").exists());
}

