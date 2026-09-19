"""계약서 텍스처(ui_msg_firsttime.dat / msg_firsttime.wta #0) 한글판 생성
-> translation/images_ko/ui_msg_firsttime.dat/msg_firsttime_000.png"""
import os
import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
SRC = os.path.join(ROOT, 'extract', 'tex', 'ui_ui_msg_firsttime', 'msg_firsttime_000.png')
DST = os.path.join(ROOT, 'translation', 'images_ko', 'ui_msg_firsttime.dat', 'msg_firsttime_000.png')
FONT = r'C:\Windows\Fonts\NotoSansKR-VF.ttf'

TITLE = '계약서'
BODY = ['코네리아 특수금속 스페셜 대사장',
        '그리피 토드는',
        '귀하를 우리 회사 레어메탈 채굴 타워',
        '방어 임무에 투입하여 팍팍 일하게 할',
        '것을 이에 약속한다.']
SIGN = '그리피 토드'


def font(size, wght):
    f = ImageFont.truetype(FONT, size)
    f.set_variation_by_axes([wght])
    return f


def main():
    src = np.array(Image.open(SRC).convert('RGB'))
    r, g, b = [src[..., i].astype(int) for i in range(3)]
    H, W = src.shape[:2]
    yy, xx = np.mgrid[0:H, 0:W]
    green = (g - b > 25) & (g >= r)
    title_box = (xx >= 205) & (xx <= 450) & (yy >= 88) & (yy <= 172)
    body_box = (xx >= 60) & (xx <= 600) & (yy >= 290) & (yy <= 610)
    lum = (r * 3 + g * 6 + b) / 10
    reddish = (r - g > 25)
    sign_box = (xx >= 220) & (xx <= 520) & (yy >= 680) & (yy <= 762)
    sign = sign_box & (lum < 190) & ~reddish
    mask = ((green & (title_box | body_box)) | sign).astype(np.uint8) * 255
    mask = cv2.dilate(mask, np.ones((7, 7), np.uint8))
    # 본문 글자색: 원래 글자 중심부 픽셀 중앙값
    core = green & body_box & (g < 120)
    body_col = tuple(int(np.median(src[core][:, i])) for i in range(3))
    clean = cv2.inpaint(src[..., ::-1].copy(), mask, 6, cv2.INPAINT_TELEA)[..., ::-1]
    # 종이 질감 살리기: 인페인트 영역에 원본 종이의 고주파 노이즈를 옮겨 붙임
    paper = cv2.GaussianBlur(clean.astype(np.float32), (0, 0), 3)
    noise = src.astype(np.float32) - cv2.GaussianBlur(src.astype(np.float32), (0, 0), 3)
    # 글자가 없는 종이 영역(제목 띠 아래~본문 위) 노이즈를 타일링
    patch = noise[200:280, 70:590]
    reps = (H // patch.shape[0] + 1, W // patch.shape[1] + 1, 1)
    noise = np.tile(patch, reps)[:H, :W]
    m = (cv2.GaussianBlur(mask.astype(np.float32), (0, 0), 2) / 255.0)[..., None]
    clean = np.clip(clean * (1 - m) + (paper + noise * 0.6) * m, 0, 255).astype(np.uint8)
    img = Image.fromarray(clean).convert('RGBA')

    # 제목: 위→아래 밝은 녹색→진한 녹색 그라데이션 + 옅은 밝은 테두리
    tf = font(70, 900)
    bb = tf.getbbox(TITLE)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    cx, top = 327, 100
    tm = Image.new('L', img.size, 0)
    ImageDraw.Draw(tm).text((cx - tw / 2 - bb[0], top - bb[1]), TITLE, font=tf, fill=255)
    grad = np.zeros((H, W, 4), np.uint8)
    t = np.clip((yy - top) / max(th, 1), 0, 1)[..., None]
    c0, c1 = np.array([110, 160, 80]), np.array([50, 100, 20])
    grad[..., :3] = (c0 * (1 - t) + c1 * t).astype(np.uint8)
    halo = tm.filter(ImageFilter.MaxFilter(3))
    glow = Image.new('RGBA', img.size, (200, 215, 170, 0)); glow.putalpha(halo.point(lambda v: v * 0.5))
    img = Image.alpha_composite(img, glow)
    grad[..., 3] = np.array(tm)
    img = Image.alpha_composite(img, Image.fromarray(grad))

    # 본문
    bf = font(29, 700)
    d = Image.new('RGBA', img.size, (0, 0, 0, 0)); dd = ImageDraw.Draw(d)
    ys = [322, 386, 450, 515, 580]
    for line, yc in zip(BODY, ys):
        w = bf.getlength(line)
        f = bf if w <= 500 else font(int(29 * 500 / w), 700)
        a = f.getbbox('가')
        dd.text((73, yc - (a[1] + a[3]) / 2), line, font=f, fill=body_col + (235,))
    img = Image.alpha_composite(img, d)

    # 서명: 얇은 기울임 필기 느낌 (도장 빨간 픽셀 아래로)
    sf = font(46, 250)
    s = Image.new('L', (420, 110), 0)
    ImageDraw.Draw(s).text((10, 20), SIGN, font=sf, fill=255)
    s = s.transform(s.size, Image.AFFINE, (1, 0.28, -12, 0, 1, 0), resample=Image.BICUBIC)
    s = s.rotate(4, resample=Image.BICUBIC).filter(ImageFilter.GaussianBlur(0.6))
    layer = Image.new('RGBA', img.size, (0, 0, 0, 0))
    ink = Image.new('RGBA', s.size, (55, 55, 50, 0)); ink.putalpha(s.point(lambda v: min(255, int(v * 0.9))))
    layer.paste(ink, (215, 660), ink)
    arr = np.array(layer)
    arr[..., 3][reddish & sign_box.__or__((xx > 480) & (yy > 650) & (yy < 760)) & reddish] = 0
    img = Image.alpha_composite(img, Image.fromarray(arr))
    # 도장 복원 (원본 빨간 픽셀을 위에 다시)
    out = np.array(img.convert('RGB'))
    stamp = reddish & (xx > 470) & (yy > 650) & (yy < 770)
    out[stamp] = src[stamp]
    os.makedirs(os.path.dirname(DST), exist_ok=True)
    Image.fromarray(out).save(DST)
    print('saved', DST, 'body color', body_col)


if __name__ == '__main__':
    main()
