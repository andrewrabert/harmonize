import argparse
import asyncio
import logging
import os
import pathlib
import sys

import mutagen
import mutagen.mp3

LOGGER = logging.getLogger("harmonize")

_ENCODERS = {
    "mp3": "lame",
    "opus": "opusenc",
}


class flac:
    @staticmethod
    async def decode(path):
        read_pipe, write_pipe = os.pipe()
        proc = await asyncio.create_subprocess_exec(
            "flac",
            "-csd",
            str(path),
            stdout=write_pipe,
            stderr=asyncio.subprocess.PIPE,
        )
        os.close(write_pipe)
        return proc, read_pipe


class lame:
    @staticmethod
    async def encode(stdin_pipe, target, options=()):
        proc = await asyncio.create_subprocess_exec(
            "lame",
            "--quiet",
            *options,
            "-",
            str(target),
            stdin=stdin_pipe,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        os.close(stdin_pipe)
        await proc.wait()
        return proc


class opusenc:
    @staticmethod
    async def encode(stdin_pipe, target, options=()):
        proc = await asyncio.create_subprocess_exec(
            "opusenc",
            "--quiet",
            *options,
            "-",
            str(target),
            stdin=stdin_pipe,
        )
        os.close(stdin_pipe)
        await proc.wait()
        return proc


def copy_metadata(source, target):
    source_metadata = mutagen.File(str(source), easy=True)
    target_metadata = mutagen.File(str(target), easy=True)
    if target_metadata is None:
        target_metadata = mutagen.mp3.EasyMP3(str(target))
    for key, value in source_metadata.items():
        try:
            target_metadata[key] = value
        except KeyError:
            LOGGER.debug('Cannot set tag "%s" for %s', key, target)
    target_metadata.save()


async def transcode(encoder_cls, input_path, output_path, options=()):
    decoder_proc, read_pipe = await flac.decode(input_path)
    encoder_proc = await encoder_cls.encode(read_pipe, output_path, options)
    await decoder_proc.wait()

    stderr = await decoder_proc.stderr.read()
    if decoder_proc.returncode:
        print(
            f"flac decoder failed (exit {decoder_proc.returncode}): "
            f"{stderr.decode(errors='replace').strip()}",
            file=sys.stderr,
        )
        sys.exit(1)
    if stderr:
        LOGGER.warning('Decode "%s" "%s"', input_path, stderr)

    if encoder_proc.returncode:
        print(
            f"encoder failed (exit {encoder_proc.returncode})",
            file=sys.stderr,
        )
        sys.exit(1)

    copy_metadata(input_path, output_path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("codec", choices=_ENCODERS)
    parser.add_argument("input", type=pathlib.Path)
    parser.add_argument("output", type=pathlib.Path)
    args, extra = parser.parse_known_args()

    encoder_cls = {"mp3": lame, "opus": opusenc}[args.codec]
    asyncio.run(transcode(encoder_cls, args.input, args.output, extra))


if __name__ == "__main__":
    main()
