import asyncio


async def get_resolution(path):
    resolution = {
        'width': None,
        'height': None,
    }
    resolution = []
    for dimension in 'width', 'height':
        proc = await asyncio.create_subprocess_exec(
            'vipsheader',
            '-f', dimension,
            '--', path,
            stdout=asyncio.subprocess.PIPE)
        stdout, _ = await proc.communicate()
        if proc.returncode:
            raise ProcessError(proc)
        resolution.append(int(stdout))
    return tuple(resolution)


async def generate_thumbnail(source, target, res):
    proc = await asyncio.create_subprocess_exec(
        'vips', 'thumbnail',
        source, target,
        str(res))
    await proc.wait()
    if proc.returncode:
        raise ProcessError(proc)


async def optimize_jpeg(path):
    proc = await asyncio.create_subprocess_exec(
        'jpegoptim', '--quiet', '--all-progressive',
        '--force', '--strip-all', '--', path)
    await proc.wait()
    if proc.returncode:
        raise ProcessError(proc)


class ProcessError(Exception):
    def __init__(self, process, message=None):
        self.process = process
        self.message = message

    def __str__(self):
        proc = self.process

        text = f'exit {proc.returncode}'
        if self.message is not None:
            text = f'{text} - {self.message}'

        try:
            args = proc._transport._extra['subprocess'].args
        except (AttributeError, KeyError):
            pass
        else:
            text = f'{text}: {args}'
        return text


async def transcode_image(source, target):
    max_res = max(await get_resolution(source))
    thumb_res = 1000 if max_res >= 1000 else max_res
    await generate_thumbnail(source, target, thumb_res)
    await optimize_jpeg(target)
