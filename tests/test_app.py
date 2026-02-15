import pathlib
import shutil
import subprocess
import textwrap

import pytest

from tests import helpers

TMP = pathlib.Path(__file__).parent.joinpath("tmp")


@pytest.fixture(autouse=True)
def setup_tmp_dir():
    try:
        shutil.rmtree(TMP)
    except FileNotFoundError:
        pass
    TMP.mkdir()
    yield
    try:
        shutil.rmtree(TMP)
    except FileNotFoundError:
        pass


def write_config(source_dir, target_dir, converters="", mappings="", extra=""):
    config_path = TMP / "harmonize.toml"
    config_path.write_text(
        textwrap.dedent(f"""\
        [harmonize]
        source = "{source_dir}"
        target = "{target_dir}"
        {extra}

        {converters}

        {mappings}
    """)
    )
    return config_path


def test_copies_other_file_type():
    source_dir = TMP / "source"
    source_dir.mkdir()
    target_dir = TMP / "target"
    text_file = source_dir / "other.txt"
    text_file.write_text("test file")

    config_path = write_config(source_dir, target_dir)

    proc = subprocess.run(
        ["harmonize", "--config", str(config_path)],
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE,
        check=True,
    )
    assert proc.stdout == b""
    assert proc.stderr.decode() == (
        f'Scanning "{source_dir}"\n'
        "Scanned 1 items\n"
        f"Copying {text_file}\n"
        "Processing complete\n"
    )

    assert text_file.read_text() == (target_dir / "other.txt").read_text()


def test_converts_flac_to_opus():
    source_dir = TMP / "source"
    source_dir.mkdir()
    target_dir = TMP / "target"
    audio_file = source_dir / "audio.flac"
    helpers.ffmpeg.generate_silence(1, audio_file)

    config_path = write_config(
        source_dir,
        target_dir,
        converters=textwrap.dedent("""\
            [converters.opus]
            command = ["ffmpeg", "-y", "-i", "{input}", "-c:a", "libopus", "-b:a", "128k", "{output}"]
        """),
        mappings=textwrap.dedent("""\
            [mappings]
            ".flac" = { converter = "opus", output_ext = ".opus" }
        """),
    )

    proc = subprocess.run(
        ["harmonize", "--config", str(config_path)],
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE,
        check=True,
    )
    assert proc.stdout == b""
    assert proc.stderr.decode() == (
        f'Scanning "{source_dir}"\n'
        "Scanned 1 items\n"
        f"Converting {audio_file}\n"
        "Processing complete\n"
    )

    metadata = helpers.ffprobe.get_metadata(target_dir / "audio.opus")

    assert metadata["format"]["format_name"] == "ogg"
    assert len(metadata["streams"]) == 1
    assert metadata["streams"][0]["codec_name"] == "opus"
    assert 1 <= float(metadata["format"]["duration"]) <= 1.1


def test_converts_flac_to_mp3():
    source_dir = TMP / "source"
    source_dir.mkdir()
    target_dir = TMP / "target"
    audio_file = source_dir / "audio.flac"
    helpers.ffmpeg.generate_silence(1, audio_file)

    config_path = write_config(
        source_dir,
        target_dir,
        converters=textwrap.dedent("""\
            [converters.mp3]
            command = ["ffmpeg", "-y", "-i", "{input}", "-c:a", "libmp3lame", "-q:a", "0", "{output}"]
        """),
        mappings=textwrap.dedent("""\
            [mappings]
            ".flac" = { converter = "mp3", output_ext = ".mp3" }
        """),
    )

    proc = subprocess.run(
        ["harmonize", "--config", str(config_path)],
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE,
        check=True,
    )
    assert proc.stdout == b""
    assert proc.stderr.decode() == (
        f'Scanning "{source_dir}"\n'
        "Scanned 1 items\n"
        f"Converting {audio_file}\n"
        "Processing complete\n"
    )

    metadata = helpers.ffprobe.get_metadata(target_dir / "audio.mp3")

    assert metadata["format"]["format_name"] == "mp3"
    assert len(metadata["streams"]) == 1
    assert metadata["streams"][0]["codec_name"] == "mp3"
    assert 1 <= float(metadata["format"]["duration"]) <= 1.1


def test_multiple_mixed_audio_and_other_files():
    source_dir = TMP / "source"
    source_dir.mkdir()
    target_dir = TMP / "target"

    text_file = source_dir / "other.txt"
    text_file.write_text("test file")

    for duration in range(1, 4):
        helpers.ffmpeg.generate_silence(
            duration, source_dir / f"{duration}.flac"
        )

    config_path = write_config(
        source_dir,
        target_dir,
        converters=textwrap.dedent("""\
            [converters.mp3]
            command = ["ffmpeg", "-y", "-i", "{input}", "-c:a", "libmp3lame", "-q:a", "0", "{output}"]
        """),
        mappings=textwrap.dedent("""\
            [mappings]
            ".flac" = { converter = "mp3", output_ext = ".mp3" }
        """),
    )

    proc = subprocess.run(
        ["harmonize", "--config", str(config_path)],
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE,
        check=True,
    )
    assert proc.stdout == b""

    stderr = proc.stderr.decode().splitlines()
    assert stderr[0:2] == [f'Scanning "{source_dir}"', "Scanned 4 items"]
    assert sorted(stderr[2:6]) == [
        f"Converting {source_dir}/1.flac",
        f"Converting {source_dir}/2.flac",
        f"Converting {source_dir}/3.flac",
        f"Copying {source_dir}/other.txt",
    ]
    assert stderr[6] == "Processing complete"

    for duration in range(1, 4):
        metadata = helpers.ffprobe.get_metadata(target_dir / f"{duration}.mp3")

        assert metadata["format"]["format_name"] == "mp3"
        assert len(metadata["streams"]) == 1
        assert metadata["streams"][0]["codec_name"] == "mp3"
        assert (
            duration <= float(metadata["format"]["duration"]) <= duration + 0.1
        )

    assert text_file.read_text() == (target_dir / "other.txt").read_text()


def test_dry_run():
    source_dir = TMP / "source"
    source_dir.mkdir()
    target_dir = TMP / "target"
    text_file = source_dir / "other.txt"
    text_file.write_text("test file")

    config_path = write_config(source_dir, target_dir)

    proc = subprocess.run(
        ["harmonize", "--config", str(config_path), "--dry-run"],
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE,
        check=True,
    )
    assert proc.stdout == b""
    assert "Would copy" in proc.stderr.decode()
    assert not (target_dir / "other.txt").exists()


def test_legacy_copies_other_file_type():
    source_dir = TMP / "source"
    source_dir.mkdir()
    target_dir = TMP / "target"
    text_file = source_dir / "other.txt"
    text_file.write_text("test file")

    proc = subprocess.run(
        ["harmonize", str(source_dir), str(target_dir)],
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE,
        check=True,
    )
    assert proc.stdout == b""
    assert text_file.read_text() == (target_dir / "other.txt").read_text()


def test_legacy_transcodes_flac_to_mp3():
    source_dir = TMP / "source"
    source_dir.mkdir()
    target_dir = TMP / "target"
    helpers.ffmpeg.generate_silence(1, source_dir / "audio.flac")

    proc = subprocess.run(
        ["harmonize", str(source_dir), str(target_dir)],
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE,
        check=True,
    )
    assert proc.stdout == b""

    metadata = helpers.ffprobe.get_metadata(target_dir / "audio.mp3")
    assert metadata["format"]["format_name"] == "mp3"
    assert len(metadata["streams"]) == 1
    assert metadata["streams"][0]["codec_name"] == "mp3"
    assert 1 <= float(metadata["format"]["duration"]) <= 1.1


def test_legacy_transcodes_flac_to_opus():
    source_dir = TMP / "source"
    source_dir.mkdir()
    target_dir = TMP / "target"
    helpers.ffmpeg.generate_silence(1, source_dir / "audio.flac")

    proc = subprocess.run(
        ["harmonize", "--codec", "opus", str(source_dir), str(target_dir)],
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE,
        check=True,
    )
    assert proc.stdout == b""

    metadata = helpers.ffprobe.get_metadata(target_dir / "audio.opus")
    assert metadata["format"]["format_name"] == "ogg"
    assert len(metadata["streams"]) == 1
    assert metadata["streams"][0]["codec_name"] == "opus"
    assert 1 <= float(metadata["format"]["duration"]) <= 1.1
