"""Create a new XDVDFS image, preserving every existing asset extent."""
from pathlib import Path
import hashlib
import json
import os
import shutil
import struct
from .patch import patch_xbe

SECTOR = 2048
MAGIC = b'MICROSOFT*XBOX*MEDIA'
PARTITIONS = (0, 0xFD90000, 0x2080000)
CHUNK = 4 * 1024 * 1024


def index_image(path):
    path = Path(path)
    size = path.stat().st_size
    if not 33 * SECTOR <= size <= 16 * 1024**3:
        raise ValueError('Image size is outside supported Xbox ISO limits')
    entries = []
    with path.open('rb') as stream:
        partition = None
        for at in PARTITIONS:
            stream.seek(at + 0x10000)
            descriptor = stream.read(SECTOR)
            if descriptor[:20] == MAGIC and descriptor[-20:] == MAGIC:
                partition = at
                root, length = struct.unpack_from('<II', descriptor, 20)
                break
        if partition is None:
            raise ValueError('No XDVDFS filesystem found. Choose an Xbox XISO/ISO.')
        pending, directories, tables_total = [(root, length, '', 0)], set(), 0
        while pending:
            sector, length, prefix, depth = pending.pop()
            if not length:
                continue
            at = partition + sector * SECTOR
            tables_total += length
            if (depth > 64 or length > 8 * 1024**2 or tables_total > 32 * 1024**2
                    or (sector, length) in directories or at + length > size):
                raise ValueError('Invalid, cyclic or oversized Xbox directory')
            directories.add((sector, length))
            stream.seek(at)
            table = stream.read(length)
            offsets, visited, occupied, names = [0], set(), [], set()
            while offsets:
                node = offsets.pop()
                if node in visited or node % 4 or not 0 <= node <= length - 14:
                    raise ValueError('Invalid Xbox directory link')
                visited.add(node)
                if table[node:node + 2] == b'\xff\xff':
                    if node == 0:
                        continue
                    node = (node // SECTOR + 1) * SECTOR
                    if node in visited or node > length - 14:
                        raise ValueError('Directory link points into padding')
                    visited.add(node)
                left, right, start, count, flags, name_size = struct.unpack_from('<HHIIBB', table, node)
                end = node + 14 + name_size
                if (not name_size or end > length
                        or any(node < hi and end > lo for lo, hi in occupied)):
                    raise ValueError('Overlapping or truncated directory entry')
                occupied.append((node, end))
                name = table[node + 14:end].decode('ascii')
                if (name in ('.', '..') or any(ch in name for ch in '/\\\0:')
                        or name.casefold() in names):
                    raise ValueError('Invalid or duplicate file name')
                names.add(name.casefold())
                extent = partition + start * SECTOR
                if extent + count > size:
                    raise ValueError('File extent is outside the image')
                entry = dict(path=prefix + name, sector=start, size=count,
                             offset=extent, directory=bool(flags & 16), node=at + node)
                entries.append(entry)
                if entry['directory']:
                    pending.append((start, count, entry['path'] + '/', depth + 1))
                if left:
                    offsets.append(left * 4)
                if right:
                    offsets.append(right * 4)
    executables = [e for e in entries if not e['directory'] and e['path'].casefold() == 'default.xbe']
    if len(executables) != 1:
        raise ValueError('Exactly one root default.xbe is required')
    return partition, entries, executables[0]


def build_iso(source, destination, progress=None):
    source, destination = Path(source).resolve(), Path(destination).resolve()
    report_path = destination.with_suffix(destination.suffix + '.report.json')
    if source == destination or destination.exists() or report_path.exists():
        raise ValueError('Choose a new output file; existing files are never overwritten')
    partition, entries, executable = index_image(source)
    if executable['size'] > 8 * 1024**2:
        raise ValueError('Unexpected executable size')
    with source.open('rb') as stream:
        stream.seek(executable['offset'])
        original = stream.read(executable['size'])
    replacement, report = patch_xbe(original)
    source_size = source.stat().st_size
    appended_at = (source_size + SECTOR - 1) // SECTOR * SECTOR
    directory_edit = struct.pack('<II', (appended_at - partition) // SECTOR, len(replacement))
    if shutil.disk_usage(destination.parent).free < appended_at + len(replacement) + 16 * 1024**2:
        raise ValueError('Not enough disk space for a separate test ISO')
    # Exclusive create ensures both the source and any existing destination survive.
    source_digest = hashlib.sha256()
    output_digest = hashlib.sha256()
    completed = False
    created = False
    try:
        with source.open('rb') as src, destination.open('xb') as out:
            created = True
            position = 0
            while block := src.read(CHUNK):
                source_digest.update(block)
                adjusted = bytearray(block)
                for index, value in enumerate(directory_edit):
                    absolute = executable['node'] + 4 + index
                    if position <= absolute < position + len(block):
                        adjusted[absolute - position] = value
                out.write(adjusted)
                output_digest.update(adjusted)
                position += len(block)
                if progress:
                    progress(position / source_size * 90, 'Copying original game data')
            if position != source_size:
                raise ValueError('Source image changed during copy')
            padding = b'\0' * (appended_at - position)
            tail = replacement + b'\0' * (-len(replacement) % SECTOR)
            out.write(padding)
            out.write(tail)
            output_digest.update(padding)
            output_digest.update(tail)
            out.flush()
            os.fsync(out.fileno())
        # Read the resulting directory again and compare all original asset pointers.
        actual_partition, actual_entries, actual_executable = index_image(destination)
        expected_entries = [dict(e) for e in entries]
        expected_executable = next(e for e in expected_entries if e['path'].casefold() == 'default.xbe')
        expected_executable.update(sector=(appended_at - partition) // SECTOR,
                                   size=len(replacement), offset=appended_at)
        if actual_partition != partition or actual_entries != expected_entries:
            raise ValueError('Unexpected Xbox filesystem change')
        # Verify the complete prefix and appended XBE from disk, including assets.
        verification_digest = hashlib.sha256()
        with source.open('rb') as src, destination.open('rb') as out:
            position = 0
            while block := src.read(CHUNK):
                verification_digest.update(block)
                expected = bytearray(block)
                for index, value in enumerate(directory_edit):
                    absolute = executable['node'] + 4 + index
                    if position <= absolute < position + len(block):
                        expected[absolute - position] = value
                if out.read(len(block)) != expected:
                    raise ValueError('Full-image readback differs outside executable directory entry')
                position += len(block)
                if progress:
                    progress(90 + position / source_size * 10, 'Verifying all game data')
            if (out.read(len(padding)) != padding or out.read(len(tail)) != tail
                    or out.read(1)):
                raise ValueError('Patched executable failed readback')
        if verification_digest.digest() != source_digest.digest():
            raise ValueError('Source image changed during verification')
        report.update(inputSha256=source_digest.hexdigest(), isoSha256=output_digest.hexdigest(),
                      sourceUnchanged=True, otherFilesByteIdentical=True,
                      sourceISOBytes=source_size, outputISOBytes=destination.stat().st_size,
                      executableDirectoryOffset=executable['node'] + 4,
                      executableOffset=appended_at, imageTestedInGame=False)
        with report_path.open('x', encoding='utf-8') as stream:
            stream.write(json.dumps(report, indent=2) + '\n')
        completed = True
        return report
    finally:
        if created and not completed and destination.exists():
            destination.unlink()  # Only the exclusively created single output file.


def build_xbe(source, destination):
    source, destination = Path(source).resolve(), Path(destination).resolve()
    report_path = destination.with_suffix(destination.suffix + '.report.json')
    if source == destination or destination.exists() or report_path.exists():
        raise ValueError('Choose a new output file')
    body, report = patch_xbe(source.read_bytes())
    with destination.open('xb') as stream:
        stream.write(body)
    with report_path.open('x', encoding='utf-8') as stream:
        stream.write(json.dumps(report, indent=2) + '\n')
    return report
