import pathlib
import textwrap

import pytest

from harmonize.config import ConfigError, load


@pytest.fixture
def tmp_dir(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    return tmp_path


def write_config(tmp_dir, toml_str):
    path = tmp_dir / "harmonize.toml"
    path.write_text(textwrap.dedent(toml_str))
    return path


def test_valid_complete_config(tmp_dir):
    cfg = load(
        write_config(
            tmp_dir,
            f"""\
        [harmonize]
        source = "{tmp_dir / "source"}"
        target = "{tmp_dir / "target"}"
        copy_unmatched = false
        source_exclude = ["*.log"]
        target_exclude = ["*.m3u"]
        jobs = 4

        [converters.opus]
        command = ["ffmpeg", "-i", "{{input}}", "-c:a", "libopus", "{{output}}"]

        [mappings]
        ".flac" = {{ converter = "opus", output_ext = ".opus" }}
    """,
        )
    )
    assert cfg.source == tmp_dir / "source"
    assert cfg.target == tmp_dir / "target"
    assert cfg.copy_unmatched is False
    assert cfg.source_exclude == ["*.log"]
    assert cfg.target_exclude == ["*.m3u"]
    assert cfg.jobs == 4
    assert "opus" in cfg.converters
    assert cfg.converters["opus"].command == [
        "ffmpeg",
        "-i",
        "{input}",
        "-c:a",
        "libopus",
        "{output}",
    ]
    assert ".flac" in cfg.mappings
    assert cfg.mappings[".flac"].converter == "opus"
    assert cfg.mappings[".flac"].output_ext == ".opus"


def test_defaults(tmp_dir):
    cfg = load(
        write_config(
            tmp_dir,
            f"""\
        [harmonize]
        source = "{tmp_dir / "source"}"
        target = "{tmp_dir / "target"}"
    """,
        )
    )
    assert cfg.copy_unmatched is True
    assert cfg.source_exclude == []
    assert cfg.target_exclude == []
    assert cfg.jobs == 0
    assert cfg.converters == {}
    assert cfg.mappings == {}


def test_missing_source(tmp_dir):
    with pytest.raises(ConfigError, match="Missing required field.*source"):
        load(
            write_config(
                tmp_dir,
                f"""\
            [harmonize]
            target = "{tmp_dir / "target"}"
        """,
            )
        )


def test_missing_target(tmp_dir):
    with pytest.raises(ConfigError, match="Missing required field.*target"):
        load(
            write_config(
                tmp_dir,
                f"""\
            [harmonize]
            source = "{tmp_dir / "source"}"
        """,
            )
        )


def test_source_not_exists(tmp_dir):
    with pytest.raises(ConfigError, match="Source directory does not exist"):
        load(
            write_config(
                tmp_dir,
                f"""\
            [harmonize]
            source = "{tmp_dir / "nonexistent"}"
            target = "{tmp_dir / "target"}"
        """,
            )
        )


def test_mapping_references_undefined_converter(tmp_dir):
    with pytest.raises(ConfigError, match="undefined converter.*nope"):
        load(
            write_config(
                tmp_dir,
                f"""\
            [harmonize]
            source = "{tmp_dir / "source"}"
            target = "{tmp_dir / "target"}"

            [mappings]
            ".flac" = {{ converter = "nope" }}
        """,
            )
        )


def test_invalid_substitution_in_command(tmp_dir):
    with pytest.raises(ConfigError, match="Invalid command template"):
        load(
            write_config(
                tmp_dir,
                f"""\
            [harmonize]
            source = "{tmp_dir / "source"}"
            target = "{tmp_dir / "target"}"

            [converters.bad]
            command = ["ffmpeg", "{{unknown_var}}"]
        """,
            )
        )


def test_extension_normalization(tmp_dir):
    cfg = load(
        write_config(
            tmp_dir,
            f"""\
        [harmonize]
        source = "{tmp_dir / "source"}"
        target = "{tmp_dir / "target"}"

        [converters.opus]
        command = ["ffmpeg", "-i", "{{input}}", "{{output}}"]

        [mappings]
        "flac" = {{ converter = "opus", output_ext = "opus" }}
        ".WAV" = {{ converter = "opus", output_ext = ".OGG" }}
    """,
        )
    )
    assert ".flac" in cfg.mappings
    assert cfg.mappings[".flac"].output_ext == ".opus"
    assert ".wav" in cfg.mappings
    assert cfg.mappings[".wav"].output_ext == ".ogg"


def test_no_output_ext_keeps_original(tmp_dir):
    cfg = load(
        write_config(
            tmp_dir,
            f"""\
        [harmonize]
        source = "{tmp_dir / "source"}"
        target = "{tmp_dir / "target"}"

        [converters.compress]
        command = ["magick", "{{input}}", "{{output}}"]

        [mappings]
        ".jpg" = {{ converter = "compress" }}
    """,
        )
    )
    assert cfg.mappings[".jpg"].output_ext == ".jpg"


def test_config_file_not_found(tmp_dir):
    with pytest.raises(ConfigError, match="Config file not found"):
        load(tmp_dir / "nonexistent.toml")


def test_missing_converter_command(tmp_dir):
    with pytest.raises(ConfigError, match="Missing required field.*command"):
        load(
            write_config(
                tmp_dir,
                f"""\
            [harmonize]
            source = "{tmp_dir / "source"}"
            target = "{tmp_dir / "target"}"

            [converters.bad]
            something = "else"
        """,
            )
        )
