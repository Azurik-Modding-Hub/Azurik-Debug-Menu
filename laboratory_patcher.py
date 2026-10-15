"""Experimental native submenu patcher; never includes a game executable."""
import argparse
import json
from pathlib import Path
from freecam.iso import build_iso
from freecam.laboratory import patch_xbe


def main():
    parser=argparse.ArgumentParser(description='Azurik native Debug Laboratory — experimental EU test')
    parser.add_argument('--input',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    options=parser.parse_args()
    catalogue=json.loads((Path(__file__).resolve().parent/'freecam/laboratory-catalogue.json').read_text('utf-8'))
    report=build_iso(options.input,options.output,executable_patcher=lambda data:patch_xbe(data,catalogue))
    print(json.dumps({'iso':str(options.output.resolve()),'sha256':report['isoSha256'],'sourceUnchanged':report['sourceUnchanged'],'gameplayTested':False},indent=2))


if __name__=='__main__':main()
