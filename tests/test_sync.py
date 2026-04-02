import asyncio
import pathlib
import textwrap

import pytest

from harmonize.config import load
from harmonize.sync import run


@pytest.fixture
def tmp_dir(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    target = tmp_path / "target"
    return tmp_path


def write_config(tmp_dir, extra=""):
    source = tmp_dir / "source"
    target = tmp_dir / "target"
    toml = textwrap.dedent(f"""\
        [harmonize]
        source = "{source}"
        target = "{target}"
        {extra}
    """)
    path = tmp_dir / "harmonize.toml"
    path.write_text(toml)
    return load(path)


def test_copies_unmatched_file(tmp_dir):
    source = tmp_dir / "source"
    target = tmp_dir / "target"
    (source / "hello.txt").write_text("hello world")

    cfg = write_config(tmp_dir)
    asyncio.run(run(cfg))

    assert (target / "hello.txt").read_text() == "hello world"


def test_copy_unmatched_false_skips_file(tmp_dir):
    source = tmp_dir / "source"
    target = tmp_dir / "target"
    (source / "hello.txt").write_text("hello world")

    cfg = write_config(tmp_dir, "copy_unmatched = false")
    asyncio.run(run(cfg))

    assert not (target / "hello.txt").exists()


def test_copies_nested_directory_structure(tmp_dir):
    source = tmp_dir / "source"
    target = tmp_dir / "target"
    sub = source / "a" / "b"
    sub.mkdir(parents=True)
    (sub / "deep.txt").write_text("deep")

    cfg = write_config(tmp_dir)
    asyncio.run(run(cfg))

    assert (target / "a" / "b" / "deep.txt").read_text() == "deep"


def test_mtime_skip(tmp_dir):
    source = tmp_dir / "source"
    target = tmp_dir / "target"
    (source / "file.txt").write_text("v1")

    cfg = write_config(tmp_dir)
    asyncio.run(run(cfg))

    # Modify target content but keep mtime synced (simulating already synced)
    # Second run should not overwrite since mtime matches
    first_mtime = (target / "file.txt").stat().st_mtime
    asyncio.run(run(cfg))
    second_mtime = (target / "file.txt").stat().st_mtime
    assert first_mtime == second_mtime


def test_source_exclude(tmp_dir):
    source = tmp_dir / "source"
    target = tmp_dir / "target"
    (source / "keep.txt").write_text("keep")
    (source / "skip.log").write_text("skip")

    cfg = write_config(tmp_dir, 'source_exclude = ["*.log"]')
    asyncio.run(run(cfg))

    assert (target / "keep.txt").exists()
    assert not (target / "skip.log").exists()


def test_orphan_cleanup(tmp_dir):
    source = tmp_dir / "source"
    target = tmp_dir / "target"
    target.mkdir()
    (source / "keep.txt").write_text("keep")
    (target / "orphan.txt").write_text("orphan")

    cfg = write_config(tmp_dir)
    asyncio.run(run(cfg))

    assert (target / "keep.txt").exists()
    assert not (target / "orphan.txt").exists()


def test_target_exclude_protects_from_cleanup(tmp_dir):
    source = tmp_dir / "source"
    target = tmp_dir / "target"
    target.mkdir()
    (source / "keep.txt").write_text("keep")
    (target / "playlist.m3u").write_text("protected")

    cfg = write_config(tmp_dir, 'target_exclude = ["*.m3u"]')
    asyncio.run(run(cfg))

    assert (target / "keep.txt").exists()
    assert (target / "playlist.m3u").exists()


def test_dry_run_does_not_modify(tmp_dir):
    source = tmp_dir / "source"
    target = tmp_dir / "target"
    (source / "file.txt").write_text("content")

    cfg = write_config(tmp_dir)
    asyncio.run(run(cfg, dry_run=True))

    assert not target.exists() or not (target / "file.txt").exists()


def test_converter_changes_extension(tmp_dir):
    source = tmp_dir / "source"
    target = tmp_dir / "target"

    # Create a file and a converter that just copies (cp as converter)
    (source / "song.fake").write_text("audio data")

    toml = textwrap.dedent(f"""\
        [harmonize]
        source = "{source}"
        target = "{target}"

        [converters.copy-converter]
        command = ["cp", "{{input}}", "{{output}}"]

        [mappings]
        ".fake" = {{ converter = "copy-converter", output_ext = ".out" }}
    """)
    path = tmp_dir / "harmonize.toml"
    path.write_text(toml)
    cfg = load(path)

    asyncio.run(run(cfg))

    assert (target / "song.out").exists()
    assert (target / "song.out").read_text() == "audio data"
    assert not (target / "song.fake").exists()


def test_converter_keeps_extension_when_same(tmp_dir):
    source = tmp_dir / "source"
    target = tmp_dir / "target"

    (source / "photo.jpg").write_text("image data")

    toml = textwrap.dedent(f"""\
        [harmonize]
        source = "{source}"
        target = "{target}"

        [converters.compress]
        command = ["cp", "{{input}}", "{{output}}"]

        [mappings]
        ".jpg" = {{ converter = "compress" }}
    """)
    path = tmp_dir / "harmonize.toml"
    path.write_text(toml)
    cfg = load(path)

    asyncio.run(run(cfg))

    assert (target / "photo.jpg").exists()
    assert (target / "photo.jpg").read_text() == "image data"


def test_copies_empty_directories(tmp_dir):
    source = tmp_dir / "source"
    target = tmp_dir / "target"
    (source / "empty_dir").mkdir()
    (source / "nested" / "empty").mkdir(parents=True)

    cfg = write_config(tmp_dir)
    asyncio.run(run(cfg))

    assert (target / "empty_dir").is_dir()
    assert (target / "nested" / "empty").is_dir()


def test_empty_directories_survive_resync(tmp_dir):
    source = tmp_dir / "source"
    target = tmp_dir / "target"
    (source / "empty_dir").mkdir()
    (source / "file.txt").write_text("content")

    cfg = write_config(tmp_dir)
    asyncio.run(run(cfg))
    asyncio.run(run(cfg))

    assert (target / "empty_dir").is_dir()
    assert (target / "file.txt").exists()


def test_empty_source_directory(tmp_dir):
    cfg = write_config(tmp_dir)
    asyncio.run(run(cfg))
    # Should not error on empty source


def test_failed_converter_skips_file(tmp_dir):
    source = tmp_dir / "source"
    target = tmp_dir / "target"

    (source / "file.bad").write_text("data")

    toml = textwrap.dedent(f"""\
        [harmonize]
        source = "{source}"
        target = "{target}"

        [converters.failing]
        command = ["false"]

        [mappings]
        ".bad" = {{ converter = "failing", output_ext = ".out" }}
    """)
    path = tmp_dir / "harmonize.toml"
    path.write_text(toml)
    cfg = load(path)

    asyncio.run(run(cfg))

    assert not (target / "file.out").exists()
