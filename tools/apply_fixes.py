"""out_*.json 안의 특정 id 번역을 덮어쓰기 (검수 수정용). python apply_fixes.py fixes.json"""
import json, glob, sys, os
WORK = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'translation', 'work')
fixes = {int(k): v for k, v in json.load(open(sys.argv[1], encoding='utf-8')).items()}
done = set()
for p in sorted(glob.glob(os.path.join(WORK, 'out_*.json'))):
    items = json.load(open(p, encoding='utf-8')); ch = False
    for it in items:
        if it['id'] in fixes:
            it['ko'] = fixes[it['id']]; done.add(it['id']); ch = True
    if ch:
        json.dump(items, open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('applied', len(done), 'missing', sorted(set(fixes) - done))
