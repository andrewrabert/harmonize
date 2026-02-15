import asyncio
import fnmatch
import logging
import os
import pathlib
import shutil

from . import converter as converter_mod

LOGGER = logging.getLogger("harmonize")


class AsyncExecutor:
    def __init__(self, max_pending):
        self._max_pending = max_pending
        self._queued = []
        self._pending = set()

    def submit(self, func, *args, **kwargs):
        self._queued.append((func, args, kwargs))
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            pass
        else:
            self._fill()

    async def as_completed(self):
        while self._queued or self._pending:
            self._fill()
            done, self._pending = await asyncio.wait(
                self._pending, return_when=asyncio.FIRST_COMPLETED
            )
            for result in done:
                yield result

    def _fill(self):
        for _ in range(self._max_pending - len(self._pending)):
            if not self._queued:
                return
            func, args, kwargs = self._queued.pop()
            self._pending.add(asyncio.create_task(func(*args, **kwargs)))


def _matches_any(path, patterns):
    name = str(path)
    return any(fnmatch.fnmatch(name, p) for p in patterns)


def _all_files(root):
    stack = [root]
    while stack:
        for path in stack.pop().iterdir():
            if path.is_dir():
                stack.append(path)
            else:
                yield path


def build_target_path(source_path, source_base, target_base, mappings):
    rel = source_path.relative_to(source_base)
    ext = source_path.suffix.lower()
    mapping = mappings.get(ext)
    if mapping and mapping.output_ext != ext:
        rel = rel.with_suffix(mapping.output_ext)
    return target_base / rel


def copy_path_attr(source_lstat, target):
    target.chmod(source_lstat.st_mode)
    os.utime(target, (target.lstat().st_atime, source_lstat.st_mtime))


async def sync_file(source, target, config):
    """Synchronize a single source file to target."""
    try:
        source_lstat = source.lstat()
    except FileNotFoundError:
        LOGGER.warning("File disappeared: %s", source)
        return

    if target.exists() and target.lstat().st_mtime == source_lstat.st_mtime:
        return

    ext = source.suffix.lower()
    mapping = config.mappings.get(ext)

    target.parent.mkdir(parents=True, exist_ok=True)

    if mapping:
        converter = config.converters[mapping.converter]
        success = await converter_mod.convert(converter, source, target)
        if not success:
            return
    elif config.copy_unmatched:
        LOGGER.info("Copying %s", source)
        shutil.copy2(source, target)
    else:
        return

    try:
        copy_path_attr(source_lstat, target)
    except OSError as e:
        LOGGER.warning("Failed to set attributes on %s: %s", target, e)


async def sync_file_dry_run(source, target, config):
    """Log what would be done without doing it."""
    try:
        source_mtime = source.lstat().st_mtime
    except FileNotFoundError:
        LOGGER.warning("File disappeared: %s", source)
        return
    if target.exists() and target.lstat().st_mtime == source_mtime:
        return

    ext = source.suffix.lower()
    mapping = config.mappings.get(ext)

    if mapping:
        LOGGER.info("Would convert %s -> %s", source, target)
    elif config.copy_unmatched:
        LOGGER.info("Would copy %s -> %s", source, target)


def _delete_if_exists(path):
    try:
        if path.is_file():
            path.unlink()
        else:
            shutil.rmtree(path)
    except FileNotFoundError:
        pass


def sanitize(config, known_targets):
    """Remove orphaned files from target directory."""
    if not config.target.is_dir():
        return
    for root, dirs, files in os.walk(config.target):
        root_path = pathlib.Path(root)
        for name in files:
            path = root_path / name
            if path in known_targets:
                continue
            rel = str(path.relative_to(config.target))
            if _matches_any(rel, config.target_exclude):
                continue
            LOGGER.info("Deleting %s", path)
            _delete_if_exists(path)

    # Remove empty directories (bottom-up)
    for root, dirs, files in os.walk(config.target, topdown=False):
        root_path = pathlib.Path(root)
        if root_path == config.target:
            continue
        try:
            root_path.rmdir()  # only removes if empty
        except OSError:
            pass


async def run(config, dry_run=False):
    """Run the full sync operation."""
    LOGGER.info('Scanning "%s"', config.source)

    jobs = config.jobs if config.jobs > 0 else os.cpu_count()
    executor = AsyncExecutor(jobs)
    known_targets = set()
    count = 0

    for source_path in sorted(_all_files(config.source)):
        rel = str(source_path.relative_to(config.source))
        if _matches_any(rel, config.source_exclude):
            continue

        ext = source_path.suffix.lower()
        mapping = config.mappings.get(ext)

        if not mapping and not config.copy_unmatched:
            continue

        target_path = build_target_path(
            source_path, config.source, config.target, config.mappings
        )
        known_targets.add(target_path)
        count += 1

        if dry_run:
            executor.submit(
                sync_file_dry_run, source_path, target_path, config
            )
        else:
            executor.submit(sync_file, source_path, target_path, config)

    LOGGER.info("Scanned %d items", count)

    async for result in executor.as_completed():
        result.result()

    if not dry_run:
        sanitize(config, known_targets)

    LOGGER.info("Processing complete")
