import asyncio
import contextlib
import logging
import pathlib
import tempfile

from .substitute import substitute

LOGGER = logging.getLogger("harmonize")


@contextlib.contextmanager
def _temp_path(**kwargs):
    with tempfile.NamedTemporaryFile(**kwargs, delete=False) as tmp:
        temp_path = pathlib.Path(tmp.name)
        try:
            yield temp_path
        finally:
            try:
                temp_path.unlink()
            except FileNotFoundError:
                pass


async def convert(converter, input_path, output_path):
    """Run a converter command on input_path, writing to output_path atomically.

    :param config.Converter converter: Converter definition
    :param pathlib.Path input_path: Source file path
    :param pathlib.Path output_path: Destination file path
    :returns: True on success, False on failure
    """
    variables = {
        "input": str(input_path),
        "output": None,  # set after temp file creation
        "stem": input_path.stem,
        "ext": input_path.suffix,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with _temp_path(
        dir=output_path.parent, suffix=output_path.suffix
    ) as temp_path:
        variables["output"] = str(temp_path)
        args = substitute(converter.command, variables)

        LOGGER.info("Converting %s", input_path)
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()

        if proc.returncode != 0:
            LOGGER.warning(
                "Converter %s failed for %s (exit %d): %s",
                converter.name,
                input_path,
                proc.returncode,
                stderr.decode(errors="replace").strip(),
            )
            return False

        temp_path.replace(output_path)
    return True
