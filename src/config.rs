use std::collections::{HashMap, HashSet};
use std::path::{Path, PathBuf};

use serde::Deserialize;

use crate::error::ConfigError;
use crate::substitute::validate_template;

const ALLOWED_VARIABLES: &[&str] = &["input", "output", "stem", "ext"];

#[derive(Debug, Clone)]
pub struct Converter {
    pub name: String,
    pub command: Vec<String>,
}

#[derive(Debug, Clone)]
pub struct Mapping {
    pub converter: String,
    pub output_ext: String,
}

#[derive(Debug, Clone)]
pub struct Config {
    pub source: PathBuf,
    pub target: PathBuf,
    pub copy_unmatched: bool,
    pub source_exclude: Vec<String>,
    pub target_exclude: Vec<String>,
    pub jobs: usize,
    pub converters: HashMap<String, Converter>,
    pub mappings: HashMap<String, Mapping>,
}

#[derive(Deserialize)]
struct RawConfig {
    harmonize: Option<RawHarmonize>,
    converters: Option<HashMap<String, RawConverter>>,
    mappings: Option<HashMap<String, RawMapping>>,
}

#[derive(Deserialize)]
struct RawHarmonize {
    source: Option<String>,
    target: Option<String>,
    copy_unmatched: Option<bool>,
    source_exclude: Option<Vec<String>>,
    target_exclude: Option<Vec<String>>,
    jobs: Option<usize>,
}

#[derive(Deserialize)]
struct RawConverter {
    command: Option<Vec<String>>,
}

#[derive(Deserialize)]
struct RawMapping {
    converter: Option<String>,
    output_ext: Option<String>,
}

pub fn load(path: &Path) -> Result<Config, ConfigError> {
    let content = std::fs::read_to_string(path).map_err(|e| {
        if e.kind() == std::io::ErrorKind::NotFound {
            ConfigError::FileNotFound(path.display().to_string())
        } else {
            ConfigError::Io {
                path: path.display().to_string(),
                source: e,
            }
        }
    })?;
    let raw: RawConfig = toml::from_str(&content).map_err(|e| ConfigError::TomlParseFile {
        path: path.display().to_string(),
        source: e,
    })?;
    parse(raw)
}

pub fn load_bytes(raw: &[u8]) -> Result<Config, ConfigError> {
    let content = std::str::from_utf8(raw)
        .map_err(|e| ConfigError::InvalidEncoding(e.to_string()))?;
    let raw: RawConfig = toml::from_str(content)?;
    parse(raw)
}

fn normalize_ext(ext: &str) -> String {
    let ext = ext.to_lowercase();
    if ext.starts_with('.') {
        ext
    } else {
        format!(".{ext}")
    }
}

fn parse(raw: RawConfig) -> Result<Config, ConfigError> {
    let harmonize = raw.harmonize.unwrap_or(RawHarmonize {
        source: None,
        target: None,
        copy_unmatched: None,
        source_exclude: None,
        target_exclude: None,
        jobs: None,
    });

    let source = harmonize
        .source
        .ok_or_else(|| ConfigError::MissingField("harmonize.source".to_string()))?;
    let source = PathBuf::from(source);

    let target = harmonize
        .target
        .ok_or_else(|| ConfigError::MissingField("harmonize.target".to_string()))?;
    let target = PathBuf::from(target);

    if !source.is_dir() {
        return Err(ConfigError::SourceNotExists(source.display().to_string()));
    }

    if target.exists() && !target.is_dir() {
        return Err(ConfigError::TargetNotDir(target.display().to_string()));
    }

    let copy_unmatched = harmonize.copy_unmatched.unwrap_or(true);
    let source_exclude = harmonize.source_exclude.unwrap_or_default();
    let target_exclude = harmonize.target_exclude.unwrap_or_default();
    let jobs = harmonize.jobs.unwrap_or(0);

    let allowed: HashSet<&str> = ALLOWED_VARIABLES.iter().copied().collect();

    let mut converters = HashMap::new();
    for (name, conv_data) in raw.converters.unwrap_or_default() {
        let command = conv_data
            .command
            .ok_or_else(|| ConfigError::MissingCommand { name: name.clone() })?;
        if command.is_empty() {
            return Err(ConfigError::EmptyCommand { name: name.clone() });
        }
        validate_template(&command, &allowed).map_err(|e| ConfigError::InvalidTemplate {
            name: name.clone(),
            source: e,
        })?;
        converters.insert(name.clone(), Converter { name, command });
    }

    let mut mappings = HashMap::new();
    for (ext, map_data) in raw.mappings.unwrap_or_default() {
        let ext = normalize_ext(&ext);

        let converter_name = map_data.converter.ok_or_else(|| {
            ConfigError::MissingField(format!("mappings.{ext}.converter"))
        })?;
        if !converters.contains_key(&converter_name) {
            return Err(ConfigError::UndefinedConverter {
                ext: ext.clone(),
                converter: converter_name,
            });
        }

        let output_ext = match map_data.output_ext {
            Some(oe) => normalize_ext(&oe),
            None => ext.clone(),
        };

        mappings.insert(
            ext.clone(),
            Mapping {
                converter: converter_name,
                output_ext,
            },
        );
    }

    Ok(Config {
        source,
        target,
        copy_unmatched,
        source_exclude,
        target_exclude,
        jobs,
        converters,
        mappings,
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;

    fn setup_tmp_dir() -> tempfile::TempDir {
        let tmp = tempfile::tempdir().unwrap();
        fs::create_dir(tmp.path().join("source")).unwrap();
        tmp
    }

    fn write_config(tmp_dir: &Path, toml_str: &str) -> PathBuf {
        let path = tmp_dir.join("harmonize.toml");
        fs::write(&path, toml_str).unwrap();
        path
    }

    #[test]
    fn test_valid_complete_config() {
        let tmp = setup_tmp_dir();
        let source = tmp.path().join("source");
        let target = tmp.path().join("target");
        let path = write_config(
            tmp.path(),
            &format!(
                r#"
[harmonize]
source = "{}"
target = "{}"
copy_unmatched = false
source_exclude = ["*.log"]
target_exclude = ["*.m3u"]
jobs = 4

[converters.opus]
command = ["ffmpeg", "-i", "{{input}}", "-c:a", "libopus", "{{output}}"]

[mappings]
".flac" = {{ converter = "opus", output_ext = ".opus" }}
"#,
                source.display(),
                target.display()
            ),
        );
        let cfg = load(&path).unwrap();
        assert_eq!(cfg.source, source);
        assert_eq!(cfg.target, target);
        assert!(!cfg.copy_unmatched);
        assert_eq!(cfg.source_exclude, vec!["*.log"]);
        assert_eq!(cfg.target_exclude, vec!["*.m3u"]);
        assert_eq!(cfg.jobs, 4);
        assert!(cfg.converters.contains_key("opus"));
        assert_eq!(
            cfg.converters["opus"].command,
            vec!["ffmpeg", "-i", "{input}", "-c:a", "libopus", "{output}"]
        );
        assert!(cfg.mappings.contains_key(".flac"));
        assert_eq!(cfg.mappings[".flac"].converter, "opus");
        assert_eq!(cfg.mappings[".flac"].output_ext, ".opus");
    }

    #[test]
    fn test_defaults() {
        let tmp = setup_tmp_dir();
        let source = tmp.path().join("source");
        let target = tmp.path().join("target");
        let path = write_config(
            tmp.path(),
            &format!(
                r#"
[harmonize]
source = "{}"
target = "{}"
"#,
                source.display(),
                target.display()
            ),
        );
        let cfg = load(&path).unwrap();
        assert!(cfg.copy_unmatched);
        assert!(cfg.source_exclude.is_empty());
        assert!(cfg.target_exclude.is_empty());
        assert_eq!(cfg.jobs, 0);
        assert!(cfg.converters.is_empty());
        assert!(cfg.mappings.is_empty());
    }

    #[test]
    fn test_missing_source() {
        let tmp = setup_tmp_dir();
        let target = tmp.path().join("target");
        let path = write_config(
            tmp.path(),
            &format!(
                r#"
[harmonize]
target = "{}"
"#,
                target.display()
            ),
        );
        let err = load(&path).unwrap_err();
        let msg = err.to_string();
        assert!(msg.contains("Missing required field"), "{msg}");
        assert!(msg.contains("source"), "{msg}");
    }

    #[test]
    fn test_missing_target() {
        let tmp = setup_tmp_dir();
        let source = tmp.path().join("source");
        let path = write_config(
            tmp.path(),
            &format!(
                r#"
[harmonize]
source = "{}"
"#,
                source.display()
            ),
        );
        let err = load(&path).unwrap_err();
        let msg = err.to_string();
        assert!(msg.contains("Missing required field"), "{msg}");
        assert!(msg.contains("target"), "{msg}");
    }

    #[test]
    fn test_source_not_exists() {
        let tmp = setup_tmp_dir();
        let target = tmp.path().join("target");
        let path = write_config(
            tmp.path(),
            &format!(
                r#"
[harmonize]
source = "{}"
target = "{}"
"#,
                tmp.path().join("nonexistent").display(),
                target.display()
            ),
        );
        let err = load(&path).unwrap_err();
        assert!(
            err.to_string().contains("Source directory does not exist"),
            "{}",
            err
        );
    }

    #[test]
    fn test_mapping_references_undefined_converter() {
        let tmp = setup_tmp_dir();
        let source = tmp.path().join("source");
        let target = tmp.path().join("target");
        let path = write_config(
            tmp.path(),
            &format!(
                r#"
[harmonize]
source = "{}"
target = "{}"

[mappings]
".flac" = {{ converter = "nope" }}
"#,
                source.display(),
                target.display()
            ),
        );
        let err = load(&path).unwrap_err();
        let msg = err.to_string();
        assert!(msg.contains("undefined converter"), "{msg}");
        assert!(msg.contains("nope"), "{msg}");
    }

    #[test]
    fn test_invalid_substitution_in_command() {
        let tmp = setup_tmp_dir();
        let source = tmp.path().join("source");
        let target = tmp.path().join("target");
        let path = write_config(
            tmp.path(),
            &format!(
                r#"
[harmonize]
source = "{}"
target = "{}"

[converters.bad]
command = ["ffmpeg", "{{unknown_var}}"]
"#,
                source.display(),
                target.display()
            ),
        );
        let err = load(&path).unwrap_err();
        assert!(
            err.to_string().contains("Invalid command template"),
            "{}",
            err
        );
    }

    #[test]
    fn test_extension_normalization() {
        let tmp = setup_tmp_dir();
        let source = tmp.path().join("source");
        let target = tmp.path().join("target");
        let path = write_config(
            tmp.path(),
            &format!(
                r#"
[harmonize]
source = "{}"
target = "{}"

[converters.opus]
command = ["ffmpeg", "-i", "{{input}}", "{{output}}"]

[mappings]
"flac" = {{ converter = "opus", output_ext = "opus" }}
".WAV" = {{ converter = "opus", output_ext = ".OGG" }}
"#,
                source.display(),
                target.display()
            ),
        );
        let cfg = load(&path).unwrap();
        assert!(cfg.mappings.contains_key(".flac"));
        assert_eq!(cfg.mappings[".flac"].output_ext, ".opus");
        assert!(cfg.mappings.contains_key(".wav"));
        assert_eq!(cfg.mappings[".wav"].output_ext, ".ogg");
    }

    #[test]
    fn test_no_output_ext_keeps_original() {
        let tmp = setup_tmp_dir();
        let source = tmp.path().join("source");
        let target = tmp.path().join("target");
        let path = write_config(
            tmp.path(),
            &format!(
                r#"
[harmonize]
source = "{}"
target = "{}"

[converters.compress]
command = ["magick", "{{input}}", "{{output}}"]

[mappings]
".jpg" = {{ converter = "compress" }}
"#,
                source.display(),
                target.display()
            ),
        );
        let cfg = load(&path).unwrap();
        assert_eq!(cfg.mappings[".jpg"].output_ext, ".jpg");
    }

    #[test]
    fn test_config_file_not_found() {
        let tmp = setup_tmp_dir();
        let err = load(&tmp.path().join("nonexistent.toml")).unwrap_err();
        assert!(
            err.to_string().contains("Config file not found"),
            "{}",
            err
        );
    }

    #[test]
    fn test_missing_converter_command() {
        let tmp = setup_tmp_dir();
        let source = tmp.path().join("source");
        let target = tmp.path().join("target");
        let path = write_config(
            tmp.path(),
            &format!(
                r#"
[harmonize]
source = "{}"
target = "{}"

[converters.bad]
something = "else"
"#,
                source.display(),
                target.display()
            ),
        );
        let err = load(&path).unwrap_err();
        let msg = err.to_string();
        assert!(msg.contains("Missing required field"), "{msg}");
        assert!(msg.contains("command"), "{msg}");
    }
}
