"""스타폭스 가드 한글 빌드.
  python build.py [--only ui_option.dat,ui_core.dat] [--sd E:]
translation/sfg_text.xlsx 의 '한국어 번역' 을 반영해 MCD + 글리프 atlas 재생성 -> DAT -> data000.cpk
-> build/sdcafiine/00050000101BEB00/KoreanTranslation/content/data000.cpk
"""
import argparse, glob, hashlib, json, os, re, shutil, time
import numpy as np
import openpyxl
from PIL import Image

from dat_lib import read_dat, write_dat
from mcd_lib import parse_mcd, build_mcd, text_to_words
from font_build import build_atlas
from cpk_lib import rebuild_cpk
from wtb_lib import encode_into
from text_tool import XLSX, dat_files

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
_GAME_DIR = '스타폭스 가드 [Game] [00050000101beb00]'
GAME = next((p for p in (os.path.join(ROOT, _GAME_DIR), os.path.join(ROOT, '..', _GAME_DIR))
             if os.path.exists(os.path.join(p, 'content', 'data000.cpk'))), os.path.join(ROOT, _GAME_DIR))
GAME = os.path.normpath(GAME)
BUILD = os.path.join(ROOT, 'build')
TITLE = '00050000101BEB00'
MODNAME = 'KoreanTranslation'


class _Collect(dict):
    def __missing__(self, key):
        self[key] = 0
        return 0


def load_translations():
    """번역 원본은 translation/ko/*.json ("dat|mcd|msg|para": "번역문").
    없을 때만 작업용 엑셀(translation/sfg_text.xlsx)에서 읽는다."""
    tl = {}
    for p in sorted(glob.glob(os.path.join(ROOT, 'translation', 'ko', '*.json'))):
        for k, v in json.load(open(p, encoding='utf-8')).items():
            dat, mcd, mi, pi = k.split('|')
            tl[(dat, mcd, int(mi), int(pi))] = v.replace('\r\n', '\n')
    if tl:
        return tl
    ws = openpyxl.load_workbook(XLSX).active
    for r in ws.iter_rows(min_row=2, values_only=True):
        if r[8] not in (None, ''):
            tl[(r[1], r[2], r[3], r[4])] = str(r[8]).replace('\r\n', '\n')
    return tl


def build_mcd_ko(dat, name, mcd, wta, wtp, tl):
    from text_tool import para_text
    M = parse_mcd(mcd)
    texts = {}
    n_tl = 0
    for mi, msg in enumerate(M['msgs']):
        for pi, pa in enumerate(msg['paras']):
            k = (dat, name, mi, pi)
            if k in tl:
                texts[(mi, pi)] = tl[k]; n_tl += 1
            else:
                texts[(mi, pi)] = para_text(pa, M['syms'])
    if n_tl == 0:
        return None
    # 필요한 (font, char) 수집
    need = _Collect()
    for mi, msg in enumerate(M['msgs']):
        for pi, pa in enumerate(msg['paras']):
            for line in texts[(mi, pi)].split('\n'):
                text_to_words(line, need, pa['font'])
    needed = sorted(k for k in need if isinstance(k, tuple))
    nwta, nwtp, symidx, atlas, styles = build_atlas(M, wta, wtp, needed)
    for mi, msg in enumerate(M['msgs']):
        for pi, pa in enumerate(msg['paras']):
            lines = texts[(mi, pi)].split('\n')
            old = pa['lines']
            new = []
            for li, t in enumerate(lines):
                base = old[min(li, len(old) - 1)]
                new.append(dict(words=text_to_words(t, symidx, pa['font']), a=base['a'], b=base['b']))
            pa['lines'] = new
    os.makedirs(os.path.join(BUILD, 'atlas'), exist_ok=True)
    bg = np.zeros_like(atlas); bg[..., 2] = 90; bg[..., 3] = 255
    a = atlas[..., 3:4] / 255.0; o = atlas[..., 0:1] / 255.0
    prev = (bg[..., :3] * (1 - o) * (1 - a) + 0 * o * (1 - a) + 255 * a).astype(np.uint8)
    Image.fromarray(prev).save(os.path.join(BUILD, 'atlas', name.replace('.mcd', '.png')))
    print(f'  {name}: 번역 {n_tl}문단, 글리프 {len(needed)}개, atlas {atlas.shape[1]}x{atlas.shape[0]}, '
          f'신규폰트스타일 {[(f, s.k, s.top, s.bottom) for f, s in styles.items()]}')
    return build_mcd(M), nwta, nwtp


def md5(p):
    h = hashlib.md5()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 24), b''):
            h.update(b)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--only', help='쉼표로 구분한 DAT 이름만 빌드 (예: ui_option.dat)')
    ap.add_argument('--sd', help='SD 카드 루트 (예: E:) - 지정 시 복사')
    args = ap.parse_args()
    only = set(args.only.split(',')) if args.only else None
    tl = load_translations()
    print('번역 행', len(tl))
    repl = {}
    for p in dat_files():
        dat = os.path.basename(p).split('_', 1)[1]
        if only and dat not in only:
            continue
        orig = open(p, 'rb').read()
        ents = {e['name']: e['data'] for e in read_dat(orig)}
        files = {}
        for name in ents:
            if not name.endswith('.mcd'):
                continue
            base = name[:-4]
            r = build_mcd_ko(dat, name, ents[name], ents[base + '.wta'], ents[base + '.wtp'], tl)
            if r:
                files[name], files[base + '.wta'], files[base + '.wtp'] = r
        # 이미지 교체: translation/images_ko/<dat>/<wta이름>_<번호>.png (원본과 같은 크기)
        img_dir = os.path.join(ROOT, 'translation', 'images_ko', dat)
        if os.path.isdir(img_dir):
            for fn in sorted(os.listdir(img_dir)):
                m = re.fullmatch(r'(.+)_(\d{3})\.png', fn)
                if not m:
                    continue
                base, idx = m.group(1), int(m.group(2))
                wtp = files.get(base + '.wtp', ents[base + '.wtp'])
                img = np.array(Image.open(os.path.join(img_dir, fn)).convert('RGBA'))
                files[base + '.wtp'] = encode_into(ents[base + '.wta'], wtp, idx, img)
                print(f'  이미지 {dat}/{fn}')
        if files:
            d = write_dat(orig, files)
            # 검증: 다시 읽어서 동일한지
            back = {e['name']: e['data'] for e in read_dat(d)}
            assert all(back[k] == v for k, v in files.items())
            sub = 'core' if dat == 'coreui.dat' else 'ui'
            repl[f'{sub}/{dat}'] = d
    if not repl:
        print('변경 없음'); return
    out_dir = os.path.join(BUILD, 'sdcafiine', TITLE, MODNAME, 'content')
    os.makedirs(out_dir, exist_ok=True)
    dst = os.path.join(out_dir, 'data000.cpk')
    t = time.time()
    rebuild_cpk(os.path.join(GAME, 'content', 'data000.cpk'), dst, repl)
    print(f'CPK -> {dst} ({os.path.getsize(dst):,} B, {time.time() - t:.1f}s)')
    if args.sd:
        sd_dir = os.path.join(args.sd + os.sep, 'wiiu', 'sdcafiine', TITLE, MODNAME, 'content')
        os.makedirs(sd_dir, exist_ok=True)
        shutil.copyfile(dst, os.path.join(sd_dir, 'data000.cpk'))
        ok = md5(dst) == md5(os.path.join(sd_dir, 'data000.cpk'))
        print('SD 복사', sd_dir, 'MD5 일치' if ok else 'MD5 불일치!')


if __name__ == '__main__':
    main()
