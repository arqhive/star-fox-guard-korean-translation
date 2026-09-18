"""Platinum WTA(texture info)/WTP(texture data) for Wii U."""
import struct, numpy as np
from gtx_lib import GTX_FIELDS, deswizzle, bc4_decode_blocks, bc1_decode_blocks

def parse_wta(w):
    ver, cnt, oo, so, fo, io, info = struct.unpack('>7I', w[4:32])
    tex = []
    for i in range(cnt):
        off = struct.unpack('>I', w[oo+4*i:oo+4*i+4])[0]
        size = struct.unpack('>I', w[so+4*i:so+4*i+4])[0]
        flag = struct.unpack('>I', w[fo+4*i:fo+4*i+4])[0]
        tid = struct.unpack('>I', w[io+4*i:io+4*i+4])[0]
        s = dict(zip(GTX_FIELDS, struct.unpack('>16I', w[info+0xc0*i:info+0xc0*i+64])))
        tex.append(dict(off=off, size=size, flag=flag, id=tid, surf=s))
    return tex

def decode(t, wtp):
    s = t['surf']; data = wtp[t['off']:t['off']+t['size']][:s['imageSize']]  # 밉맵 제외
    fmt = s['format'] & 0xff
    bw, bh = (s['width']+3)//4, (s['height']+3)//4
    if s['tileMode'] != 4: raise NotImplementedError(s['tileMode'])
    if fmt == 0x33:
        lin = deswizzle(data, s['pitch'], 16)
        a = bc4_decode_blocks(np.ascontiguousarray(lin[:bh,:bw,0:8]))
        rgb = bc1_decode_blocks(np.ascontiguousarray(lin[:bh,:bw,8:16]))
        return np.dstack([rgb, a])[:s['height'], :s['width']]
    if fmt == 0x31:
        lin = deswizzle(data, s['pitch'], 8)
        return bc1_decode_blocks(np.ascontiguousarray(lin[:bh,:bw,0:8]))[:s['height'], :s['width']]
    raise NotImplementedError(hex(s['format']))


_decode_bc = decode


def decode(t, wtp):
    """BC1/BC3 은 빠른 경로, 그 외(RGBA8 0x1a, R8 0x01, RG8 0x07, BC4/BC5) 는 addrlib 로 deswizzle"""
    s = t['surf']; fmt = s['format'] & 0xff
    if fmt in (0x31, 0x33):
        return _decode_bc(t, wtp)
    data = wtp[t['off']:t['off'] + t['size']][:s['imageSize']]
    W, H = s['width'], s['height']
    if fmt in (0x34, 0x35):
        from gtx_lib import deswizzle as dz
        bpb = 8 if fmt == 0x34 else 16
        lin = dz(data, s['pitch'], bpb)
        bw, bh = (W + 3) // 4, (H + 3) // 4
        ch = [bc4_decode_blocks(np.ascontiguousarray(lin[:bh, :bw, 8 * c:8 * (c + 1)]))[:H, :W] for c in range(bpb // 8)]
        z = np.zeros_like(ch[0])
        return np.dstack([ch[0], ch[1] if len(ch) > 1 else ch[0], z])
    bpp = {0x1a: 32, 0x01: 8, 0x07: 16, 0x19: 32}.get(fmt)
    if bpp is None:
        raise NotImplementedError(hex(s['format']))
    import addrlib
    raw = addrlib.deswizzle(W, H, H, s['format'], s['tileMode'], s['swizzle'], s['pitch'], bpp, data)
    a = np.frombuffer(raw[:W * H * bpp // 8], np.uint8).reshape(H, W, bpp // 8)
    if bpp == 8:
        return a[..., 0]
    if bpp == 16:
        return np.dstack([a[..., 0], a[..., 1], np.zeros_like(a[..., 0])])
    return a.copy()


def encode_into(wta, wtp, index, img):
    """같은 크기로 텍스처 index 를 img(RGBA/RGB ndarray) 로 교체한 새 wtp bytes (BC1/BC3, 밉맵 1개만)"""
    from gtx_lib import swizzle, bc4_encode_blocks
    from bc1 import bc1_encode_blocks
    t = parse_wta(wta)[index]; s = t['surf']
    assert s['numMips'] == 1, 'mipmap texture not supported'
    fmt = s['format'] & 0xff
    W, H = s['width'], s['height']
    assert img.shape[0] == H and img.shape[1] == W, (img.shape, W, H)
    bw, bh = (W + 3) // 4, (H + 3) // 4
    pad = np.pad(img, ((0, bh * 4 - H), (0, bw * 4 - W), (0, 0)), mode='edge')
    rgb = np.ascontiguousarray(pad[..., :3])
    if fmt == 0x31:
        lin = bc1_encode_blocks(rgb); bpb = 8
    elif fmt == 0x33:
        a = pad[..., 3] if pad.shape[2] == 4 else np.full(pad.shape[:2], 255, np.uint8)
        lin = np.concatenate([bc4_encode_blocks(np.ascontiguousarray(a)), bc1_encode_blocks(rgb)], -1); bpb = 16
    else:
        raise NotImplementedError(hex(s['format']))
    rows = s['imageSize'] // bpb // s['pitch']
    full = np.zeros((rows, s['pitch'], bpb), np.uint8)
    full[:bh, :bw] = lin
    data = swizzle(full)
    assert len(data) == s['imageSize']
    out = bytearray(wtp)
    out[t['off']:t['off'] + len(data)] = data
    return bytes(out)
