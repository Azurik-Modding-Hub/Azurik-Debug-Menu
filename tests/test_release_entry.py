"""Public build integration; no retail data is stored in these fixtures."""
import json
import os
from pathlib import Path
import sys

import pytest

import patcher
from freecam import iso, laboratory


def test_public_default_patcher_loads_bundled_native_menu_catalogue(monkeypatch):
    calls = []

    def native_menu(source, catalogue):
        calls.append((source, catalogue))
        return b'new native menu', {'version': laboratory.VERSION}

    monkeypatch.setattr(iso, 'patch_laboratory_xbe', native_menu)
    assert iso.patch_xbe(b'synthetic original') == (
        b'new native menu', {'version': laboratory.VERSION})
    source, catalogue = calls[0]
    assert source == b'synthetic original'
    assert [group['label'] for group in catalogue] == ['Text boxes', 'Oracles']
    assert patcher.VERSION == laboratory.VERSION


def test_xbe_builder_supports_explicit_composed_patcher(tmp_path, monkeypatch):
    source, output = tmp_path / 'original.xbe', tmp_path / 'patched.xbe'
    source.write_bytes(b'synthetic original')
    monkeypatch.setattr(iso, 'patch_xbe', lambda _: pytest.fail('Explicit patcher must be used'))
    report = iso.build_xbe(source, output,
        executable_patcher=lambda body: (body + b'custom extension', {'composed': True}))
    assert source.read_bytes() == b'synthetic original'
    assert output.read_bytes() == b'synthetic originalcustom extension'
    assert report == {'composed': True}


def test_windows_spec_bundles_names_only_catalogue():
    """Execute the build declaration with lightweight stand-ins for PyInstaller."""
    root = Path(__file__).resolve().parents[1]
    calls = {}

    class Analysis:
        def __init__(self, scripts, **options):
            calls.update(scripts=scripts, **options)
            self.pure = self.scripts = self.binaries = self.datas = []

    scope = dict(Analysis=Analysis, PYZ=lambda _: None, EXE=lambda *a, **kw: None)
    exec(compile((root / 'Azurik Freecam Patcher.spec').read_text('utf-8'),
                 'Azurik Freecam Patcher.spec', 'exec'), scope)
    assert calls['scripts'] == ['patcher.py']
    assert ('freecam/laboratory-catalogue.json', 'freecam') in calls['datas']
    for source, _ in calls['datas']:
        assert (root / source).is_file()
    catalogue = json.loads((root / 'freecam/laboratory-catalogue.json').read_text('utf-8'))
    assert isinstance(catalogue, list) and catalogue


def test_public_cli_installs_current_native_menu_instead_of_legacy_freecam(tmp_path, monkeypatch, capsys):
    original = os.environ.get('AZURIK_XBE')
    if not original:
        pytest.skip('Optional native release audit; provide your own original EU XBE.')
    source, output = tmp_path / 'original.xbe', tmp_path / 'release.xbe'
    source.write_bytes(Path(original).read_bytes())
    monkeypatch.setattr(sys, 'argv', ['patcher.py', '--input', str(source), '--output', str(output)])
    patcher.main()
    result = json.loads(capsys.readouterr().out)
    report = result['report']
    assert report['version'] == laboratory.VERSION
    assert report['activation']['reuseRetainedMenu']
    assert report['activation']['sequenceWindowSeconds'] == 1.0
    assert report['activation']['menuLanguage'] == 'English'
    assert not report['playerCheatButtonsEnabled']
    assert not report['animationPreview']
    assert report['keyInventoryCapacity'] == 5
    assert [group['label'] for group in report['catalog']] == ['Text boxes', 'Oracles']
    assert b'DBGLAB01' in output.read_bytes()
    assert ('Debug Menu - ' + laboratory.VERSION).encode('ascii') in output.read_bytes()
    assert source.read_bytes() == Path(original).read_bytes()
