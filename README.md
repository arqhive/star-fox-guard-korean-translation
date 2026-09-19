# 스타폭스 가드 한글 패치

*Star Fox Guard* (Wii U, 일본판 `WUP-P-BWFJ` / `00050000101BEB00`) 비공식 한국어 팬 패치입니다.
대사는 일본어판 원문을 기준으로 번역했습니다.

**제작: arqhive**

- 게임 내 일본어 텍스트 전체 한글화 (1,529문단 — 메뉴, 튜토리얼, 스토리 대사, 방해 통신, 도움말, 크레딧)
- 글자는 원본 UI 글꼴 모양에 맞춰 새로 그려 넣음 (Noto Sans KR 기반, MCD 전용 글리프 아틀라스 재생성)
- 그림 속 일본어 2장 한글화 (프롤로그 계약서, 크레딧 손글씨 서명)
- 인물·지명은 한국 정식 발매작(스타폭스 2026, 스타폭스 64 3D) 표기 기준 — 폭스 맥클라우드, 팔코 람바디, 페피 헤어, 슬리피 토드, 안돌프, 코네리아
- 확인 환경: 실기 Wii U + Aroma SDCafiine (부팅·프롤로그·미션 진행 확인)

> 이 저장소에는 **게임 데이터(CPK, 추출한 원문 대사, 원본 텍스처)가 들어 있지 않습니다.**
> 패치를 만들거나 적용하려면 본인이 소유한 게임에서 직접 덤프·복호화한 원본이 필요합니다.

## 사용자용: 패치 적용

[릴리즈](../../releases)의 `StarFoxGuard_KO_vX.Y.zip`을 받아 압축을 풀고, 원본 `data000.cpk`를
`패치하기.bat`에 끌어다 놓으면 한글판 `data000.cpk`가 만들어집니다. 자세한 내용은
[`release/README_한국어.txt`](release/README_한국어.txt)를 참고하세요.

패키지에는 python.org의 임베더블 파이썬이 들어 있어 별도 설치가 필요 없고,
패치 프로그램은 읽을 수 있는 스크립트([`release/patcher/patch.py`](release/patcher/patch.py))입니다.

| 원본 (일본판) | 값 |
|---|---|
| 파일 | `content/data000.cpk` |
| 크기 | 469,484,032 바이트 |
| MD5 | `3ba7b1e862cfff770066b5792381c264` |

| 패치 적용 결과 | 값 |
|---|---|
| 크기 | 572,957,184 바이트 |
| MD5 | `ea030fba2d0b6a75b511b197c84970a8` |

적용 후 SD 카드의 아래 경로에 넣고 Aroma에서 SDCafiine(콘텐츠 리디렉션)을 켜면 됩니다.

```
wiiu\sdcafiine\00050000101BEB00\KoreanTranslation\content\data000.cpk
```

### 알려진 제한
- 음성은 일본어 그대로입니다.
- 프로필 심벌 아이콘의 한자(零·技·侍·秘·戦·忍)는 디자인 요소로 보고 남겼습니다.
- 온라인 기능은 서비스 종료로 확인하지 못했습니다.

## 개발자용: 직접 빌드

### 요구 사항
- Python 3.10 이상, [Pillow](https://pypi.org/project/pillow/), [NumPy](https://pypi.org/project/numpy/), [openpyxl](https://pypi.org/project/openpyxl/), [opencv-python](https://pypi.org/project/opencv-python/)(그림 재생성 시)
- 복호화한 일본판 게임 폴더 (`code/`, `content/`, `meta/`) — 저장소 폴더 옆이나 안에 두면 자동으로 찾습니다
- 한글 글꼴: `C:\Windows\Fonts\NotoSansKR-VF.ttf`

### 빌드

```bash
python tools/build.py                  # 전체 빌드
python tools/build.py --sd E:          # 빌드 후 SD 카드까지 복사
python tools/build.py --only ui_title.dat
```

결과는 `build/sdcafiine/00050000101BEB00/KoreanTranslation/content/data000.cpk`에 생성되며,
위 "패치 적용 결과" 해시와 바이트 단위로 같습니다.

`build.py`가 하는 일:

1. `translation/ko/*.json`의 한국어를 MCD 메시지로 다시 기록
2. 번역에 쓰인 글자를 MCD별 글리프 아틀라스(BC3)로 새로 그려 심볼·글리프 표를 재작성
3. `translation/images_ko/`의 PNG를 원본과 같은 형식(BC1/BC3)으로 다시 인코딩해 텍스처 교체
4. DAT 아카이브 재조립 후 CPK의 TOC·헤더를 고쳐 `data000.cpk` 재작성

### 번역 작업

```bash
python tools/text_tool.py extract      # translation/sfg_text.xlsx 에 원문 추출 (원문이므로 커밋 금지)
python tools/tl_tool.py split          # 작업용 묶음 JSON 생성
python tools/tl_tool.py check all      # 태그·줄 수·줄 폭·문자 검사
python tools/tl_tool.py merge          # 검수 결과를 엑셀에 반영
```

- 번역 원본: [`translation/ko/*.json`](translation/ko) — 키는 `DAT|MCD|메시지번호|문단번호`, 값은 번역문(줄바꿈 `\n`)
- 용어·말투: [`translation/GLOSSARY.md`](translation/GLOSSARY.md)
- 문체 규칙: [`docs/STYLE_GUIDE.md`](docs/STYLE_GUIDE.md)
- 파일 형식 정리: [`docs/FORMATS.md`](docs/FORMATS.md)

### 배포 꾸러미 만들기

```bash
python tools/make_release.py --version v0.9   # 원본과 빌드를 비교해 release/patcher/payload 생성
```

`payload`에는 한글 MCD·글리프 아틀라스와, 한글로 고친 텍스처의 달라진 바이트 구간만 담깁니다.
여기에 `release/patcher/`와 임베더블 파이썬을 함께 압축하면 배포용 zip이 됩니다.

## 면책

- 이 저장소와 패치는 닌텐도, 플래티넘게임즈와 무관한 팬 제작물입니다.
- 게임 데이터는 포함하지 않으며, 본인이 소유한 게임의 덤프에만 사용하세요.
- 도구와 패치는 MIT 라이선스로 공개합니다([`LICENSE`](LICENSE)). 번역문의 저작권은 제작자에게 있습니다.
