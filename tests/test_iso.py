"""Bounded synthetic XDVDFS fixtures; no commercial game binaries are used."""
import hashlib
import json
from pathlib import Path
import struct
from types import SimpleNamespace

import pytest

from freecam import iso


def entry(name, sector, size, *, left=0, right=0, directory=False):
    name = name.encode("ascii")
    return struct.pack("<HHIIBB", left, right, sector, size, 16 if directory else 0, len(name)) + name


def make_image(path, *, partition=0, root_name="default.xbe"):
    sector = iso.SECTOR
    executable = b"XBEH synthetic executable for isolated filesystem tests"
    model = bytes(range(256)) + b"MODEL"
    texture = b"synthetic texture pixels\0" * 71
    body = bytearray(partition + 41 * sector + 19)
    descriptor = bytearray(sector)
    descriptor[:20] = descriptor[-20:] = iso.MAGIC
    struct.pack_into("<II", descriptor, 20, 34, sector)
    body[partition + 32 * sector:partition + 33 * sector] = descriptor
    root = bytearray(b"\xff" * sector)
    default = entry(root_name, 36, len(executable), left=16)
    root[:len(default)] = default
    assets = entry("Assets", 35, sector, directory=True)
    root[64:64 + len(assets)] = assets
    nested = bytearray(b"\xff" * sector)
    mesh = entry("model.bin", 37, len(model), right=16)
    nested[:len(mesh)] = mesh
    image = entry("texture.png", 38, len(texture))
    nested[64:64 + len(image)] = image
    for start, content in [(34, root), (35, nested), (36, executable), (37, model), (38, texture)]:
        at = partition + start * sector
        body[at:at + len(content)] = content
    path.write_bytes(body)
    return {"source": path, "body": bytes(body), "executable": executable,
            "assets": {"Assets/model.bin": model, "Assets/texture.png": texture},
            "descriptor": partition + 32 * sector, "root": partition + 34 * sector,
            "nested": partition + 35 * sector, "partition": partition}


@pytest.fixture
def image(tmp_path):
    return make_image(tmp_path / "source.iso")


@pytest.fixture
def replacement(image, monkeypatch):
    patched = image["executable"] + b"PRIVATE-DEBUG-SECTION" + b"\x5a" * 3000

    def patch(source):
        assert source == image["executable"]
        return patched, {"patch": "synthetic-test", "imageTestedInGame": False}

    monkeypatch.setattr(iso, "patch_xbe", patch)
    return patched


def sha(body):
    return hashlib.sha256(body).hexdigest()


@pytest.mark.parametrize("partition", [0, 4 * iso.SECTOR])
def test_index_reads_nested_assets_and_nonzero_partition(tmp_path, monkeypatch, partition):
    image = make_image(tmp_path / "partition.iso", partition=partition)
    monkeypatch.setattr(iso, "PARTITIONS", (0, 4 * iso.SECTOR))
    actual_partition, entries, executable = iso.index_image(image["source"])
    assert actual_partition == partition
    assert {e["path"] for e in entries} == {"default.xbe", "Assets", *image["assets"]}
    assert executable["offset"] == partition + 36 * iso.SECTOR
    for record in entries:
        if record["path"] in image["assets"]:
            assert image["body"][record["offset"]:record["offset"] + record["size"]] == image["assets"][record["path"]]


@pytest.mark.parametrize("chunk", [iso.CHUNK, 7])
def test_relocation_preserves_every_original_byte_except_eight_directory_bytes(image, replacement, tmp_path, monkeypatch, chunk):
    monkeypatch.setattr(iso, "CHUNK", chunk)  # Includes directory edits spanning copy chunks.
    destination = tmp_path / "new.iso"
    progress = []
    report = iso.build_iso(image["source"], destination, lambda value, stage: progress.append((value, stage)))
    assert image["source"].read_bytes() == image["body"]
    actual = destination.read_bytes()
    appended = (len(image["body"]) + iso.SECTOR - 1) // iso.SECTOR * iso.SECTOR
    expected_prefix = bytearray(image["body"])
    struct.pack_into("<II", expected_prefix, image["root"] + 4, appended // iso.SECTOR, len(replacement))
    assert actual[:len(expected_prefix)] == expected_prefix
    assert actual[len(expected_prefix):appended] == b"\0" * (appended - len(expected_prefix))
    assert actual[appended:appended + len(replacement)] == replacement
    assert actual[appended + len(replacement):] == b"\0" * (-len(replacement) % iso.SECTOR)
    partition, entries, executable = iso.index_image(destination)
    assert partition == 0 and executable["offset"] == appended and executable["size"] == len(replacement)
    for record in entries:
        if record["path"] in image["assets"]:
            assert actual[record["offset"]:record["offset"] + record["size"]] == image["assets"][record["path"]]
    assert report["inputSha256"] == sha(image["body"])
    assert report["isoSha256"] == sha(actual)
    assert report["otherFilesByteIdentical"] and report["sourceUnchanged"]
    assert not report["imageTestedInGame"]
    assert json.loads(destination.with_suffix(".iso.report.json").read_text("utf-8")) == report
    assert progress and progress[-1][0] == 100
    assert all(a[0] <= b[0] for a, b in zip(progress, progress[1:]))


def test_relocation_uses_partition_relative_new_sector(tmp_path, monkeypatch):
    partition = 4 * iso.SECTOR
    image = make_image(tmp_path / "partition.iso", partition=partition)
    monkeypatch.setattr(iso, "PARTITIONS", (0, partition))
    replacement = image["executable"] + b"added synthetic section"
    monkeypatch.setattr(iso, "patch_xbe", lambda _: (replacement, {}))
    destination = tmp_path / "new.iso"
    report = iso.build_iso(image["source"], destination)
    actual_partition, _, executable = iso.index_image(destination)
    assert actual_partition == partition
    assert executable["offset"] == report["executableOffset"]
    assert executable["sector"] * iso.SECTOR + partition == executable["offset"]
    assert image["source"].read_bytes() == image["body"]


@pytest.mark.parametrize("conflict", ["source", "destination", "report"])
def test_existing_source_output_and_reports_are_never_changed(image, tmp_path, monkeypatch, conflict):
    destination = image["source"] if conflict == "source" else tmp_path / "new.iso"
    protected = destination if conflict != "report" else destination.with_suffix(".iso.report.json")
    if conflict != "source":
        protected.write_bytes(b"do not overwrite this user's file")
    original = protected.read_bytes()
    monkeypatch.setattr(iso, "patch_xbe", lambda _: pytest.fail("Reject existing output before patching"))
    with pytest.raises(ValueError, match="new output"):
        iso.build_iso(image["source"], destination)
    assert protected.read_bytes() == original
    assert image["source"].read_bytes() == image["body"]


def test_exclusive_create_race_never_deletes_the_file_that_won(image, tmp_path, monkeypatch):
    destination = tmp_path / "new.iso"
    sentinel = b"a different process created this file first"

    def patch(_):
        destination.write_bytes(sentinel)
        return image["executable"] + b"new section", {}

    monkeypatch.setattr(iso, "patch_xbe", patch)
    with pytest.raises(FileExistsError):
        iso.build_iso(image["source"], destination)
    assert destination.read_bytes() == sentinel
    assert image["source"].read_bytes() == image["body"]


def test_report_creation_race_preserves_external_report_and_removes_own_failed_iso(image, tmp_path, monkeypatch):
    destination = tmp_path / "new.iso"
    report_path = destination.with_suffix(".iso.report.json")
    sentinel = b"a report from another operation"

    def patch(_):
        report_path.write_bytes(sentinel)
        return image["executable"] + b"new section", {}

    monkeypatch.setattr(iso, "patch_xbe", patch)
    with pytest.raises(FileExistsError):
        iso.build_iso(image["source"], destination)
    assert report_path.read_bytes() == sentinel
    assert not destination.exists()
    assert image["source"].read_bytes() == image["body"]


def test_callback_failure_removes_only_new_output(image, replacement, tmp_path):
    destination = tmp_path / "new.iso"

    def fail(*_):
        raise RuntimeError("synthetic progress failure")

    with pytest.raises(RuntimeError, match="progress failure"):
        iso.build_iso(image["source"], destination, fail)
    assert not destination.exists() and not destination.with_suffix(".iso.report.json").exists()
    assert image["source"].read_bytes() == image["body"]


@pytest.mark.parametrize("corruption", ["asset", "appended_xbe", "padding", "tail", "extra_byte"])
def test_full_readback_detects_changed_asset_or_appended_bytes(image, replacement, tmp_path, monkeypatch, corruption):
    destination = tmp_path / "new.iso"
    original_index = iso.index_image

    def corrupt_then_index(path):
        if Path(path) == destination:
            data = bytearray(destination.read_bytes())
            appended = (len(image["body"]) + iso.SECTOR - 1) // iso.SECTOR * iso.SECTOR
            at = {"asset": 37 * iso.SECTOR + 20, "appended_xbe": appended + 20,
                  "padding": len(image["body"]), "tail": appended + len(replacement)}.get(corruption)
            if at is None:
                data.append(7)
            else:
                data[at] ^= 1
            destination.write_bytes(data)
        return original_index(path)

    monkeypatch.setattr(iso, "index_image", corrupt_then_index)
    with pytest.raises(ValueError, match="readback"):
        iso.build_iso(image["source"], destination)
    assert not destination.exists()
    assert image["source"].read_bytes() == image["body"]


def test_insufficient_space_creates_nothing(image, replacement, tmp_path, monkeypatch):
    monkeypatch.setattr(iso.shutil, "disk_usage", lambda _: SimpleNamespace(free=1))
    destination = tmp_path / "new.iso"
    with pytest.raises(ValueError, match="disk space"):
        iso.build_iso(image["source"], destination)
    assert not destination.exists() and image["source"].read_bytes() == image["body"]


@pytest.mark.parametrize("damage", ["small", "descriptor", "root_extent", "directory_cycle", "node_cycle", "link_extent", "overlap", "name_truncated", "file_extent", "duplicate", "padding_link", "unsafe_name", "missing_default"])
def test_malformed_images_fail_without_creating_output(image, tmp_path, monkeypatch, damage):
    data = bytearray(image["body"])
    root, descriptor = image["root"], image["descriptor"]
    if damage == "small":
        data = data[:100]
    elif damage == "descriptor":
        data[descriptor] ^= 1
    elif damage == "root_extent":
        struct.pack_into("<I", data, descriptor + 20, 9000)
    elif damage == "directory_cycle":
        struct.pack_into("<I", data, root + 64 + 4, 34)
    elif damage == "node_cycle":
        struct.pack_into("<H", data, root + 64, 16)
    elif damage == "link_extent":
        struct.pack_into("<H", data, root, 0xfffe)
    elif damage == "overlap":
        struct.pack_into("<H", data, root, 4)
    elif damage == "name_truncated":
        struct.pack_into("<I", data, descriptor + 24, 14)
    elif damage == "file_extent":
        struct.pack_into("<I", data, root + 4, 9000)
    elif damage == "duplicate":
        data[root + 64 + 13] = 11
        data[root + 64 + 14:root + 64 + 25] = b"DEFAULT.XBE"
    elif damage == "padding_link":
        data[root + 64:root + 66] = b"\xff\xff"
    elif damage == "unsafe_name":
        data[root + 14:root + 25] = b"../file.xbe"
    elif damage == "missing_default":
        data[root + 14:root + 25] = b"another.xbe"
    image["source"].write_bytes(data)
    before = bytes(data)
    monkeypatch.setattr(iso, "patch_xbe", lambda _: pytest.fail("Malformed filesystems must fail before patching"))
    destination = tmp_path / "new.iso"
    with pytest.raises(ValueError):
        iso.build_iso(image["source"], destination)
    assert image["source"].read_bytes() == before and not destination.exists()


def test_foreign_xbe_is_rejected_before_output_creation(image, tmp_path):
    destination = tmp_path / "new.iso"
    with pytest.raises(ValueError, match="Unsupported executable"):
        iso.build_iso(image["source"], destination)
    assert not destination.exists() and image["source"].read_bytes() == image["body"]


def test_xbe_export_preserves_input_and_writes_new_output_and_report(tmp_path, monkeypatch):
    source, destination = tmp_path / "source.xbe", tmp_path / "new.xbe"
    source.write_bytes(b"synthetic XBE input")
    monkeypatch.setattr(iso, "patch_xbe", lambda body: (body + b"private section", {"patch": "synthetic"}))
    report = iso.build_xbe(source, destination)
    assert source.read_bytes() == b"synthetic XBE input"
    assert destination.read_bytes() == source.read_bytes() + b"private section"
    assert json.loads(destination.with_suffix(".xbe.report.json").read_text("utf-8")) == report


@pytest.mark.parametrize("kind", ["input", "output", "report"])
def test_xbe_export_rejects_existing_files_before_patching(tmp_path, monkeypatch, kind):
    source, destination = tmp_path / "source.xbe", tmp_path / "new.xbe"
    source.write_bytes(b"original input")
    if kind == "input":
        destination = source
    protected = destination.with_suffix(".xbe.report.json") if kind == "report" else destination
    if kind != "input":
        protected.write_bytes(b"existing user file")
    before = protected.read_bytes()
    monkeypatch.setattr(iso, "patch_xbe", lambda _: pytest.fail("Existing files rejected before patching"))
    with pytest.raises(ValueError, match="new output"):
        iso.build_xbe(source, destination)
    assert protected.read_bytes() == before and source.read_bytes() == b"original input"
