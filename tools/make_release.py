"""배포용 패치 꾸러미 만들기 (방법2: 파이썬 임베더블 + 스크립트 패처).

원본 data000.cpk 와 빌드 결과를 비교해, 바뀐 파일만 골라 release/payload 에 담는다.
 - mess*.mcd/.wta/.wtp (한글 텍스트·글자 텍스처)  -> full  (새 파일 통째로)
 - 그 밖의 .wtp (한글로 고친 그림)                 -> delta (달라진 바이트 구간만)
사용: python tools/make_release.py [--version v0.9]
"""
import argparse, hashlib, json, os, shutil, struct, sys, zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cpk_lib import open_cpk, extract
from dat_lib import read_dat
from build import GAME, BUILD, ROOT, TITLE, MODNAME, md5

REL = os.path.join(ROOT, 'release')
BLOCK = 4096


def diff_blocks(a, b):
    """같은 길이의 두 바이트열에서 달라진 4KB 블록 구간 목록"""
    assert len(a) == len(b)
    spans = []
    for off in range(0, len(a), BLOCK):
        if a[off:off + BLOCK] != b[off:off + BLOCK]:
            if spans and spans[-1][0] + spans[-1][1] == off:
                spans[-1][1] += min(BLOCK, len(a) - off)
            else:
                spans.append([off, min(BLOCK, len(a) - off)])
    return spans


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--version', default='v0.9')
    args = ap.parse_args()
    src = os.path.join(GAME, 'content', 'data000.cpk')
    dst = os.path.join(BUILD, 'sdcafiine', TITLE, MODNAME, 'content', 'data000.cpk')
    pay = os.path.join(REL, 'patcher', 'payload')
    if os.path.isdir(pay):
        shutil.rmtree(pay)
    os.makedirs(pay)

    f0, h0, t0 = open_cpk(src)
    f1, h1, t1 = open_cpk(dst)
    man = {'title': TITLE, 'mod': MODNAME, 'version': args.version,
           'source': {'size': os.path.getsize(src), 'md5': md5(src)},
           'result': {'size': os.path.getsize(dst), 'md5': md5(dst)},
           'dats': {}}
    total = 0
    for a, b in zip(t0, t1):
        assert a['FileName'] == b['FileName']
        if a['FileSize'] == b['FileSize']:
            f0.seek(h0['TocOffset'] + a['FileOffset']); f1.seek(h1['TocOffset'] + b['FileOffset'])
            if f0.read(a['FileSize']) == f1.read(b['FileSize']):
                continue
        da = {e['name']: e['data'] for e in read_dat(extract(f0, h0, a))}
        db = {e['name']: e['data'] for e in read_dat(extract(f1, h1, b))}
        assert set(da) == set(db), a['FileName']
        entries = []
        key = ('core/' if a['DirName'] == 'core' else 'ui/') + a['FileName']
        for name in db:
            if da[name] == db[name]:
                continue
            base = f"{a['FileName'][:-4]}__{name}"
            if len(da[name]) == len(db[name]) and not name.lower().startswith('mess'):
                spans = diff_blocks(da[name], db[name])
                blob = b''.join(db[name][o:o + n] for o, n in spans)
                open(os.path.join(pay, base + '.delta'), 'wb').write(blob)
                entries.append({'name': name, 'mode': 'delta', 'file': base + '.delta', 'spans': spans})
                total += len(blob)
            else:
                open(os.path.join(pay, base + '.bin'), 'wb').write(db[name])
                entries.append({'name': name, 'mode': 'full', 'file': base + '.bin'})
                total += len(db[name])
        man['dats'][key] = entries
        print(f"{key}: {len(entries)}개 파일")
    json.dump(man, open(os.path.join(pay, 'manifest.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'payload {total:,} B  (DAT {len(man["dats"])}개)')


if __name__ == '__main__':
    main()
