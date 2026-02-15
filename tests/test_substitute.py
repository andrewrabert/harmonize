import pytest

from harmonize.substitute import (
    SubstitutionError,
    substitute,
    validate_template,
)


def test_basic_substitution():
    result = substitute(["{input}"], {"input": "/path/to/file.flac"})
    assert result == ["/path/to/file.flac"]


def test_multiple_variables():
    result = substitute(
        ["-i", "{input}", "{output}"],
        {"input": "in.flac", "output": "out.opus"},
    )
    assert result == ["-i", "in.flac", "out.opus"]


def test_multiple_variables_in_one_string():
    result = substitute(["{stem}.{ext}"], {"stem": "song", "ext": "flac"})
    assert result == ["song.flac"]


def test_escaped_braces():
    result = substitute(["{{literal}}"], {})
    assert result == ["{literal}"]


def test_escaped_braces_mixed_with_variables():
    result = substitute(["{{before}}{input}{{after}}"], {"input": "file"})
    assert result == ["{before}file{after}"]


def test_unknown_variable():
    with pytest.raises(SubstitutionError, match="Unknown variable.*bad"):
        substitute(["{bad}"], {"input": "x"})


def test_unmatched_opening_brace():
    with pytest.raises(SubstitutionError, match="Unmatched opening brace"):
        substitute(["{unclosed"], {})


def test_unmatched_closing_brace():
    with pytest.raises(SubstitutionError, match="Unmatched closing brace"):
        substitute(["extra}"], {})


def test_empty_template():
    assert substitute([], {}) == []


def test_no_placeholders():
    result = substitute(["-c:a", "libopus"], {})
    assert result == ["-c:a", "libopus"]


def test_variable_at_start_middle_end():
    result = substitute(
        ["{input}/middle/{output}"], {"input": "a", "output": "b"}
    )
    assert result == ["a/middle/b"]


def test_validate_template_valid():
    validate_template(
        ["ffmpeg", "-i", "{input}", "{output}"],
        {"input", "output", "stem", "ext"},
    )


def test_validate_template_unknown_variable():
    with pytest.raises(SubstitutionError, match="Unknown variable.*bad"):
        validate_template(["{bad}"], {"input", "output"})
