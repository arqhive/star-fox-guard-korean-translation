"""스타폭스 가드 한글 패치 적용기 (표준 라이브러리만 사용).

원본 data000.cpk 를 읽어 한글판 data000.cpk 를 만든다. 원본 파일은 그대로 둔다.

  python patch.py [원본 data000.cpk] [--out 결과폴더] [--sd E:]

인자를 주지 않으면 같은 폴더의 data000.cpk 를 찾고, 없으면 경로를 물어본다.
"""
import argparse, hashlib, json, os, shutil, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, 'lib'))
from cpk_lib import open_cpk, extract, rebuild_cpk
from dat_lib import read_dat, write_dat

PAYLOAD = os.path.join(HERE, 'payload')


def md5(path):
    h = hashlib.md5()
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(1 << 24), b''):
            h.update(b)
    return h.hexdigest()


def ask_source():
    print('원본 data000.cpk 경로를 입력하세요 (탐색기에서 파일을 끌어다 놓아도 됩니다).')
    p = input('> ').strip().strip('"')
    return p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('source', nargs='?', help='원본 data000.cpk')
    ap.add_argument('--out', help='결과를 둘 폴더 (기본: 이 폴더의 out)')
    ap.add_argument('--sd', help='SD 카드 드라이브 (예: E:) - 지정하면 SDCafiine 경로까지 복사')
    args = ap.parse_args()

    man = json.load(open(os.path.join(PAYLOAD, 'manifest.json'), encoding='utf-8'))
    print(f"스타폭스 가드 한글 패치 {man['version']}\n")

    src = args.source or (os.path.join(HERE, 'data000.cpk') if os.path.exists(os.path.join(HERE, 'data000.cpk')) else None)
    while not src or not os.path.isfile(src):
        if src:
            print(f'파일을 찾을 수 없습니다: {src}')
        src = ask_source()

    size = os.path.getsize(src)
    if size != man['source']['size']:
        print(f"[오류] 원본 크기가 다릅니다. 기대 {man['source']['size']:,} B / 실제 {size:,} B")
        print('일본판(00050000101BEB00) 원본 data000.cpk 인지 확인하세요.')
        return 1
    print('원본 확인 중...')
    if md5(src) != man['source']['md5']:
        print('[오류] 원본 MD5가 다릅니다. 이미 패치한 파일이거나 다른 버전입니다.')
        print(f"  기대: {man['source']['md5']}")
        return 1

    out_dir = args.out or os.path.join(HERE, 'out')
    os.makedirs(out_dir, exist_ok=True)
    dst = os.path.join(out_dir, 'data000.cpk')

    print('한글 데이터 적용 중... (1~2분 걸립니다)')
    f, h, toc = open_cpk(src)
    repl = {}
    for key, entries in man['dats'].items():
        name = key.split('/')[1]
        r = next(r for r in toc if r['FileName'] == name)
        orig = extract(f, h, r)
        files = {}
        cur = {e['name']: e['data'] for e in read_dat(orig)}
        for e in entries:
            blob = open(os.path.join(PAYLOAD, e['file']), 'rb').read()
            if e['mode'] == 'full':
                files[e['name']] = blob
            else:
                buf = bytearray(cur[e['name']])
                pos = 0
                for off, n in e['spans']:
                    buf[off:off + n] = blob[pos:pos + n]
                    pos += n
                files[e['name']] = bytes(buf)
        repl[key] = write_dat(orig, files)
        print(f'  {key}')
    f.close()

    print('CPK 다시 쓰는 중...')
    rebuild_cpk(src, dst, repl, log=lambda *a: None)
    if md5(dst) != man['result']['md5']:
        print('[오류] 결과 파일이 예상과 다릅니다. 원본이나 패치 파일이 손상되었을 수 있습니다.')
        return 1
    print(f'\n완성: {dst}')

    if args.sd:
        sd = os.path.join(args.sd + os.sep, 'wiiu', 'sdcafiine', man['title'], man['mod'], 'content')
        os.makedirs(sd, exist_ok=True)
        shutil.copyfile(dst, os.path.join(sd, 'data000.cpk'))
        ok = md5(os.path.join(sd, 'data000.cpk')) == man['result']['md5']
        print(f"SD 카드 복사: {sd} {'(확인 완료)' if ok else '(복사 실패!)'}")
    else:
        print('\nSD 카드의 아래 경로에 넣으세요.')
        print(f"  wiiu\\sdcafiine\\{man['title']}\\{man['mod']}\\content\\data000.cpk")
    return 0


if __name__ == '__main__':
    try:
        code = main()
    except Exception as e:
        print(f'\n[오류] {type(e).__name__}: {e}')
        code = 1
    if sys.stdout.isatty() or os.environ.get('SFG_PAUSE'):
        try:
            input('\n엔터를 누르면 창을 닫습니다...')
        except EOFError:
            pass
    sys.exit(code)
