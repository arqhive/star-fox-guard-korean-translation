"""검수 끝난 번역(엑셀)을 translation/ko/*.json 으로 내보낸다.

키는 `DAT|MCD|메시지번호|문단번호`, 값은 번역문(줄바꿈 \n).
묶음(work/in_NN.json)의 ID 범위를 그대로 파일별로 나눈다.
"""
import glob
import json
import os

import openpyxl

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
XLSX = os.path.join(ROOT, 'translation', 'sfg_text.xlsx')
WORK = os.path.join(ROOT, 'translation', 'work')
KO = os.path.join(ROOT, 'translation', 'ko')
CHUNKS = {'01': 'core_1', '02': 'core_2', '03': 'story',
          '04': 'jamming_tips_profile', '05': 'hud_edit', '06': 'menu_select_result'}

ws = openpyxl.load_workbook(XLSX)['text']
rows = {}
for r in ws.iter_rows(min_row=2, values_only=True):
    rows[r[0]] = (f'{r[1]}|{r[2]}|{r[3]}|{r[4]}', r[8])

for p in sorted(glob.glob(os.path.join(WORK, 'in_*.json'))):
    name = CHUNKS[os.path.basename(p)[3:-5]]
    out = {}
    for it in json.load(open(p, encoding='utf-8')):
        key, ko = rows[it['id']]
        if ko:
            out[key] = ko
    dst = os.path.join(KO, name + '.json')
    json.dump(out, open(dst, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(name, len(out))
