"""PlatinumGames MCD (Star Fox Guard, Wii U, big-endian) read/write.

Layout (verified by byte-identical round-trip):
  header 10*u32: msgOff,msgCnt, symOff,symCnt, glyphOff,glyphCnt, fontOff,fontCnt, evOff,evCnt
  contents (u16 words for every line, in msg/para/line order), u16 0, align 4
  msgs   16b: paraOff, paraCnt, seq, eventHash           then u32 0
  paras  20b: lineOff, lineCnt, paraIdx, u32 0, font<<16  then u32 0
  lines  24b: contentOff, 0, wordCnt, wordCnt, f32 a, f32 b then u32 0
  syms    8b: u16 font, u16 char(UTF-16), u32 glyphIdx   then u32 0
  glyphs 40b: u32 texHash, f32 u1,v1,u2,v2, w,h, f32 x3    then u32 0
  fonts  20b: u32 id, f32 x4                             then u32 0
  events 40b: u32 hash, u32 msgIdx, char[32] name
Line words: (symIdx, kerning s16) pairs; 0x8001,font = space; 0x8003,n = button icon n; 0x8000 = end.
"""
import struct


def parse_mcd(m):
    mo, mc, so, sc, go, gc, fo, fc, eo, ec = struct.unpack('>10I', m[:40])
    M = dict(msgs=[], syms=[], glyphs=[], fonts=[], events=[])
    for i in range(mc):
        po, pc, seq, eh = struct.unpack('>4I', m[mo+16*i:mo+16*i+16])
        paras = []
        for j in range(pc):
            lo, lc, pidx, z, font = struct.unpack('>5I', m[po+20*j:po+20*j+20])
            lines = []
            for k in range(lc):
                co, z2, n, n2 = struct.unpack('>4I', m[lo+24*k:lo+24*k+16])
                fa, fb = m[lo+24*k+16:lo+24*k+24][:4], m[lo+24*k+20:lo+24*k+24]
                words = list(struct.unpack('>%dH' % n, m[co:co+2*n]))
                assert z2 == 0 and n == n2
                lines.append(dict(words=words, a=struct.unpack('>f', fa)[0], b=struct.unpack('>f', fb)[0]))
            paras.append(dict(idx=pidx, z=z, font=font >> 16, fontlo=font & 0xffff, lines=lines))
        M['msgs'].append(dict(seq=seq, hash=eh, paras=paras))
    M['syms'] = [list(struct.unpack('>HHI', m[so+8*i:so+8*i+8])) for i in range(sc)]
    M['glyphs'] = [list(struct.unpack('>I9f', m[go+40*i:go+40*i+40])) for i in range(gc)]
    M['fonts'] = [list(struct.unpack('>I4f', m[fo+20*i:fo+20*i+20])) for i in range(fc)]
    for i in range(ec):
        o = eo + 40 * i
        h, idx = struct.unpack('>II', m[o:o+8])
        M['events'].append(dict(hash=h, idx=idx, name=m[o+8:o+40]))
    return M


def build_mcd(M):
    lines = [l for msg in M['msgs'] for p in msg['paras'] for l in p['lines']]
    out = bytearray(40)
    coffs = []
    for l in lines:
        coffs.append(len(out))
        out += struct.pack('>%dH' % len(l['words']), *l['words'])
    out += b'\0\0'  # u16 terminator
    while len(out) % 4: out += b'\0'
    npara = sum(len(msg['paras']) for msg in M['msgs'])
    mo = len(out)
    po = mo + 16 * len(M['msgs']) + 4
    lo = po + 20 * npara + 4
    so = lo + 24 * len(lines) + 4
    go = so + 8 * len(M['syms']) + 4
    fo = go + 40 * len(M['glyphs']) + 4
    eo = fo + 20 * len(M['fonts']) + 4
    pi = li = 0
    msgb = bytearray(); parab = bytearray(); lineb = bytearray()
    for msg in M['msgs']:
        msgb += struct.pack('>4I', po + 20 * pi, len(msg['paras']), msg['seq'], msg['hash'])
        for p in msg['paras']:
            parab += struct.pack('>5I', lo + 24 * li, len(p['lines']), p['idx'], p['z'], (p['font'] << 16) | p['fontlo'])
            pi += 1
            for l in p['lines']:
                n = len(l['words'])
                lineb += struct.pack('>4I2f', coffs[li], 0, n, n, l['a'], l['b'])
                li += 1
    out += msgb + b'\0' * 4 + parab + b'\0' * 4 + lineb + b'\0' * 4
    for s in M['syms']: out += struct.pack('>HHI', *s)
    out += b'\0' * 4
    for g in M['glyphs']: out += struct.pack('>I9f', *g)
    out += b'\0' * 4
    for f in M['fonts']: out += struct.pack('>I4f', *f)
    out += b'\0' * 4
    for e in M['events']: out += struct.pack('>II', e['hash'], e['idx']) + e['name']
    struct.pack_into('>10I', out, 0, mo, len(M['msgs']), so, len(M['syms']), go, len(M['glyphs']),
                     fo, len(M['fonts']), eo, len(M['events']))
    return bytes(out)


# ---------------------------------------------------------------- text <-> words
# 표기: 일반 글자 그대로 / 커닝 != 0 이면 글자 뒤 {k:-2} / 공백 0x8001 은 ' ' (폰트가 문단 폰트와 다르면 {sp:n})
#       버튼 아이콘 {btn:n} / 리터럴 { } 는 {{ }} / 줄바꿈 = 줄 구분
def words_to_text(words, syms, pfont):
    s = []; i = 0
    while i < len(words):
        w = words[i]
        if w == 0x8000:
            assert i == len(words) - 1
            break
        arg = words[i + 1]
        if w < 0x8000:
            f, ch, _ = syms[w]
            c = chr(ch)
            s.append({'{': '{{', '}': '}}'}.get(c, c))
            if f != pfont: s.append('{f:%d}' % f)
            if arg: s.append('{k:%d}' % (arg - 0x10000 if arg & 0x8000 else arg))
        elif w == 0x8001:
            s.append(' ' if arg == pfont else '{sp:%d}' % arg)
        elif w == 0x8003:
            s.append('{btn:%d}' % arg)
        else:
            raise ValueError(hex(w))
        i += 2
    return ''.join(s)


def text_to_words(text, symidx, pfont):
    """text (words_to_text 표기) -> words. symidx: {(font, char): symIdx}. 없는 글자는 KeyError"""
    words = []
    i = 0
    while i < len(text):
        c = text[i]
        if text.startswith('{{', i) or text.startswith('}}', i):
            ch = c; i += 2
        elif c == '{':
            j = text.index('}', i)
            tag, val = text[i+1:j].split(':'); val = int(val); i = j + 1
            if tag == 'btn': words += [0x8003, val]
            elif tag == 'sp': words += [0x8001, val]
            elif tag == 'k': words[-1] = val & 0xffff
            elif tag == 'f':  # 앞 글자의 폰트 변경
                raise NotImplementedError('font tag')
            else: raise ValueError(tag)
            continue
        else:
            ch = c; i += 1
        if ch == ' ':
            words += [0x8001, pfont]
        else:
            words += [symidx[(pfont, ord(ch))], 0]
    return words + [0x8000]
