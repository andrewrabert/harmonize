use thiserror::Error;

#[derive(Error, Debug)]
pub enum ConfigError {
    #[error("Config file not found: {0}")]
    FileNotFound(String),
    #[error("Failed to read config {path}: {source}")]
    Io {
        path: String,
        source: std::io::Error,
    },
    #[error("Invalid TOML in {path}: {source}")]
    TomlParseFile {
        path: String,
        source: toml::de::Error,
    },
    #[error("Invalid TOML: {0}")]
    TomlParse(#[from] toml::de::Error),
    #[error("Invalid config encoding: {0}")]
    InvalidEncoding(String),
    #[error("Missing required field: {0}")]
    MissingField(String),
    #[error("Source directory does not exist: {0}")]
    SourceNotExists(String),
    #[error("Target path exists but is not a directory: {0}")]
    TargetNotDir(String),
    #[error("Missing required field: converters.{name}.command")]
    MissingCommand { name: String },
    #[error("converters.{name}.command must be a non-empty list")]
    EmptyCommand { name: String },
    #[error("Invalid command template for converter {name}: {source}")]
    InvalidTemplate {
        name: String,
        source: SubstitutionError,
    },
    #[error("Mapping {ext} references undefined converter: {converter}")]
    UndefinedConverter { ext: String, converter: String },
}

#[derive(Error, Debug)]
pub enum SubstitutionError {
    #[error("Unmatched opening brace at position {pos} in: {template}")]
    UnmatchedOpen { pos: usize, template: String },
    #[error("Unmatched closing brace at position {pos} in: {template}")]
    UnmatchedClose { pos: usize, template: String },
    #[error("Unknown variable {{{name}}} in: {template}")]
    UnknownVariable { name: String, template: String },
}
