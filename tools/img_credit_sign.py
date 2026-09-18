"""크레딧 손글씨 서명 (ui_credit.dat / credit.wta #3, 512x128 RGBA) 한글판
-> translation/images_ko/ui_credit.dat/credit_003.png
원본: 분홍빛 흰 마커 글씨 + 빨간 외곽선 + 밑줄, 투명 배경"""
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
DST = os.path.join(ROOT, 'translation', 'images_ko', 'ui_credit.dat', 'credit_003.png')
FONT = os.environ.get('SIGN_FONT', r'C:\Windows\Fonts\NotoSansKR-VF.ttf')
TEXT = '그리피 토드'
SS = 4
FILL = (255, 228, 228)
LINE = (235, 20, 20)


def main():
    W, H = 512 * SS, 128 * SS
    mask = Image.new('L', (W, H), 0)
    f = ImageFont.truetype(FONT, 54 * SS)
    try:
        f.set_variation_by_axes([500])
    except Exception:
        pass
    ImageDraw.Draw(mask).text((24 * SS, 18 * SS), TEXT, font=f, fill=255)
    # 필기 느낌: 오른쪽으로 기울이고 살짝 올라가게 회전
    mask = mask.transform(mask.size, Image.AFFINE, (1, 0.22, -10 * SS, 0, 1, 0), resample=Image.BICUBIC)
    mask = mask.rotate(3, resample=Image.BICUBIC, center=(40 * SS, 60 * SS))
    d = ImageDraw.Draw(mask)
    # 밑줄: 왼쪽 아래에서 오른쪽 위로 살짝 휘는 획
    pts = [(6 + t * 300, 110 - 42 * t - 10 * np.sin(np.pi * t)) for t in np.linspace(0, 1, 40)]
    d.line([(x * SS, y * SS) for x, y in pts], fill=255, width=5 * SS, joint='curve')
    fill = mask.resize((512, 128), Image.LANCZOS)
    outline = fill.filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.GaussianBlur(0.5))
    a_f = np.asarray(fill).astype(np.float32) / 255
    a_o = np.asarray(outline).astype(np.float32) / 255
    rgb = np.zeros((128, 512, 3), np.float32)
    rgb[:] = LINE
    rgb = rgb * (1 - a_f[..., None]) + np.array(FILL, np.float32) * a_f[..., None]
    alpha = np.clip(np.maximum(a_o, a_f) * 255, 0, 255)
    out = np.dstack([rgb, alpha]).astype(np.uint8)
    os.makedirs(os.path.dirname(DST), exist_ok=True)
    Image.fromarray(out, 'RGBA').save(DST)
    print('saved', DST)


if __name__ == '__main__':
    main()
