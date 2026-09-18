"""두 CPK의 모든 DAT에서 wta/wtp(및 wtb) 텍스처를 PNG로 덤프 -> extract/tex/<dat>/<name>_NNN.png, 목록 tex_index.tsv"""
import os, sys, struct, time, traceback
import numpy as np
from PIL import Image
from cpk_lib import open_cpk, extract
from dat_lib import read_dat
from wtb_lib import parse_wta, decode

G = '../../스타폭스 가드 [Game] [00050000101beb00]/content/'
OUT = '../extract/tex'
os.makedirs(OUT, exist_ok=True)
idx = open('../extract/tex_index.tsv', 'a', encoding='utf-8')
done = set(os.listdir(OUT))


def dump_dat(label, d):
    try:
        ents = {e['name']: e['data'] for e in read_dat(d)}
    except Exception:
        return
    for nm, data in ents.items():
        if nm.endswith('.dat') or nm.endswith('.eft') or nm.endswith('.eff'):
            if data[:4] == b'DAT\0':
                dump_dat(label + '__' + nm, data)
        if not nm.endswith('.wta'):
            continue
        wtp = ents.get(nm[:-4] + '.wtp')
        if wtp is None:
            continue
        try:
            T = parse_wta(data)
        except Exception as e:
            idx.write(f'{label}\t{nm}\t-\tWTA_ERR {e}\n'); continue
        od = os.path.join(OUT, label); os.makedirs(od, exist_ok=True)
        for i, t in enumerate(T):
            s = t['surf']
            info = f"{s['width']}x{s['height']} fmt={s['format']:#x}"
            try:
                img = decode(t, wtp)
                fn = f'{nm[:-4]}_{i:03d}.png'
                Image.fromarray(img).save(os.path.join(od, fn))
                idx.write(f'{label}\t{nm}\t{i}\t{info}\t{fn}\n')
            except Exception as e:
                idx.write(f'{label}\t{nm}\t{i}\t{info}\tFAIL {e}\n')
    idx.flush()


for n in ['data000', 'data001']:
    f, h, toc = open_cpk(G + n + '.cpk')
    for r in toc:
        label = f"{r['DirName'] or 'root'}_{r['FileName'][:-4]}"
        if label in done:
            continue
        t = time.time()
        d = extract(f, h, r)
        if d[:4] == b'DAT\0':
            dump_dat(label, d)
        print(label, round(time.time() - t, 1), flush=True)
print('END')
