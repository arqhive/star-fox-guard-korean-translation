"""MCD 글리프 아틀라스 재생성 (한글).

원본 atlas 구조 (messoption 기준으로 측정):
  - BC3 sRGB, 알파 = 글자 본체, RGB(회색) = 외곽선 (본체를 MaxFilter 로 팽창한 모양)
  - 글리프 rect: 왼쪽 여백 ~7px, 잉크 높이 y13..45 (h57 폰트), rect 폭 = 잉크 오른쪽 + ~7px
  - glyph 레코드: texHash, u1 v1 u2 v2 (정규화), w, h (= rect 픽셀), 추가 3 f32 (폰트별 고정)
새 atlas: 번역문/원문에 쓰이는 (font, char) 전부를 다시 배치.
  원본에 같은 (font, char) 가 있으면 원본 픽셀·metrics 그대로 복사, 없으면 Noto Sans KR 로 렌더.
"""
import struct
from collections import Counter
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

from gtx_lib import bc4_encode_blocks, swizzle, deswizzle
from wtb_lib import parse_wta, decode
from bc1 import bc1_encode_blocks

KO_FONT = r'C:\Windows\Fonts\NotoSansKR-VF.ttf'
KO_WEIGHT = 800
SS = 4  # 슈퍼샘플링
REF = '한국어글뷁빼앎'
PAD = 2  # atlas 셀 사이 여백


def _is_ref(c):
    return 0x4E00 <= c <= 0x9FFF or 0xAC00 <= c <= 0xD7A3


def _is_kana(c):
    return 0x3041 <= c <= 0x30FF and chr(c) not in 'ぁぃぅぇぉっゃゅょゎァィゥェォッャュョヮー゛゜・'


class FontStyle:
    """원본 MCD 안의 한 폰트(id)에 대한 측정값 + 한글 렌더러"""

    def __init__(self, fid, samples):
        # samples: [(char, rgba cell, glyph record)]
        self.fid = fid
        self.h = Counter(int(round(g[6])) for _, _, g in samples).most_common(1)[0][0]
        self.extra = Counter(tuple(g[7:10]) for _, _, g in samples).most_common(1)[0][0]
        refs = [s for s in samples if _is_ref(ord(s[0]))] or [s for s in samples if _is_kana(ord(s[0]))]
        self.from_orig = bool(refs)
        if not refs:
            # 참조 글자가 없는 폰트(숫자 전용 등): 전체 폰트 높이로 추정
            refs = []
            self.left, self.top, self.bottom, self.rpad, self.k = 3, int(self.h * 0.2), int(self.h * 0.8), 3, 5
        else:
            boxes = []
            for ch, cell, g in refs:
                a = cell[..., 3]
                ys, xs = np.nonzero(a > 128)
                if len(xs):
                    boxes.append((xs.min(), ys.min(), ys.max(), cell.shape[1] - 1 - xs.max()))
            b = np.median(np.array(boxes), axis=0)
            self.left, self.top, self.bottom, self.rpad = int(round(b[0])), int(round(b[1])), int(round(b[2])), int(round(b[3]))
            # 외곽선 팽창 크기 추정
            errs = {}
            for k in (3, 5, 7, 9, 11, 13):
                e = 0
                for ch, cell, g in refs[:12]:
                    d = np.asarray(Image.fromarray(np.ascontiguousarray(cell[..., 3])).filter(ImageFilter.MaxFilter(k))).astype(int)
                    e += np.abs(d - cell[..., 0].astype(int)).mean()
                errs[k] = e
            self.k = min(errs, key=errs.get)
        self._setup_font()

    def _setup_font(self):
        tgt = (self.bottom - self.top + 1) * SS
        size = tgt
        for _ in range(4):
            font = self._font(size)
            bb = self._bbox(font)
            size = max(4, int(round(size * tgt / (bb[3] - bb[1]))))
        self.font = self._font(size)
        bb = self._bbox(self.font)
        self.oy = self.top * SS - bb[1]

    @staticmethod
    def _font(size):
        f = ImageFont.truetype(KO_FONT, size)
        try:
            f.set_variation_by_axes([KO_WEIGHT])
        except Exception:
            pass
        return f

    def _bbox(self, font):
        bbs = [font.getbbox(c) for c in REF]
        return (min(b[0] for b in bbs), min(b[1] for b in bbs), max(b[2] for b in bbs), max(b[3] for b in bbs))

    def render(self, ch):
        """-> rgba cell (h x w)"""
        bb = self.font.getbbox(ch)
        wide = self.left + (bb[2] - bb[0]) // SS + self.rpad + 4
        im = Image.new('L', (wide * SS, self.h * SS), 0)
        ImageDraw.Draw(im).text((self.left * SS - bb[0], self.oy), ch, fill=255, font=self.font)
        a = np.asarray(im.resize((wide, self.h), Image.LANCZOS))
        # 실제 잉크 기준으로 폭 결정 (getbbox 는 안티앨리어싱 여백 포함이라 1~3px 넓음)
        xs = np.nonzero(a.max(0) > 40)[0]
        right = xs.max() + 1 if len(xs) else self.left + 1
        w = right + self.rpad - 1
        a = a[:, :w] if w <= wide else np.pad(a, ((0, 0), (0, w - wide)))
        o = np.asarray(Image.fromarray(a).filter(ImageFilter.MaxFilter(self.k)))
        return np.dstack([o, o, o, a]).astype(np.uint8)


def _pow2(x):
    p = 1
    while p < x:
        p *= 2
    return p


def build_atlas(M, wta, wtp, needed):
    """M: parse_mcd 결과 (syms/glyphs 가 교체됨), needed: 정렬된 [(font, charcode)]
    -> (new wta, new wtp, symidx {(font,char): idx})"""
    T = parse_wta(wta)
    assert len(T) == 1
    t = T[0]; s = t['surf']
    tex_hash = t['id']
    W, H = s['width'], s['height']
    orig = decode(t, wtp)
    # 원본 글리프
    orig_cells = {}
    per_font = {}
    for f, ch, gi in M['syms']:
        g = M['glyphs'][gi]
        x0, y0 = int(round(g[1] * W)), int(round(g[2] * H))
        x1, y1 = int(round(g[3] * W)), int(round(g[4] * H))
        cell = orig[y0:y1, x0:x1].copy()
        orig_cells[(f, ch)] = (cell, g)
        per_font.setdefault(f, []).append((chr(ch), cell, g))
    styles = {}

    def style(f):
        if f not in styles:
            src = per_font.get(f)
            if src is None:  # 원본에 없는 폰트: 가장 가까운 id 로 대체
                src = per_font[min(per_font, key=lambda x: abs(x - f))]
            styles[f] = FontStyle(f, src)
        return styles[f]

    cells = []
    for f, ch in needed:
        if (f, ch) in orig_cells:
            cell, g = orig_cells[(f, ch)]
            cells.append((f, ch, cell, list(g[5:10])))
        else:
            st = style(f)
            cell = st.render(chr(ch))
            cells.append((f, ch, cell, [float(cell.shape[1]), float(cell.shape[0])] + list(st.extra)))
    # shelf packing (폰트별로 높이가 달라서 높이순)
    order = sorted(range(len(cells)), key=lambda i: -cells[i][2].shape[0])
    pos = [None] * len(cells)
    x = y = row_h = 0
    for i in order:
        h, w = cells[i][2].shape[:2]
        if x + w + PAD > W:
            x = 0; y += row_h + PAD; row_h = 0
        pos[i] = (x, y)
        x += w + PAD; row_h = max(row_h, h)
    NH = max(H, _pow2(y + row_h + PAD))
    atlas = np.zeros((NH, W, 4), np.uint8)
    syms, glyphs = [], []
    for i, (f, ch, cell, metr) in enumerate(cells):
        cx, cy = pos[i]; h, w = cell.shape[:2]
        atlas[cy:cy + h, cx:cx + w] = cell
        syms.append([f, ch, i])
        glyphs.append([tex_hash, cx / W, cy / NH, (cx + w) / W, (cy + h) / NH] + metr)
    M['syms'], M['glyphs'] = syms, glyphs
    # BC3 인코드
    blk_h, blk_w = NH // 4, W // 4
    a_blk = bc4_encode_blocks(np.ascontiguousarray(atlas[..., 3]))
    c_blk = bc1_encode_blocks(np.ascontiguousarray(atlas[..., :3]))
    lin = np.concatenate([a_blk, c_blk], axis=-1)
    rows = -(-blk_h // 16) * 16
    if rows != blk_h:
        lin = np.concatenate([lin, np.zeros((rows - blk_h, blk_w, 16), np.uint8)])
    img = swizzle(lin)
    new_wtp = img + wtp[s['imageSize']:]  # 원본 꼬리(128B) 유지
    nw = bytearray(wta)
    _, _, oo, so, fo, io, info = struct.unpack('>7I', wta[4:32])
    struct.pack_into('>I', nw, so, len(img) + (t['size'] - s['imageSize']))
    struct.pack_into('>I', nw, info + 0x08, NH)
    struct.pack_into('>I', nw, info + 0x20, len(img))
    r1 = struct.unpack('>I', wta[info + 0x8C:info + 0x90])[0]
    struct.pack_into('>I', nw, info + 0x8C, (r1 & ~0x1FFF) | (NH - 1))
    symidx = {(f, ch): i for i, (f, ch, _) in enumerate(syms)}
    return bytes(nw), new_wtp, symidx, atlas, styles
