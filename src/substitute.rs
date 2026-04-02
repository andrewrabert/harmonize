use std::collections::{HashMap, HashSet};

use crate::error::SubstitutionError;

/// Substitute {var} placeholders in a list of command template strings.
///
/// Supports {{/}} escaping for literal braces. Errors on unknown variables
/// or unmatched braces.
pub fn substitute(
    template: &[String],
    variables: &HashMap<&str, &str>,
) -> Result<Vec<String>, SubstitutionError> {
    template.iter().map(|s| substitute_string(s, variables)).collect()
}

/// Validate that a command template only uses known variables.
pub fn validate_template(
    template: &[String],
    allowed_variables: &HashSet<&str>,
) -> Result<(), SubstitutionError> {
    let dummy: HashMap<&str, &str> = allowed_variables.iter().map(|&name| (name, "")).collect();
    for s in template {
        substitute_string(s, &dummy)?;
    }
    Ok(())
}

fn substitute_string(
    s: &str,
    variables: &HashMap<&str, &str>,
) -> Result<String, SubstitutionError> {
    let bytes = s.as_bytes();
    let mut result = String::new();
    let mut i = 0;

    while i < bytes.len() {
        match bytes[i] {
            b'{' => {
                if i + 1 < bytes.len() && bytes[i + 1] == b'{' {
                    result.push('{');
                    i += 2;
                } else {
                    let end = s[i + 1..].find('}').map(|pos| pos + i + 1);
                    match end {
                        None => {
                            return Err(SubstitutionError::UnmatchedOpen {
                                pos: i,
                                template: s.to_string(),
                            });
                        }
                        Some(end) => {
                            let name = &s[i + 1..end];
                            match variables.get(name) {
                                None => {
                                    return Err(SubstitutionError::UnknownVariable {
                                        name: name.to_string(),
                                        template: s.to_string(),
                                    });
                                }
                                Some(value) => {
                                    result.push_str(value);
                                }
                            }
                            i = end + 1;
                        }
                    }
                }
            }
            b'}' => {
                if i + 1 < bytes.len() && bytes[i + 1] == b'}' {
                    result.push('}');
                    i += 2;
                } else {
                    return Err(SubstitutionError::UnmatchedClose {
                        pos: i,
                        template: s.to_string(),
                    });
                }
            }
            _ => {
                result.push(bytes[i] as char);
                i += 1;
            }
        }
    }

    Ok(result)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn sub(template: &[&str], vars: &[(&str, &str)]) -> Result<Vec<String>, SubstitutionError> {
        let template: Vec<String> = template.iter().map(|s| s.to_string()).collect();
        let variables: HashMap<&str, &str> = vars.iter().copied().collect();
        substitute(&template, &variables)
    }

    #[test]
    fn test_basic_substitution() {
        let result = sub(&["{input}"], &[("input", "/path/to/file.flac")]).unwrap();
        assert_eq!(result, vec!["/path/to/file.flac"]);
    }

    #[test]
    fn test_multiple_variables() {
        let result = sub(
            &["-i", "{input}", "{output}"],
            &[("input", "in.flac"), ("output", "out.opus")],
        )
        .unwrap();
        assert_eq!(result, vec!["-i", "in.flac", "out.opus"]);
    }

    #[test]
    fn test_multiple_variables_in_one_string() {
        let result = sub(&["{stem}.{ext}"], &[("stem", "song"), ("ext", "flac")]).unwrap();
        assert_eq!(result, vec!["song.flac"]);
    }

    #[test]
    fn test_escaped_braces() {
        let result = sub(&["{{literal}}"], &[]).unwrap();
        assert_eq!(result, vec!["{literal}"]);
    }

    #[test]
    fn test_escaped_braces_mixed_with_variables() {
        let result = sub(&["{{before}}{input}{{after}}"], &[("input", "file")]).unwrap();
        assert_eq!(result, vec!["{before}file{after}"]);
    }

    #[test]
    fn test_unknown_variable() {
        let err = sub(&["{bad}"], &[("input", "x")]).unwrap_err();
        assert!(err.to_string().contains("Unknown variable"));
        assert!(err.to_string().contains("bad"));
    }

    #[test]
    fn test_unmatched_opening_brace() {
        let err = sub(&["{unclosed"], &[]).unwrap_err();
        assert!(err.to_string().contains("Unmatched opening brace"));
    }

    #[test]
    fn test_unmatched_closing_brace() {
        let err = sub(&["extra}"], &[]).unwrap_err();
        assert!(err.to_string().contains("Unmatched closing brace"));
    }

    #[test]
    fn test_empty_template() {
        let result = sub(&[], &[]).unwrap();
        assert_eq!(result, Vec::<String>::new());
    }

    #[test]
    fn test_no_placeholders() {
        let result = sub(&["-c:a", "libopus"], &[]).unwrap();
        assert_eq!(result, vec!["-c:a", "libopus"]);
    }

    #[test]
    fn test_variable_at_start_middle_end() {
        let result = sub(
            &["{input}/middle/{output}"],
            &[("input", "a"), ("output", "b")],
        )
        .unwrap();
        assert_eq!(result, vec!["a/middle/b"]);
    }

    #[test]
    fn test_validate_template_valid() {
        let template: Vec<String> = ["ffmpeg", "-i", "{input}", "{output}"]
            .iter()
            .map(|s| s.to_string())
            .collect();
        let allowed: HashSet<&str> = ["input", "output", "stem", "ext"].into();
        validate_template(&template, &allowed).unwrap();
    }

    #[test]
    fn test_validate_template_unknown_variable() {
        let template: Vec<String> = ["{bad}"].iter().map(|s| s.to_string()).collect();
        let allowed: HashSet<&str> = ["input", "output"].into();
        let err = validate_template(&template, &allowed).unwrap_err();
        assert!(err.to_string().contains("Unknown variable"));
        assert!(err.to_string().contains("bad"));
    }
}
