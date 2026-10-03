"""원본 글리프와 한글 글리프를 나란히 둔 비교 시트 생성.

  python tools/font_compare.py glyphs <out.png>   # 폰트별 글자 모양 비교
  python tools/font_compare.py lines  <out.png>   # 실제 문장 비교(원본 vs 한글)

원본 CPK에서 바로 읽으므로 빌드 결과가 없어도 된다.
"""
import glob
import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cpk_lib import open_cpk, extract
from dat_lib import read_dat
from mcd_lib import parse_mcd
from wtb_lib import parse_wta, decode
from font_build import FontStyle, KO_FONT

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GAME = os.path.join(ROOT, '..', '스타폭스 가드 [Game] [00050000101beb00]')
BG = (12, 26, 54)
LAB = ImageFont.truetype(KO_FONT, 20)
TARGETS = [('ui_msg_firsttime.dat', 'messmsg_firsttime.mcd', '스토리 대사'),
           ('ui_title.dat', 'messtitle.mcd', '타이틀·메뉴'),
           ('ui_hud.dat', 'messhud.mcd', '게임 중 HUD'),
           ('ui_core.dat', 'messcore.mcd', '공통 UI')]
SAMPLE = '한글패치글자모양'


def load(dat, mcd):
    f, h, toc = open_cpk(os.path.join(GAME, 'content', 'data000.cpk'))
    r = next(r for r in toc if r['FileName'] == dat)
    ents = {e['name']: e['data'] for e in read_dat(extract(f, h, r))}
    M = parse_mcd(ents[mcd])
    base = mcd[:-4]
    T = parse_wta(ents[base + '.wta'])
    img = decode(T[0], ents[base + '.wtp'])
    cells, per_font = {}, {}
    H, W = img.shape[:2]
    for fid, ch, gi in M['syms']:
        g = M['glyphs'][gi]
        x0, y0 = int(round(g[1] * W)), int(round(g[2] * H))
        x1, y1 = int(round(g[3] * W)), int(round(g[4] * H))
        cell = img[y0:y1, x0:x1].copy()
        cells[(fid, ch)] = (cell, g)
        per_font.setdefault(fid, []).append((chr(ch), cell, g))
    return M, cells, per_font


def blit(canvas, cell, x, y):
    """preview.py 와 같은 합성: 알파 = 흰 글자 본체, RGB = 검은 외곽선"""
    h, w = cell.shape[:2]
    if y + h > canvas.shape[0] or x + w > canvas.shape[1]:
        return
    c = cell.astype(np.float32) / 255
    o, a = c[..., :1], c[..., 3:4]
    reg = canvas[y:y + h, x:x + w]
    reg[:] = reg * (1 - o) * (1 - a) + 255 * a


def draw_jp(canvas, M, cells, line, x, y):
    fonts = {f[0]: f for f in M['fonts']}
    w = line['words']
    i = 0
    while i < len(w) and w[i] != 0x8000:
        c, arg = w[i], w[i + 1]
        if c < 0x8000:
            fid, ch, gi = M['syms'][c]
            cell, g = cells[(fid, ch)]
            blit(canvas, cell, x, y)
            x += int(g[5] + line['a']) + (arg - 0x10000 if arg & 0x8000 else arg)
        elif c == 0x8001:
            x += int(fonts[arg][1] + line['a'])
        elif c == 0x8003:
            canvas[y + 15:y + 45, x + 4:x + 34] = (210, 170, 20)
            x += 40
        i += 2
    return x


def draw_ko(canvas, M, cells, style, text, pfont, x, y, a):
    fonts = {f[0]: f for f in M['fonts']}
    for ch in text:
        if ch == ' ':
            x += int(fonts[pfont][1] + a)
            continue
        key = (pfont, ord(ch))
        cell = cells[key][0] if key in cells else style.render(ch)
        blit(canvas, cell, x, y)
        x += cell.shape[1] + int(a)
    return x


def text_layer(size, labels):
    im = Image.new('RGBA', size, (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    for x, y, t in labels:
        col = (255, 220, 120, 255) if t in ('원본', '한글') else (150, 200, 255, 255)
        d.text((x, y), t, fill=col, font=LAB)
    return im


def save(canvas, labels, out):
    im = Image.fromarray(canvas.astype(np.uint8)).convert('RGBA')
    im.alpha_composite(text_layer(im.size, labels))
    im.convert('RGB').save(out)
    print('saved', out, im.size)


def sheet_glyphs(out):
    rows = []
    for dat, mcd, title in TARGETS:
        M, cells, per_font = load(dat, mcd)
        for fid, samples in sorted(per_font.items()):
            jp = [s for s in samples
                  if 'ぁ' <= s[0] <= 'ヿ' or '一' <= s[0] <= '鿿']
            if len(jp) < 8:
                continue
            h = int(round(jp[0][2][6]))
            rows.append((f'{title}  ·  {mcd}  ·  font {fid}  ·  글자 높이 {h}px',
                         jp[:10], FontStyle(fid, samples)))
    hs = [max(c.shape[0] for _, c, _ in r[1]) for r in rows]
    H = 24 + sum(30 + 2 * h + 10 + 26 for h in hs)
    canvas = np.zeros((H, 1400, 3), np.float32)
    canvas[:] = BG
    labels = []
    y = 24
    for (name, jp, st), h in zip(rows, hs):
        labels.append((28, y, name))
        y += 30
        labels.append((36, y + h // 2 - 14, '원본'))
        x = 150
        for _, cell, _ in jp:
            if x + cell.shape[1] > canvas.shape[1] - 20:
                break
            blit(canvas, cell, x, y)
            x += cell.shape[1] + 6
        y += h + 10
        labels.append((36, y + h // 2 - 14, '한글'))
        x = 150
        for ch in SAMPLE:
            cell = st.render(ch)
            if x + cell.shape[1] > canvas.shape[1] - 20:
                break
            blit(canvas, cell, x, y)
            x += cell.shape[1] + 6
        y += h + 26
    save(canvas, labels, out)


def sheet_lines(out):
    tl = {}
    for p in sorted(glob.glob(os.path.join(glob.escape(ROOT), 'translation', 'ko', '*.json'))):
        for k, v in json.load(open(p, encoding='utf-8')).items():
            d, m, mi, pi = k.split('|')
            tl[(d, m, int(mi), int(pi))] = v.replace('\r\n', '\n')
    blocks = []
    for dat, mcd, title in TARGETS:
        M, cells, per_font = load(dat, mcd)
        used = set()
        for mi, msg in enumerate(M['msgs']):
            for pi, pa in enumerate(msg['paras']):
                ko = tl.get((dat, mcd, mi, pi))
                if not ko or pa['font'] in used or len(pa['lines']) > 2:
                    continue
                if not any('가' <= c <= '힣' for c in ko):
                    continue
                n = max(len(l['words']) for l in pa['lines'])
                if n < 16 or n > 64:
                    continue
                used.add(pa['font'])
                blocks.append((f'{title}  ·  {mcd}  ·  font {pa["font"]}',
                               M, cells, FontStyle(pa['font'], per_font[pa['font']]), pa, ko))
    H = 24 + sum(34 + (len(pa['lines']) + len(ko.split('\n'))) * (st.h + 14) + 36
                 for _, _, _, st, pa, ko in blocks)
    canvas = np.zeros((H, 1700, 3), np.float32)
    canvas[:] = BG
    labels = []
    y = 24
    for name, M, cells, st, pa, ko in blocks:
        labels.append((28, y, name))
        y += 34
        labels.append((36, y + st.h // 2 - 14, '원본'))
        for l in pa['lines']:
            draw_jp(canvas, M, cells, l, 150, y)
            y += st.h + 14
        labels.append((36, y + st.h // 2 - 14, '한글'))
        for li, t in enumerate(ko.split('\n')):
            l = pa['lines'][min(li, len(pa['lines']) - 1)]
            draw_ko(canvas, M, cells, st, t, pa['font'], 150, y, l['a'])
            y += st.h + 14
        y += 36
    save(canvas[:y], labels, out)


CANDS = [('현재 · Noto Sans KR ExtraBold(w800)', KO_FONT, 800),
         ('본고딕 Bold · Source Han Sans KR', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fonts', 'SourceHanSansKR-Bold.otf'), None),
         ('본고딕 Heavy · Source Han Sans KR', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fonts', 'SourceHanSansKR-Heavy.otf'), None),
         ('Pretendard Bold', os.path.join(os.environ['LOCALAPPDATA'], 'Microsoft', 'Windows', 'Fonts', 'Pretendard-Bold.otf'), None),
         ('Pretendard ExtraBold', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fonts', 'Pretendard-ExtraBold.otf'), None)]
PICKS = [('ui_msg_firsttime.dat', 'messmsg_firsttime.mcd', 7, '스토리 대사 (58px)', '코네리아 채굴 기지를 지켜라.'),
         ('ui_core.dat', 'messcore.mcd', 1, '공통 UI 본문 (57px)', '리플레이 계속하기'),
         ('ui_title.dat', 'messtitle.mcd', 3, '메뉴 굵은 글씨 (64px)', '친구/가족의 유닛'),
         ('ui_core.dat', 'messcore.mcd', 4, '큰 제목 (130px)', '드릴 하이호')]


def style_with(fid, samples, path, weight):
    """글꼴 파일만 바꿔 같은 보정값으로 FontStyle 생성"""
    import font_build
    old_f, old_w = font_build.KO_FONT, font_build.KO_WEIGHT
    font_build.KO_FONT = path
    if weight:
        font_build.KO_WEIGHT = weight
    try:
        return FontStyle(fid, samples)
    finally:
        font_build.KO_FONT, font_build.KO_WEIGHT = old_f, old_w


def sheet_fonts(out):
    blocks = []
    for dat, mcd, fid, title, text in PICKS:
        M, cells, per_font = load(dat, mcd)
        samples = per_font[fid]
        jp = [s for s in samples
              if 'ぁ' <= s[0] <= 'ヿ' or '一' <= s[0] <= '鿿'][:10]
        styles = [(name, style_with(fid, samples, p, w)) for name, p, w in CANDS]
        blocks.append((f'{title}  ·  {mcd}  ·  font {fid}', jp, styles, text))
    W = 1700
    H = 24 + sum(34 + (len(b[2]) + 1) * (b[2][0][1].h + 12) + 36 for b in blocks)
    canvas = np.zeros((H, W, 3), np.float32)
    canvas[:] = BG
    labels = []
    y = 24
    for name, jp, styles, text in blocks:
        labels.append((28, y, name))
        y += 34
        h = styles[0][1].h
        labels.append((36, y + h // 2 - 14, '원본'))
        x = 420
        for _, cell, _ in jp:
            if x + cell.shape[1] > W - 20:
                break
            blit(canvas, cell, x, y)
            x += cell.shape[1] + 6
        y += h + 12
        for cname, st in styles:
            labels.append((36, y + h // 2 - 14, cname))
            x = 420
            for ch in text:
                if ch == ' ':
                    x += int(h * 0.3)
                    continue
                cell = st.render(ch)
                if x + cell.shape[1] > W - 20:
                    break
                blit(canvas, cell, x, y)
                x += cell.shape[1]
            y += h + 12
        y += 36
    save(canvas[:y], labels, out)


def style_mode(fid, samples, auto):
    """auto=False: 예전 방식(전 구간 800 고정), True: 구간별 자동 굵기+팽창"""
    import font_build
    old = font_build.AUTO_WEIGHT, font_build.BOLDEN
    font_build.AUTO_WEIGHT = font_build.BOLDEN = auto
    try:
        return FontStyle(fid, samples)
    finally:
        font_build.AUTO_WEIGHT, font_build.BOLDEN = old


def sheet_weights(out):
    """폰트(구간)마다 실제 문장 한 개: 원본 / 기존(800 고정) / 구간별 굵기"""
    tl = {}
    for p in sorted(glob.glob(os.path.join(glob.escape(ROOT), 'translation', 'ko', '*.json'))):
        for k, v in json.load(open(p, encoding='utf-8')).items():
            d, m, mi, pi = k.split('|')
            tl[(d, m, int(mi), int(pi))] = v.replace('\r\n', '\n')
    blocks, seen = [], set()
    for dat, mcd, title in TARGETS:
        M, cells, per_font = load(dat, mcd)
        best = {}
        for mi, msg in enumerate(M['msgs']):
            for pi, pa in enumerate(msg['paras']):
                ko = tl.get((dat, mcd, mi, pi))
                fid = pa['font']
                if not ko or fid in seen or len(pa['lines']) > 1 or len(ko.split('\n')) > 1:
                    continue
                if sum('가' <= c <= '힣' for c in ko) < 2:
                    continue
                n = len(pa['lines'][0]['words']) // 2
                cap = 22 if per_font[fid][0][2][6] < 80 else (10 if per_font[fid][0][2][6] < 200 else 5)
                if n > cap:
                    continue
                if fid not in best or n > best[fid][0]:
                    best[fid] = (n, pa, ko)
        for fid, (n, pa, ko) in sorted(best.items()):
            seen.add(fid)
            old = style_mode(fid, per_font[fid], False)
            new = style_mode(fid, per_font[fid], True)
            note = f'굵기 {new.weight}' + (f' + 팽창 {new.dil / 4:.2f}px' if new.dil else '')
            blocks.append((f'{title}  ·  {mcd}  ·  font {fid}  ·  {new.h}px  ·  새 설정: {note}',
                           M, cells, old, new, pa, ko))
    W = 1700
    H = 24 + sum(34 + 3 * (b[4].h + 14) + 30 for b in blocks)
    canvas = np.zeros((H, W, 3), np.float32)
    canvas[:] = BG
    labels = []
    y = 24
    for name, M, cells, old, new, pa, ko in blocks:
        labels.append((28, y, name))
        y += 34
        h = new.h
        l = pa['lines'][0]
        labels.append((36, y + h // 2 - 14, '원본'))
        draw_jp(canvas, M, cells, l, 200, y)
        y += h + 14
        labels.append((36, y + h // 2 - 14, '기존 (800 고정)'))
        draw_ko(canvas, M, cells, old, ko, pa['font'], 200, y, l['a'])
        y += h + 14
        labels.append((36, y + h // 2 - 14, '구간별 굵기'))
        draw_ko(canvas, M, cells, new, ko, pa['font'], 200, y, l['a'])
        y += h + 14 + 30
    save(canvas[:y], labels, out)


if __name__ == '__main__':
    {'glyphs': sheet_glyphs, 'lines': sheet_lines, 'fonts': sheet_fonts,
     'weights': sheet_weights}[sys.argv[1]](sys.argv[2])
