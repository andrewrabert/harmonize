# harmonize

[![PyPI Version](https://img.shields.io/pypi/v/harmonize.svg)](https://pypi.org/pypi/harmonize) [![AUR Version](https://img.shields.io/aur/version/harmonize.svg)](https://aur.archlinux.org/packages/harmonize)

Create and synchronize transcoded copies of audio folders.

* Transcodes FLAC files to MP3 or Opus with tags
* Copies everything else as-is
* Parallelized
* Additional runs synchronize changes since the initial run
* Configurable encoders

## History

My audio library is comprised of FLACs, MP3s, cover images, and various
metadata files. This is not a problem when I'm on my
desktop - wired into the same network as my server. However, my laptop and
phone use often suffers from poor connectivity and limited storage capacities.
Further, lossless audio often is a waste as my laptop and phone are used in
less-than-ideal environments and equipment. Thus, I decided to use only MP3s
on those devices.

Previously, I was solving this with a combination of [mp3fs](https://khenriks.github.io/mp3fs/) and [rsync](https://rsync.samba.org/). This
served me well for a number of years, but had a few drawbacks for my uses.

* **Only MP3** - Cannot experiment with formats like Opus without implementing
  support in mp3fs's C codebase.
* **Only CBR MP3** - LAME's V0 often is indistinguishable from 320 CBR while
  reducing the file size by ~15%.
* **Uses FUSE** - Makes containerization and portability more complicated.
* **Not Parallelized** - On a system with eight logical cores and competent
  disk speeds, encoding one file at a time is a gross inefficiency.

Harmonize transcodes to LAME V0, has no dependency on FUSE, and supports
parallel copying and transcoding. While it currently only transcodes to MP3,
it's written in Python. This is far more accessible to modification for a
Pythonista like myself.

## Installation

* [Arch Linux](https://aur.archlinux.org/packages/harmonize/)
* [PyPI](https://pypi.org/pypi/harmonize)

If installing from [PyPI](https://pypi.org/pypi/harmonize) or using the script directly, ensure the following
are installed:

* Python 3.6+
* FLAC
* LAME (when using mp3)
* opusenc (when using opus)

## Usage

```
usage: harmonize [-h] [--codec {mp3,opus}] [-n NUM_PROCESSES] [-q] [--version]
                 source target

positional arguments:
  source              Source directory
  target              Target directory

optional arguments:
  -h, --help          show this help message and exit
  --codec {mp3,opus}  codec to output as. encoder configuration may be
                      specified as additional arguments to harmonize
  -n NUM_PROCESSES    Number of processes to use
  -q, --quiet         suppress informational output
  --version           show program's version number and exit
```
