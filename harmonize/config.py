import dataclasses
import pathlib
import tomllib

from .substitute import validate_template

ALLOWED_VARIABLES = {"input", "output", "stem", "ext"}


class ConfigError(Exception):
    pass


@dataclasses.dataclass
class Converter:
    name: str
    command: list[str]


@dataclasses.dataclass
class Mapping:
    input_ext: str
    converter: str
    output_ext: str


@dataclasses.dataclass
class Config:
    source: pathlib.Path
    target: pathlib.Path
    copy_unmatched: bool
    source_exclude: list[str]
    target_exclude: list[str]
    jobs: int
    converters: dict[str, Converter]
    mappings: dict[str, Mapping]


def load(path):
    """Load and validate a harmonize config from a TOML file.

    :param pathlib.Path path: Path to the TOML config file
    :returns: Validated Config
    :raises ConfigError: On invalid config
    """
    try:
        with open(path, "rb") as f:
            data = tomllib.load(f)
    except FileNotFoundError:
        raise ConfigError(f"Config file not found: {path}")
    except tomllib.TOMLDecodeError as e:
        raise ConfigError(f"Invalid TOML in {path}: {e}")
    return _parse(data)


def load_bytes(raw):
    """Load and validate a harmonize config from raw TOML bytes.

    :param bytes raw: Raw TOML content
    :returns: Validated Config
    :raises ConfigError: On invalid config
    """
    try:
        data = tomllib.loads(raw.decode())
    except tomllib.TOMLDecodeError as e:
        raise ConfigError(f"Invalid TOML: {e}")
    return _parse(data)


def _parse(data):
    harmonize = data.get("harmonize", {})

    source = harmonize.get("source")
    if source is None:
        raise ConfigError("Missing required field: harmonize.source")
    source = pathlib.Path(source)

    target = harmonize.get("target")
    if target is None:
        raise ConfigError("Missing required field: harmonize.target")
    target = pathlib.Path(target)

    if not source.is_dir():
        raise ConfigError(f"Source directory does not exist: {source}")

    if target.exists() and not target.is_dir():
        raise ConfigError(
            f"Target path exists but is not a directory: {target}"
        )

    copy_unmatched = harmonize.get("copy_unmatched", True)
    source_exclude = harmonize.get("source_exclude", [])
    target_exclude = harmonize.get("target_exclude", [])
    jobs = harmonize.get("jobs", 0)

    converters = {}
    for name, conv_data in data.get("converters", {}).items():
        command = conv_data.get("command")
        if command is None:
            raise ConfigError(
                f"Missing required field: converters.{name}.command"
            )
        if not isinstance(command, list) or not command:
            raise ConfigError(
                f"converters.{name}.command must be a non-empty list"
            )
        try:
            validate_template(command, ALLOWED_VARIABLES)
        except Exception as e:
            raise ConfigError(
                f"Invalid command template for converter {name}: {e}"
            )
        converters[name] = Converter(name=name, command=command)

    mappings = {}
    for ext, map_data in data.get("mappings", {}).items():
        if not ext.startswith("."):
            ext = f".{ext}"
        ext = ext.lower()

        converter_name = map_data.get("converter")
        if converter_name is None:
            raise ConfigError(
                f"Missing required field: mappings.{ext}.converter"
            )
        if converter_name not in converters:
            raise ConfigError(
                f"Mapping {ext} references undefined converter: {converter_name}"
            )

        output_ext = map_data.get("output_ext")
        if output_ext is None:
            output_ext = ext
        elif not output_ext.startswith("."):
            output_ext = f".{output_ext}"
        output_ext = output_ext.lower()

        mappings[ext] = Mapping(
            input_ext=ext,
            converter=converter_name,
            output_ext=output_ext,
        )

    return Config(
        source=source,
        target=target,
        copy_unmatched=copy_unmatched,
        source_exclude=source_exclude,
        target_exclude=target_exclude,
        jobs=jobs,
        converters=converters,
        mappings=mappings,
    )
