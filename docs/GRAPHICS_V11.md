# 그래픽 개선 v1.1

내장 ImageGen 도구로 서명과 계약서 서명 영역을 편집했습니다. 생성 원본은 `translation/images_source/`에 보관합니다. 계약서는 1024×1024로 크기를 맞춘 뒤 `(180,650)–(590,756)` 영역만 가장자리 8px를 부드럽게 합성합니다. 이 영역 밖의 기존 한글 이미지 픽셀은 보존합니다. 크레딧은 투명한 생성 서명을 원본 점유 영역에 맞춰 512×128 RGBA 텍스처에 배치합니다.

재생성: `node tools/prepare_graphics_v11.cjs` (Node.js와 sharp 필요). 이후 `python tools/build.py`로 전체 패치를 빌드합니다. `build.py --only`는 원본 CPK를 기준으로 부분 빌드하므로 완성된 전체 한글 패치를 갱신할 때 사용하지 않습니다.

기존 `img_contract.py`, `img_credit_sign.py`는 v1.0 이미지 생성 코드입니다. v1.1 그래픽을 만들 때는 위 준비 스크립트를 사용합니다.

원본 게임 데이터와 편집된 게임 이미지는 기존 저장소 정책대로 커밋하지 않습니다. 생성 입력은 로컬 작업 폴더에 보존됩니다.

## 적용 및 검증

- 최종 PNG: `translation/images_ko/ui_msg_firsttime.dat/msg_firsttime_000.png`, `translation/images_ko/ui_credit.dat/credit_003.png`
- 기존 전체 한글 CPK에 그림만 갱신: `python tools/rebuild_graphics.py 기존한글.cpk --out 새한글.cpk`
- 최종 CPK: `build/sdcafiine/00050000101BEB00/KoreanTranslation/content/data000.cpk`
- 배포 파일: `release/StarFoxGuard_KO_v1.1.zip`
- 결과 MD5: `9181ea49e6b5276b2dc11bda08ec45a5` (572,957,184 바이트)
- 기존 v1.0 CPK·PNG·payload 백업: `build/graphics_review/backup_v10/`
- CPK 전체 비교: `ui_credit.dat/credit.wtp`, `ui_msg_firsttime.dat/msg_firsttime.wtp` 두 항목만 변경. 메시지·폰트와 나머지 데이터는 바이트 단위 동일.
- 계약서 수정 영역 밖 픽셀, 크레딧 알파·빈 영역, PNG 재인코딩과 CPK 내 텍스처 일치 확인.
- 원본 게임 파일에 배포 패처를 적용해 결과 MD5 일치 확인. ZIP CRC 검사 통과.
- 실기 실행은 이 작업에서 수행하지 않음.
- 비교 이미지: `build/graphics_review/before_after_v11.png`
- 검증 결과: `build/graphics_review/validation_v11.json`

## 크레딧 서명 프롬프트

Use case: text-localization. Asset: transparent handwritten Korean signature for a Wii U game texture. Reference image is the original Japanese signature, only a reference for spontaneous hand-drawn marker style, NOT text to retain. Create a single standalone Korean handwritten signature with EXACT text "그리피 토드" (five Hangul syllables: 그 리 피, space, 토 드). Genuine quick natural Korean handwriting, thick felt-tip pen with modest variation of pressure, baseline and character angle, subtly rough ink edges, lively slightly right-leaning strokes. Readable syllables, no extra marks or extra letters. Pale pink-white marker fill (#ffe4e4), thin bright red outline (#eb1414) matching the original. A single slender energetic underline rising gently from lower left to right, tapered at both tips. Keep the letters bold enough for a final 305 by 105 pixel footprint. Signature and underline all inside frame with generous transparent margins. True transparent background and no paper, no checkerboard, no rectangle or shadow. Horizontal single line. No typeset font, no geometric sans-serif, no extravagant calligraphy loops. Output only the signature asset.

## 계약서 프롬프트

Use case: precise-object-edit / text-localization. Edit target image 1: existing Korean game contract texture, 1024x1024. Supporting style reference image 2: handwritten Korean signature. Change ONLY the signature region of the contract (roughly x=220..582 y=665..752). Preserve EVERYTHING ELSE exactly, including all Korean text in title and body, paper, green border and rules, size, position, black unused padding on right and bottom. Replace the existing thin typeset gray signature with a natural handwritten signature reading exactly "그리피 토드" in warm dark gray-brown ink, matching the lively irregular handwritten letter forms from image 2 but without red outline and WITHOUT the swoosh underline (the contract already has a green rule). Make the signature about x=229..482 and y=682..744, dark enough and substantially thicker than before, with subtle felt-tip ink texture and natural stroke variation. No extra letters. Also clean the leftover dark Japanese ink marks contaminating the red stamp at x=476..580 y=666..742; preserve/reconstruct the existing red stylized stamp design and its fine red contours, printed directly on the same aged paper. Do not redesign the stamp. Restore natural aged paper where old gray lettering was removed. No change outside this small signature/stamp area. Flat front-on exact same game texture, no mockup, no new text.
