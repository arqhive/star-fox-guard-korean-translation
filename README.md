# 스타폭스 가드 (Wii U) 한글 패치

*Star Fox Guard* (Wii U, 일본판 `WUP-P-BWFJ` / `00050000101BEB00`) 비공식 한국어 팬 패치입니다.
대사는 일본어판 원문을 기준으로 번역했습니다.

**제작: arqhive** · **최신 버전: [v1.1](../../releases/tag/v1.1)**

- 게임 안의 일본어 텍스트 1,529문단을 모두 한글화했습니다(메뉴, 튜토리얼, 스토리 대사, 방해 통신, 도움말, 크레딧).
- 글자는 원본 UI 글꼴 모양에 맞춰 Noto Sans KR 기반으로 새로 그렸으며, MCD 파일마다 전용 글리프 아틀라스를 다시 만들었습니다.
- 그림 속 일본어 2장(프롤로그 계약서, 크레딧 손글씨 서명)을 한글화했습니다.
- 인물·지명은 한국 정식 발매작(스타폭스 2026, 스타폭스 64 3D) 표기를 따릅니다. 폭스 맥클라우드, 팔코 람바디, 페피 헤어, 슬리피 토드, 안돌프, 코네리아 등입니다.

> 이 저장소에는 **게임 데이터(롬·디스크 이미지, 추출한 원문 대사, 그래픽, 스크린샷)가 들어 있지 않습니다.**
> 패치를 만들거나 적용하려면 본인이 소유한 게임에서 직접 덤프한 원본이 필요합니다.

## 사용자용: 패치 적용

### 준비물

- 본인이 덤프해 복호화한 일본판의 `content/data000.cpk`. 북미판·유럽판과 이미 한글 패치한 파일에는 적용할 수 없습니다.
- 윈도우 PC. 배포 ZIP에 python.org의 임베더블 파이썬과 스크립트 패처([`release/patcher/patch.py`](release/patcher/patch.py))가 들어 있어 따로 설치할 것이 없습니다.
- Aroma 환경과 SDCafiine(콘텐츠 리디렉션)을 쓸 수 있는 Wii U, 여유 공간이 약 600MB인 SD 카드(FAT32).

### 적용 방법

1. [배포 페이지](../../releases/latest)에서 `StarFoxGuard_KO_v1.1.zip`을 받아 폴더째 압축을 풉니다.
2. 원본 `data000.cpk`를 `패치하기.bat`에 끌어다 놓습니다. 패처가 원본 MD5를 검사한 뒤 `out` 폴더에 한글판 `data000.cpk`를 만들고, 결과 MD5도 검사합니다. 원본 파일은 바뀌지 않습니다.
3. 결과 파일의 확인값을 아래 표와 비교합니다.
4. 결과 파일을 SD 카드의 `wiiu\sdcafiine\00050000101BEB00\KoreanTranslation\content\data000.cpk`에 넣고, Aroma에서 SDCafiine을 켠 채 게임을 실행합니다.

자세한 방법은 [`README_한국어.txt`](release/README_한국어.txt)를 참고하세요.

### 파일 확인값

| 항목 | 원본 일본판 `data000.cpk` | 패치 적용 결과 (v1.1) |
|---|---|---|
| 크기 | 469,484,032 바이트 | 572,957,184 바이트 |
| CRC32 | `C784C69A` | `A7CCB682` |
| MD5 | `3ba7b1e862cfff770066b5792381c264` | `9181ea49e6b5276b2dc11bda08ec45a5` |
| SHA-1 | `66fc224894138bd54633dc88bf47445ef4e0f81b` | `df5ce1eec0fb34e0a9c47adb0650c11dad0b236d` |

원본 파일 위치: `content/data000.cpk` (타이틀 ID `00050000101BEB00`)

### 실행 환경

- **확인함**: Wii U + Aroma SDCafiine, Cemu.

### 알려진 문제

- 음성은 일본어 그대로입니다.
- 프로필 심벌 아이콘의 한자(零·技·侍·秘·戦·忍)는 디자인 요소로 보고 남겼습니다.
- 온라인 기능은 서비스 종료로 확인하지 못했습니다.

## 개발자용: 직접 빌드

### 요구 사항

- Python 3.10 이상, [Pillow](https://pypi.org/project/pillow/), [NumPy](https://pypi.org/project/numpy/), [openpyxl](https://pypi.org/project/openpyxl/). 그림을 다시 만들 때는 [opencv-python](https://pypi.org/project/opencv-python/)도 필요합니다.
- 복호화한 일본판 게임 폴더(`code/`, `content/`, `meta/`). 폴더 이름이 `스타폭스 가드 [Game] [00050000101beb00]`이면 저장소 폴더 옆이나 안에 두었을 때 자동으로 찾습니다.
- 한글 글꼴 `C:\Windows\Fonts\NotoSansKR-VF.ttf`.

### 빌드

```bash
python tools/build.py                  # 전체 빌드
python tools/build.py --sd E:          # 빌드 후 SD 카드까지 복사
python tools/build.py --only ui_title.dat
```

결과는 `build/sdcafiine/00050000101BEB00/KoreanTranslation/content/data000.cpk`에 생깁니다.
위 확인값은 v1.1 그림을 반영한 결과입니다. 그림 생성 입력과 재생성 방법은 [`docs/GRAPHICS_V11.md`](docs/GRAPHICS_V11.md)를 참고하세요.

`build.py`는 다음을 수행합니다.

1. `translation/ko/*.json`의 한국어를 MCD 메시지로 다시 기록합니다.
2. 번역에 쓰인 글자로 MCD별 글리프 아틀라스(BC3)를 새로 그리고 심볼·글리프 표를 다시 씁니다.
3. `translation/images_ko/`의 PNG를 원본과 같은 형식(BC1/BC3)으로 다시 인코딩해 텍스처를 교체합니다.
4. DAT 아카이브를 다시 조립한 뒤 CPK의 TOC와 헤더를 고쳐 `data000.cpk`를 다시 씁니다.

### 번역 수정

```bash
python tools/text_tool.py extract      # translation/sfg_text.xlsx에 원문 추출 (원문이므로 커밋 금지)
python tools/tl_tool.py split          # 작업용 묶음 JSON 생성
python tools/tl_tool.py check all      # 태그·줄 수·줄 폭·문자 검사
python tools/tl_tool.py merge          # 검수 결과를 엑셀에 반영
```

- 번역 원본은 [`translation/ko/*.json`](translation/ko)입니다. 키는 `DAT|MCD|메시지번호|문단번호`, 값은 번역문(줄바꿈 `\n`)입니다.
- 용어와 말투는 [`translation/GLOSSARY.md`](translation/GLOSSARY.md)를 따릅니다.
- 문체 규칙은 [`docs/STYLE_GUIDE.md`](docs/STYLE_GUIDE.md)에 있습니다.

### 배포 꾸러미 만들기

```bash
python tools/make_release.py --version v1.1  # 원본과 빌드를 비교해 release/patcher/payload 생성
```

`payload`에는 한글 MCD와 글리프 아틀라스, 그리고 한글로 고친 텍스처에서 달라진 바이트 구간만 담깁니다.
여기에 `release/patcher/`와 임베더블 파이썬을 함께 압축하면 배포용 ZIP이 됩니다.

### 폴더 구조

```
release/       배포용 패처(patcher/), 패치하기.bat, 사용자 설명서
translation/   번역 원본(ko/*.json), 용어집(GLOSSARY.md)
tools/         CPK·DAT·MCD 읽기·쓰기, 번역 추출·검사, 빌드·배포 도구
docs/          파일 형식, 그래픽 작업 기록, 문체 규칙, 릴리즈 노트 사본(docs/releases/)
```

### 기술 문서

- CPK·DAT·MCD·텍스처 형식은 [`docs/FORMATS.md`](docs/FORMATS.md)에 정리했습니다.
- v1.1 그림 개선 과정은 [`docs/GRAPHICS_V11.md`](docs/GRAPHICS_V11.md)에 있습니다.

## 변경 내역

전체 내역은 [`CHANGELOG.md`](CHANGELOG.md)에 있습니다.

## 크레딧·라이선스

- 이 저장소의 도구 코드, 한국어 번역문, 문서: [MIT License](LICENSE) (© 2026 arqhive).
- 한글 글리프는 [Noto Sans KR](https://fonts.google.com/noto/specimen/Noto+Sans+KR)(SIL Open Font License 1.1)로 그렸습니다.

## 면책

비공식 팬 번역이며 Nintendo, PlatinumGames와 관련이 없습니다. 「스타폭스 가드」 관련 상표·저작권은 Nintendo에 있습니다.
패치를 적용한 게임 파일의 배포를 금지합니다.
