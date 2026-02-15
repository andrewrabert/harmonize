import argparse
import asyncio
import importlib.metadata
import logging
import os
import pathlib
import sys

from . import config as config_mod
from . import sync

LOGGER = logging.getLogger("harmonize")

_CODECS = ("mp3", "opus")

try:
    VERSION = importlib.metadata.version("harmonize")
except importlib.metadata.PackageNotFoundError:
    VERSION = "unknown"


def _build_legacy_config(args, encoder_options):
    transcode_base = [sys.executable, "-m", "harmonize.transcode"]
    codec_commands = {
        "mp3": transcode_base
        + ["mp3", "{input}", "{output}"]
        + encoder_options,
        "opus": transcode_base
        + ["opus", "{input}", "{output}"]
        + encoder_options,
    }
    codec_ext = {
        "mp3": ".mp3",
        "opus": ".opus",
    }
    return config_mod.Config(
        source=args.source,
        target=args.target,
        copy_unmatched=True,
        source_exclude=args.exclude or [],
        target_exclude=[],
        jobs=args.jobs if args.jobs is not None else os.cpu_count(),
        converters={
            "transcode": config_mod.Converter(
                name="transcode",
                command=codec_commands[args.codec],
            ),
        },
        mappings={
            ".flac": config_mod.Mapping(
                input_ext=".flac",
                converter="transcode",
                output_ext=codec_ext[args.codec],
            ),
        },
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=pathlib.Path, help=argparse.SUPPRESS)
    parser.add_argument("--stdin", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument(
        "--codec",
        default="mp3",
        choices=_CODECS,
        help="codec to output as",
    )
    parser.add_argument(
        "-n",
        dest="jobs",
        type=int,
        default=None,
        help="number of parallel jobs",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="suppress informational output",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    parser.add_argument("--version", action="version", version=VERSION)
    parser.add_argument(
        "--exclude",
        metavar="PATTERN",
        action="append",
        help="ignore files matching this pattern",
    )
    parser.add_argument(
        "source", type=pathlib.Path, nargs="?", help="source directory"
    )
    parser.add_argument(
        "target", type=pathlib.Path, nargs="?", help="target directory"
    )

    args, encoder_options = parser.parse_known_args()

    logging.basicConfig(
        format="%(message)s",
        level=logging.WARNING if args.quiet else logging.INFO,
    )

    if args.stdin:
        if encoder_options:
            parser.error("unexpected arguments in config mode")
        cfg = config_mod.load_bytes(sys.stdin.buffer.read())
        if args.jobs is not None:
            cfg.jobs = args.jobs
    elif args.config:
        if encoder_options:
            parser.error("unexpected arguments in config mode")
        cfg = config_mod.load(args.config)
        if args.jobs is not None:
            cfg.jobs = args.jobs
    elif args.source and args.target:
        cfg = _build_legacy_config(args, encoder_options)
    else:
        parser.error(
            "either --config or source and target arguments are required"
        )

    asyncio.run(sync.run(cfg, dry_run=args.dry_run))


if __name__ == "__main__":
    main()
