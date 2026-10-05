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
KO_WEIGHT = 800  # 자동 선택이 안 되는 폰트(가변 축 없음 등)에 쓰는 기본 굵기
AUTO_WEIGHT = True  # 원본 글자의 획 두께에 맞춰 폰트(=구간)마다 굵기를 따로 고른다
WEIGHT_RANGE = (350, 900)
SMALL_H = 100  # 이보다 작은 글씨는 굵기 상한을 낮춰 자음·모음 사이 틈을 지킨다
SMALL_MAX_WEIGHT = 800  # v1.1 굵기. 898 에선 슬리피의 리·피가 붙어 보였다
ROUND_OUTLINE = True  # 외곽선을 확대 해상도에서 둥근 커널로 그려 원본 두께에 맞춤(정사각 MaxFilter 계단 방지)
BOLDEN = False  # 덧칠(획 팽창): 어느 방향이든 틈을 메움(사방=ㅌ, 가로=리·피) -> 끔(2026-10-06 실기 사진)
BOLDEN_MAX = 0.12  # 팽창 상한: 글자 높이 대비 획 두께 증가량
OPEN_MIN = 0.70  # 팽창 후 글자 속공간이 팽창 전의 이 비율 밑으로 줄면 멈춘다(르·포 틈이 막히지 않게)
XSCALE = 0.94  # 한글 가로 축약(원본 칸이 일본어 폭 기준이라 여유 확보)
SS = 4  # 슈퍼샘플링
REF = '한국어글뷁빼앎'
DIGITS = '0123456789'
ALNUM_REDRAW = False  # True: 숫자·영문자도 한글과 같은 글꼴로 새로 그림. 실기에서 글자가 다닥다닥 붙어 보여 끔(2026-10-05), 원본 글리프 유지
ALNUM_MIN_SCALE = 0.85  # 숫자·영문 가로 축약 하한 (원본 평균 폭에 맞추되 이보다 좁히지 않음)
PAD = 2  # atlas 셀 사이 여백


def _alnum_class(ch):
    return 'digit' if ch.isdigit() else ('upper' if ch.isupper() else 'lower')


def redraw(ch):
    """원본 글리프 대신 새로 그릴 글자인가 (한글은 원본에 없으니 늘 새로 그림)"""
    return ALNUM_REDRAW and ch.isascii() and ch.isalnum()


def _is_ref(c):
    return 0x4E00 <= c <= 0x9FFF or 0xAC00 <= c <= 0xD7A3


DILATE_HORIZONTAL = True  # 덧칠은 가로로만: 세로로도 불리면 ㅌ·ㅍ처럼 쌓인 가로획 사이가 메워진다(스타폭스 제로 「통」 사례)


def _dilate(im, r):
    import cv2
    if DILATE_HORIZONTAL:
        k = np.ones((1, 2 * r + 1), np.uint8)
    else:
        k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1))
    return Image.fromarray(cv2.dilate(np.asarray(im), k))


def _outline_band(cell):
    """외곽선만 있는 띠의 평균 두께(px) = 외곽선 넓이 / 글자 윤곽 길이"""
    a = cell[..., 3]; o = cell[..., 0]
    ring = (o > 40) & (a < 128)
    body = a >= 128
    edge = np.abs(np.diff(body, axis=1)).sum() + np.abs(np.diff(body, axis=0)).sum()
    return ring.sum() / max(edge, 1)


def _stroke(a):
    """획 두께 ≈ 2 x 잉크 면적 / 윤곽 길이 (글자 복잡도에 덜 민감하다)"""
    m = np.asarray(a) > 127
    edge = np.abs(np.diff(m, axis=1)).sum() + np.abs(np.diff(m, axis=0)).sum()
    return 2 * m.sum() / max(edge, 1)


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
        self.ref = REF  # 크기·두께를 맞출 때 쓰는 기준 글자
        if not refs and ALNUM_REDRAW:
            # 숫자·영문 전용 폰트(점수 표시 등): 원본 숫자의 높이·두께에 맞춘다
            refs = ([s for s in samples if s[0] in DIGITS]
                    or [s for s in samples if s[0].isascii() and s[0].isupper()])
            self.ref = ''.join(s[0] for s in refs)
        self.from_orig = bool(refs)
        if not refs:
            # 참조 글자가 없는 폰트: 전체 폰트 높이로 추정
            self.ref = REF
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
        # 원본 글자의 획 두께 (구간마다 다르다: 작은 대사는 가늘고 큰 제목은 두껍다)
        self.th_target = float(np.mean([_stroke(c[..., 3]) for _, c, _ in refs[:16]])) if refs else None
        self.weight = KO_WEIGHT
        self.dil = 0  # 획 팽창 반경 (슈퍼샘플 px)
        self._setup_font(self.weight)
        if AUTO_WEIGHT and self.th_target and self._variable():
            self._pick_weight()
        if BOLDEN and self.th_target and self._stroke_now() < self.th_target * 0.97:
            self._pick_dilation()
        self.alnum_scale = 1.0
        self.alnum_left, self.alnum_rpad = self.left, self.rpad
        self._fit_alnum(samples)
        self.ol = 0  # 둥근 외곽선 반경(슈퍼샘플 px), 0이면 예전 MaxFilter(k)
        if ROUND_OUTLINE and refs:
            self.ol_target = float(np.mean([_outline_band(c) for _, c, _ in refs[:16]]))
            self._pick_outline()

    def _pick_outline(self):
        """원본 외곽선 평균 두께(px)에 맞는 둥근 외곽선 반경을 고른다"""
        best, err = 0, None
        for r in range(1, 6 * SS + 1):
            self.ol = r
            e = abs(float(np.mean([_outline_band(self.render(c)) for c in self.ref])) - self.ol_target)
            if err is None or e < err:
                best, err = r, e
            elif e > err:
                break
        self.ol = best

    def _fit_alnum(self, samples):
        """숫자·영문자의 가로 축약률: 원본 글리프 잉크 폭의 중앙값 비율에 맞춘다(넓히지는 않음).
        원본 영문 문단(크레딧·라벨)의 배치가 그대로 유지되게 하기 위함."""
        def ink_w(a):
            xs = np.nonzero(np.asarray(a).max(0) > 127)[0]
            return xs.max() - xs.min() + 1 if len(xs) else 0
        # 좌우 여백: 원본 영문 글리프는 한자보다 여백이 좁다 -> 원본 영문 기준으로 따로 둔다
        sides = []
        for ch, cell, g in samples:
            if redraw(ch):
                xs = np.nonzero(cell[..., 3].max(0) > 127)[0]
                if len(xs):
                    sides.append((xs.min(), cell.shape[1] - 1 - xs.max()))
        if sides:
            self.alnum_left, self.alnum_rpad = (int(round(v)) for v in np.median(np.array(sides), axis=0))
        r = {}
        for ch, cell, g in samples:
            if not redraw(ch):
                continue
            ow, nw = ink_w(cell[..., 3]), ink_w(self.render(ch)[..., 3])
            if ow > 2 and nw > 2:
                r.setdefault(_alnum_class(ch), []).append(ow / nw)
        # 숫자·대문자·소문자는 원본과 Noto 의 폭 비율이 서로 달라서 따로 맞춘다
        self.alnum_scales = {k: float(min(1.0, max(ALNUM_MIN_SCALE, np.median(v)))) for k, v in r.items()}
        if r:
            self.alnum_scale = float(min(1.0, max(ALNUM_MIN_SCALE, np.median(sum(r.values(), [])))))

    def _alnum_scale(self, ch):
        return getattr(self, 'alnum_scales', {}).get(_alnum_class(ch), getattr(self, 'alnum_scale', 1.0))

    def _variable(self):
        try:
            ImageFont.truetype(KO_FONT, 32).set_variation_by_axes([KO_WEIGHT])
            return True
        except Exception:
            return False

    def _pick_weight(self):
        """원본 획 두께에 가장 가까운 굵기를 이분 탐색으로 고른다"""
        lo, hi = WEIGHT_RANGE
        if self.h < SMALL_H:
            hi = min(hi, SMALL_MAX_WEIGHT)
        for _ in range(7):
            mid = (lo + hi) / 2
            self._setup_font(mid)
            if self._stroke_now() < self.th_target:
                lo = mid
            else:
                hi = mid
        self.weight = round((lo + hi) / 2)
        self._setup_font(self.weight)

    def _pick_dilation(self):
        """굵기를 다 올려도 모자란 두께를 획 팽창으로 채운다 (상한 BOLDEN_MAX)"""
        self.dil = 0
        base = self._open_now()
        lo, hi = 0, max(1, int(self.h * BOLDEN_MAX * SS / 2))
        while lo < hi:  # 두께는 반경에 단조 증가, 속공간은 단조 감소
            self.dil = (lo + hi + 1) // 2
            if self._stroke_now() <= self.th_target and self._open_now() >= base * OPEN_MIN:
                lo = self.dil
            else:
                hi = self.dil - 1
        self.dil = lo

    def _open_now(self):
        """잉크 상자 안의 빈 곳 비율(글자 속공간) 평균"""
        v = []
        for c in self.ref:
            a = self.render(c)[..., 3] > 127
            ys, xs = np.nonzero(a)
            v.append(1 - a[ys.min():ys.max() + 1, xs.min():xs.max() + 1].mean())
        return float(np.mean(v))

    def _stroke_now(self):
        return float(np.mean([_stroke(self.render(c)[..., 3]) for c in self.ref]))

    def _setup_font(self, weight):
        tgt = (self.bottom - self.top + 1) * SS
        size = tgt
        for _ in range(4):
            font = self._font(size, weight)
            bb = self._bbox(font)
            size = max(4, int(round(size * tgt / (bb[3] - bb[1]))))
        self.font = self._font(size, weight)
        bb = self._bbox(self.font)
        self.oy = self.top * SS - bb[1]

    @staticmethod
    def _font(size, weight=None):
        f = ImageFont.truetype(KO_FONT, size)
        try:
            f.set_variation_by_axes([KO_WEIGHT if weight is None else weight])
        except Exception:
            pass
        return f

    def _bbox(self, font):
        bbs = [font.getbbox(c) for c in self.ref]
        return (min(b[0] for b in bbs), min(b[1] for b in bbs), max(b[2] for b in bbs), max(b[3] for b in bbs))

    def render(self, ch):
        """-> rgba cell (h x w). 한글은 가로로 XSCALE 만큼 살짝 좁혀 그린다
        (원본 UI 칸이 일본어 폭에 맞춰져 있어 여유를 두기 위함)."""
        bb = self.font.getbbox(ch)
        d = self.dil  # 팽창하면 잉크가 좌우로 d 만큼 번지므로 그만큼 안쪽에서 그린다
        L, Rp = (getattr(self, 'alnum_left', self.left), getattr(self, 'alnum_rpad', self.rpad))             if redraw(ch) else (self.left, self.rpad)  # 숫자·영문은 원본 영문 여백
        wide = L + (bb[2] - bb[0] + 2 * d) // SS + Rp + 4
        x0 = L * SS + d
        im = Image.new('L', (wide * SS, self.h * SS), 0)
        ImageDraw.Draw(im).text((x0 - bb[0], self.oy), ch, fill=255, font=self.font)
        scale = XSCALE if '가' <= ch <= '힣' else (self._alnum_scale(ch) if redraw(ch) else 1.0)
        if d:  # 덧칠(팽창)로 늘어날 폭(양쪽 d)만큼 미리 좁혀서, 굵어져도 글자 폭은 그대로 둔다
            scale -= 2 * d / max(1, bb[2] - bb[0])
        if scale != 1.0:  # 잉크만 좁히고 왼쪽 여백은 유지
            body = im.crop((x0, 0, wide * SS, self.h * SS))
            body = body.resize((max(1, round(body.width * scale)), body.height), Image.LANCZOS)
            im2 = Image.new('L', im.size, 0)
            im2.paste(body, (x0, 0))
            im = im2
        if d:  # 덧칠(가로 방향 팽창)로 세로획을 두껍게
            im = _dilate(im, d)
        im_ss = im
        a = np.asarray(im.resize((wide, self.h), Image.LANCZOS))
        sh = 0
        if redraw(ch):  # 숫자·영문: 글꼴 자체 앞 여백을 빼고 잉크를 원본 영문 여백(L) 위치에 맞춘다
            xs = np.nonzero(a.max(0) > 127)[0]
            if len(xs) and xs.min() > L:
                sh = xs.min() - L
                a = np.pad(a[:, sh:], ((0, 0), (0, sh)))
        # 실제 잉크 기준으로 폭 결정 (getbbox 는 안티앨리어싱 여백 포함이라 1~3px 넓음)
        xs = np.nonzero(a.max(0) > 40)[0]
        right = xs.max() + 1 if len(xs) else L + 1
        w = right + Rp - 1
        a = a[:, :w] if w <= wide else np.pad(a, ((0, 0), (0, w - wide)))
        if getattr(self, 'ol', 0):  # 확대 해상도에서 둥글게 팽창한 뒤 줄여 매끈한 외곽선
            import cv2
            r = self.ol
            k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1))
            o_ss = Image.fromarray(cv2.dilate(np.asarray(im_ss), k))
            if sh:
                o_ss = o_ss.transform(o_ss.size, Image.AFFINE, (1, 0, sh * SS, 0, 1, 0))
            o = np.asarray(o_ss.resize((wide, self.h), Image.LANCZOS))
            o = o[:, :w] if w <= wide else np.pad(o, ((0, 0), (0, w - wide)))
            o = np.maximum(o, a)
        else:
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
        if (f, ch) in orig_cells and not redraw(chr(ch)):
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
