use std::collections::HashMap;
use std::path::Path;

use crate::config::Converter;
use crate::substitute::substitute;

pub async fn convert(converter: &Converter, input_path: &Path, output_path: &Path) -> bool {
    let input_str = input_path.display().to_string();
    let stem = input_path
        .file_stem()
        .map(|s| s.to_string_lossy().to_string())
        .unwrap_or_default();
    let ext = input_path
        .extension()
        .map(|s| format!(".{}", s.to_string_lossy()))
        .unwrap_or_default();

    let suffix = output_path
        .extension()
        .map(|s| format!(".{}", s.to_string_lossy()))
        .unwrap_or_default();

    let temp_file = match tempfile::Builder::new()
        .suffix(&suffix)
        .tempfile_in(output_path.parent().unwrap_or(Path::new(".")))
    {
        Ok(f) => f,
        Err(e) => {
            tracing::warn!(
                "Failed to create temp file for {}: {}",
                input_path.display(),
                e
            );
            return false;
        }
    };
    let temp_str = temp_file.path().display().to_string();

    let variables: HashMap<&str, &str> = [
        ("input", input_str.as_str()),
        ("output", temp_str.as_str()),
        ("stem", stem.as_str()),
        ("ext", ext.as_str()),
    ]
    .into();

    let args = match substitute(&converter.command, &variables) {
        Ok(args) => args,
        Err(e) => {
            tracing::warn!(
                "Template substitution failed for {}: {}",
                converter.name,
                e
            );
            return false;
        }
    };

    tracing::info!("Converting {}", input_path.display());

    let child = match tokio::process::Command::new(&args[0])
        .args(&args[1..])
        .stdout(std::process::Stdio::piped())
        .stderr(std::process::Stdio::piped())
        .spawn()
    {
        Ok(c) => c,
        Err(e) => {
            tracing::warn!(
                "Failed to start converter {} for {}: {}",
                converter.name,
                input_path.display(),
                e
            );
            return false;
        }
    };

    let output = match child.wait_with_output().await {
        Ok(o) => o,
        Err(e) => {
            tracing::warn!(
                "Converter {} failed for {}: {}",
                converter.name,
                input_path.display(),
                e
            );
            return false;
        }
    };

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        tracing::warn!(
            "Converter {} failed for {} (exit {}): {}",
            converter.name,
            input_path.display(),
            output.status.code().unwrap_or(-1),
            stderr.trim()
        );
        return false;
    }

    if let Err(e) = temp_file.persist(output_path) {
        tracing::warn!(
            "Failed to persist temp file to {}: {}",
            output_path.display(),
            e
        );
        return false;
    }

    true
}
