"""Replace just the two illustration textures in an existing Korean CPK.

Usage: python tools/rebuild_graphics.py existing.cpk --out updated.cpk
The source is never overwritten; text and font data remain byte-identical.
"""
import argparse
from pathlib import Path

import numpy as np
from PIL import Image

from cpk_lib import open_cpk, extract, rebuild_cpk
from dat_lib import read_dat, write_dat
from wtb_lib import encode_into

ROOT = Path(__file__).resolve().parent.parent
TARGETS = [('ui_msg_firsttime.dat', 'msg_firsttime', 0),
           ('ui_credit.dat', 'credit', 3)]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('source', type=Path)
    ap.add_argument('--out', required=True, type=Path)
    args = ap.parse_args()
    if args.source.resolve() == args.out.resolve():
        ap.error('Source and output must be different files.')
    repl = {}
    f, header, toc = open_cpk(args.source)
    try:
        for dat, base, index in TARGETS:
            row = next(r for r in toc if r['DirName'] == 'ui' and r['FileName'] == dat)
            original = extract(f, header, row)
            entries = {e['name']: e['data'] for e in read_dat(original)}
            p = ROOT / 'translation/images_ko' / dat / f'{base}_{index:03d}.png'
            with Image.open(p) as image:
                pixels = np.array(image.convert('RGBA'))
            name = base + '.wtp'
            texture = encode_into(entries[base + '.wta'], entries[name], index, pixels)
            assert len(texture) == len(entries[name])
            updated = write_dat(original, {name: texture})
            check = {e['name']: e['data'] for e in read_dat(updated)}
            assert check.keys() == entries.keys()
            assert all(check[k] == (texture if k == name else v) for k, v in entries.items())
            repl['ui/' + dat] = updated
    finally:
        f.close()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.out.with_name(args.out.name + '.graphics.tmp')
    if temporary.exists():
        raise FileExistsError(temporary)
    rebuild_cpk(args.source, temporary, repl)
    temporary.replace(args.out)
    print('Updated only the two illustration textures:', args.out)


if __name__ == '__main__':
    main()
