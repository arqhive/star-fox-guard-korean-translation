"""BC1 encoder (Wii Fit U image_tool.py 에서 가져옴)"""
import numpy as np


def bc1_encode_blocks(rgb):
    """rgb: (H, W, 3) uint8, H/W 4의 배수 -> (H/4, W/4, 8), 항상 4색 모드(c0 > c1)"""
    H, W, _ = rgb.shape
    bh, bw = H // 4, W // 4
    px = rgb.reshape(bh, 4, bw, 4, 3).transpose(0, 2, 1, 3, 4).reshape(bh, bw, 16, 3).astype(np.float32)
    mean = px.mean(2, keepdims=True)
    cen = px - mean
    cov = np.einsum('abki,abkj->abij', cen, cen)
    axis = np.ones((bh, bw, 3), np.float32)
    for _ in range(6):
        axis = np.einsum('abij,abj->abi', cov, axis)
        axis /= np.linalg.norm(axis, axis=-1, keepdims=True) + 1e-6
    proj = np.einsum('abki,abi->abk', cen, axis)
    e0 = mean[:, :, 0] + axis * proj.max(2)[..., None]
    e1 = mean[:, :, 0] + axis * proj.min(2)[..., None]

    def to565(c):
        c = np.clip(np.rint(c), 0, 255).astype(np.int32)
        return ((c[..., 0] * 31 + 127) // 255 << 11) | ((c[..., 1] * 63 + 127) // 255 << 5) | ((c[..., 2] * 31 + 127) // 255)

    c0 = to565(e0); c1 = to565(e1)
    swap = c0 < c1
    c0, c1 = np.where(swap, c1, c0), np.where(swap, c0, c1)
    eq = c0 == c1
    c0 = np.where(eq & (c0 < 0xFFFF), c0 + 1, c0)
    c1 = np.where(eq & (c0 == 0xFFFF), c1 - 1, c1)
    blk = np.zeros((bh, bw, 8), np.uint8)
    blk[..., 0] = c0 & 0xFF; blk[..., 1] = c0 >> 8; blk[..., 2] = c1 & 0xFF; blk[..., 3] = c1 >> 8

    def rgb888(c):
        r = (c >> 11) & 31; g = (c >> 5) & 63; b = c & 31
        return np.stack([(r << 3) | (r >> 2), (g << 2) | (g >> 4), (b << 3) | (b >> 2)], -1).astype(np.float32)

    p0, p1 = rgb888(c0), rgb888(c1)
    pal = np.stack([p0, p1, np.floor((2 * p0 + p1) / 3), np.floor((p0 + 2 * p1) / 3)], 2)
    dist = ((px[:, :, :, None, :] - pal[:, :, None, :, :]) ** 2).sum(-1)
    idx = dist.argmin(-1).astype(np.int64)
    bits = np.zeros((bh, bw), np.int64)
    for k in range(16):
        bits |= idx[..., k] << (2 * k)
    for i in range(4):
        blk[..., 4 + i] = (bits >> (8 * i)) & 0xFF
    return blk
