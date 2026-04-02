# harmonize

Create and synchronize transcoded copies of audio folders.

* Transcodes FLAC files to MP3 or Opus
* Copies everything else as-is
* Parallelized
* Additional runs synchronize changes since the initial run
* Configurable converters via TOML config (ffmpeg, ImageMagick, etc.)

## Installation

* [Arch Linux](https://aur.archlinux.org/packages/harmonize/)

Or build from source:

```
cargo install --path .
```

Requires [ffmpeg](https://ffmpeg.org/) for audio conversion.

## Usage

Create a TOML config file (see `harmonize.toml.example`):

```toml
[harmonize]
source = "/media/source"
target = "/media/target"

[converters.opus]
command = ["ffmpeg", "-y", "-i", "{input}", "-c:a", "libopus", "-b:a", "128k", "{output}"]

[mappings]
".flac" = { converter = "opus", output_ext = ".opus" }
```

Then run:

```
harmonize --config harmonize.toml
```

### Options

```
      --config <CONFIG>                Config file path
      --stdin                          Read config from stdin
  -n <JOBS>                            Number of parallel jobs
  -q, --quiet                          Suppress informational output
  -v, --verbose                        Enable debug output
      --dry-run                        Show what would be done without doing it
      --modify-window <MODIFY_WINDOW>  Compare mod-times with reduced accuracy (seconds). -1 = nanoseconds [default: 0]
  -h, --help                           Print help
  -V, --version                        Print version
```
