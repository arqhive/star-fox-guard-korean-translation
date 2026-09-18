"""PlatinumGames DAT archive (big-endian, Wii U).
Header: 'DAT\0', count, offTbl, extTbl, nameTbl(u32 nameLen + names), sizeTbl, hashMap, 0.
Rebuild keeps everything before the first file (tables + hash map) and file order by offset;
only offsets/sizes change. Data alignment: .wtp 0x2000, others 0x40, file end 0x2000."""
import struct


def read_dat(d):
    n, ot, et, nt, st = struct.unpack('>5I', d[4:24])
    nl = struct.unpack('>I', d[nt:nt+4])[0]
    ents = []
    for i in range(n):
        o = struct.unpack('>I', d[ot+4*i:ot+4*i+4])[0]
        s = struct.unpack('>I', d[st+4*i:st+4*i+4])[0]
        nm = d[nt+4+nl*i:nt+4+nl*i+nl].split(b'\0')[0].decode()
        ents.append(dict(name=nm, off=o, data=d[o:o+s]))
    return ents


def _align(x, a):
    return (x + a - 1) // a * a


def write_dat(orig, files):
    """orig: original DAT bytes, files: {name: bytes} replacements"""
    ents = read_dat(orig)
    n, ot, et, nt, st = struct.unpack('>5I', orig[4:24])
    first = min(e['off'] for e in ents)
    out = bytearray(orig[:first])
    for i in sorted(range(n), key=lambda i: ents[i]['off']):
        e = ents[i]
        data = files.get(e['name'], e['data'])
        pos = _align(len(out), 0x2000 if e['name'].endswith('.wtp') else 0x40)
        out += b'\0' * (pos - len(out))
        struct.pack_into('>I', out, ot + 4 * i, pos)
        struct.pack_into('>I', out, st + 4 * i, len(data))
        out += data
    out += b'\0' * (_align(len(out), 0x2000) - len(out))
    return bytes(out)
