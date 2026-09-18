"""빌드된 CPK에서 DAT를 다시 꺼내 MCD 메시지를 atlas 글리프로 합성한 미리보기 PNG 생성 (엔드투엔드 검증)."""
import sys, os
import numpy as np
from PIL import Image
from cpk_lib import open_cpk, extract
from dat_lib import read_dat
from mcd_lib import parse_mcd
from wtb_lib import parse_wta, decode


def render_msg(M, img, mi, scale=1.0):
    H, W = img.shape[:2]
    fonts = {f[0]: f for f in M['fonts']}
    lines_img = []
    canvas = np.zeros((900, 1400, 3), np.float32); canvas[..., 2] = 70; canvas[..., 1] = 30
    y = 10
    for pa in M['msgs'][mi]['paras']:
        for l in pa['lines']:
            x = 10; w = l['words']; i = 0
            while i < len(w) and w[i] != 0x8000:
                c, arg = w[i], w[i + 1]
                if c < 0x8000:
                    f, ch, gi = M['syms'][c]; g = M['glyphs'][gi]
                    x0, y0, x1, y1 = [int(round(v)) for v in (g[1] * W, g[2] * H, g[3] * W, g[4] * H)]
                    cell = img[y0:y1, x0:x1].astype(np.float32) / 255
                    h, cw = cell.shape[:2]
                    reg = canvas[y:y + h, x:x + cw]
                    o = cell[..., :1]; a = cell[..., 3:4]
                    reg[:] = reg * (1 - o) * (1 - a) + 0 * o * (1 - a) + 255 * a
                    x += int(g[5] + l['a']) + (arg - 0x10000 if arg & 0x8000 else arg)
                elif c == 0x8001:
                    x += int(fonts[arg][1] + l['a'])
                elif c == 0x8003:
                    canvas[y + 15:y + 45, x + 4:x + 34] = (200, 160, 0); x += 40
                i += 2
            y += int(fonts[pa['font']][2] + l['b']) if False else 60
    return canvas.astype(np.uint8)


if __name__ == '__main__':
    cpk, dat, mcd, mi, out = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4]), sys.argv[5]
    f, h, toc = open_cpk(cpk)
    r = next(r for r in toc if r['FileName'] == dat)
    ents = {e['name']: e['data'] for e in read_dat(extract(f, h, r))}
    M = parse_mcd(ents[mcd]); base = mcd[:-4]
    T = parse_wta(ents[base + '.wta']); img = decode(T[0], ents[base + '.wtp'])
    Image.fromarray(render_msg(M, img, mi)).save(out)
    print('saved', out, T[0]['surf']['width'], T[0]['surf']['height'])
