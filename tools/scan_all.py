from cpk_lib import *
import collections, os, time
os.makedirs('../extract/all', exist_ok=True)
out = open('../extract/scan_all.txt', 'a', encoding='utf-8')
done = set(l.split()[2] for l in open('../extract/scan_log_done.txt') if len(l.split()) > 2)
for n in ['data000', 'data001']:
    f, h, toc = open_cpk(f'../../스타폭스 가드 [Game] [00050000101beb00]/content/{n}.cpk')
    for r in toc:
        if r['FileName'] in done or r['DirName'] in ('ui', 'core'):
            continue
        t = time.time()
        d = extract(f, h, r)
        if d[:4] != b'DAT\0':
            out.write(f"{n} {r['DirName']} {r['FileName']} nonDAT {d[:4]}\n"); continue
        try:
            items = parse_dat(d)
        except Exception as e:
            out.write(f"{n} {r['DirName']} {r['FileName']} DATERR {e}\n"); continue
        for nm, x in items:
            e = nm.rsplit('.', 1)[-1]
            out.write(f"{n} {r['DirName']} {r['FileName']} {nm} {len(x)}\n")
            if e in ('mcd', 'bxm', 'uvd', 'sub', 'txt', 'csv', 'xml', 'srt', 'smd'):
                open(f"../extract/all/{r['FileName'][:-4]}__{nm}", 'wb').write(x)
        out.flush()
        print(r['FileName'], round(time.time() - t, 1), flush=True)
out.write('END\n'); out.close()
