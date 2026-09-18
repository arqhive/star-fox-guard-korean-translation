"""CRI CPK reader (@UTF tables, TOC)."""
import struct

def _dec_utf(data):
    # data: @UTF table bytes (possibly encrypted)
    if data[:4] != b'@UTF':
        m, t = 0x655f, bytearray(data)
        for i in range(len(t)):
            t[i] ^= m & 0xff; m = (m * 0x4115) & 0xffff
        data = bytes(t)
    assert data[:4] == b'@UTF', data[:4]
    return data

def parse_utf(data):
    data = _dec_utf(data)
    tsize, rows_off, str_off, dat_off, name_off, ncols, rowlen, nrows = struct.unpack('>IIIIIHHI', data[4:32])
    base = 8
    def rstr(o):
        s = base + str_off + o
        e = data.index(b'\0', s)
        return data[s:e].decode('utf-8', 'replace')
    cols = []
    p = 32
    for _ in range(ncols):
        flags = data[p]; p += 1
        nm = rstr(struct.unpack('>I', data[p:p+4])[0]); p += 4
        st = flags & 0xf0; ty = flags & 0x0f
        const = None
        if st == 0x30:
            const, p = _rd(data, p, ty, rstr, base, dat_off)
        cols.append((nm, st, ty, const))
    rows = []
    for r in range(nrows):
        q = base + rows_off + r * rowlen
        row = {}
        pos = {}
        for nm, st, ty, const in cols:
            if st == 0x50:
                pos[nm] = (q, ty)
                row[nm], q = _rd(data, q, ty, rstr, base, dat_off)
            elif st == 0x30:
                row[nm] = const
            else:
                row[nm] = None
        row['_pos'] = pos
        rows.append(row)
    return rows

def _rd(d, p, ty, rstr, base, dat_off):
    fmt = {0:'>B',1:'>b',2:'>H',3:'>h',4:'>I',5:'>i',6:'>Q',7:'>q',8:'>f',9:'>d'}
    if ty in fmt:
        n = struct.calcsize(fmt[ty]); return struct.unpack(fmt[ty], d[p:p+n])[0], p + n
    if ty == 0xa:
        return rstr(struct.unpack('>I', d[p:p+4])[0]), p + 4
    if ty == 0xb:
        o, n = struct.unpack('>II', d[p:p+8]); s = base + dat_off + o
        return d[s:s+n], p + 8
    raise ValueError(ty)

def read_chunk(f, off):
    f.seek(off); hdr = f.read(16)
    size = struct.unpack('<Q', hdr[8:16])[0]
    return hdr[:4], parse_utf(f.read(size))

def open_cpk(path):
    f = open(path, 'rb')
    _, h = read_chunk(f, 0)
    h = h[0]
    toc = []
    if h.get('TocOffset'):
        _, toc = read_chunk(f, h['TocOffset'])
    return f, h, toc

def cri_layla_decompress(src):
    # CRILAYLA
    assert src[:8] == b'CRILAYLA'
    usize, hoff = struct.unpack('<II', src[8:16])
    out = bytearray(usize + 0x100)
    out[:0x100] = src[0x10 + hoff:0x10 + hoff + 0x100]
    comp = src
    bitpos = [len(comp) - 0x100]  # read backwards
    state = {'byte': 0, 'left': 0, 'pos': 0x10 + hoff - 1}
    def bits(n):
        v = 0
        while n:
            if state['left'] == 0:
                state['byte'] = comp[state['pos']]; state['pos'] -= 1; state['left'] = 8
            take = min(n, state['left'])
            v = (v << take) | ((state['byte'] >> (state['left'] - take)) & ((1 << take) - 1))
            state['left'] -= take; n -= take
        return v
    w = usize + 0x100 - 1
    end = 0x100
    while w >= end:
        if bits(1):
            off = bits(13) + 3
            ln = 3
            lvls = [2, 3, 5, 8]
            for lv in lvls:
                x = bits(lv); ln += x
                if x != (1 << lv) - 1: break
            else:
                while True:
                    x = bits(8); ln += x
                    if x != 255: break
            for _ in range(ln):
                out[w] = out[w + off]; w -= 1
        else:
            out[w] = bits(8); w -= 1
    return bytes(out[:usize + 0x100])

def extract(f, h, r):
    f.seek(h['ContentOffset'] + r['FileOffset'] if False else r['FileOffset'] + h['TocOffset'])
    d = f.read(r['FileSize'])
    if d[:8] == b'CRILAYLA':
        d = cri_layla_decompress(d)
    return d

def parse_dat(d):
    # Platinum DAT: magic 'DAT\0', count, offsTbl, extTbl, namesTbl, sizesTbl
    import struct
    end = '<' if struct.unpack('<I', d[4:8])[0] < 0x10000 else '>'
    n, ot, et, nt, st = struct.unpack(end + 'IIIII', d[4:24])
    nl = struct.unpack(end + 'I', d[nt:nt+4])[0]
    out = []
    for i in range(n):
        o = struct.unpack(end + 'I', d[ot+4*i:ot+4*i+4])[0]
        s = struct.unpack(end + 'I', d[st+4*i:st+4*i+4])[0]
        nm = d[nt+4+nl*i:nt+4+nl*i+nl].split(b'\0')[0].decode()
        out.append((nm, d[o:o+s]))
    return out


# ---------------------------------------------------------------- rebuild
_FMT = {2: '>H', 4: '>I', 6: '>Q'}


def _patch(buf, base, row, name, value):
    q, ty = row['_pos'][name]
    struct.pack_into(_FMT[ty], buf, base + q, value)


def rebuild_cpk(src, dst, repl, log=print):
    """repl: {'Dir/FileName' or 'FileName': bytes} -> stored uncompressed.
    Keeps header/TOC bytes, patches FileOffset/FileSize/ExtractSize and header sizes in place.
    Content order = original offset order, align = header Align."""
    f, h, toc = open_cpk(src)
    f.seek(0); hdr_chunk = bytearray(f.read(h['ContentOffset']))
    _, hrows = read_chunk(f, 0)
    hrow = hrows[0]
    align = h['Align']; tocoff = h['TocOffset']
    UTF0 = 16  # chunk header size; @UTF row positions are relative to utf start
    key = lambda r: ((r['DirName'] + '/') if r['DirName'] else '') + r['FileName']
    used = set()
    out = open(dst, 'wb')
    out.write(b'\0' * h['ContentOffset'])
    pos = h['ContentOffset']
    packed_delta = data_delta = 0
    for r in sorted(toc, key=lambda r: r['FileOffset']):
        k = key(r)
        if k in repl or r['FileName'] in repl:
            data = repl[k] if k in repl else repl[r['FileName']]
            used.add(k if k in repl else r['FileName'])
            fsz = esz = len(data)
            packed_delta += fsz - r['FileSize']; data_delta += esz - r['ExtractSize']
            log(f'  replace {k}: {r["FileSize"]}/{r["ExtractSize"]} -> {fsz}')
        else:
            f.seek(tocoff + r['FileOffset']); data = f.read(r['FileSize'])
            fsz, esz = r['FileSize'], r['ExtractSize']
        npos = (pos + align - 1) // align * align
        out.write(b'\0' * (npos - pos)); pos = npos
        tp = UTF0 + tocoff
        _patch(hdr_chunk, tp, r, 'FileOffset', pos - tocoff)
        _patch(hdr_chunk, tp, r, 'FileSize', fsz)
        _patch(hdr_chunk, tp, r, 'ExtractSize', esz)
        out.write(data); pos += len(data)
    missing = set(repl) - used
    if missing: raise KeyError(f'not in CPK: {missing}')
    epos = (pos + align - 1) // align * align
    out.write(b'\0' * (epos - pos))
    f.seek(h['EtocOffset']); out.write(f.read(h['EtocSize']))
    # tail after ETOC (if any)
    f.seek(0, 2); end = f.tell(); f.seek(h['EtocOffset'] + h['EtocSize'])
    out.write(f.read(end - h['EtocOffset'] - h['EtocSize']))
    for nm, val in [('ContentSize', epos - h['ContentOffset']), ('EtocOffset', epos),
                    ('EnabledPackedSize', h['EnabledPackedSize'] + packed_delta),
                    ('EnabledDataSize', h['EnabledDataSize'] + data_delta)]:
        if nm in hrow['_pos']:
            _patch(hdr_chunk, UTF0, hrow, nm, val)
    out.seek(0); out.write(hdr_chunk); out.close(); f.close()
