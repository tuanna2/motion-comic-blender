# Series registry and AI story creation

`series/urban_mystery/series.json` defines the first fixed cast for the series
**Ký Ức Sau Nửa Đêm**. Character assets are marked `planned`: the identity,
palette, voice, and writing constraints are stable, but production PNG layers
still need to be drawn or generated later.

| ID | Character | Function | Primary color | Edge-TTS profile |
|---|---|---|---|---|
| `char_minh_khang` | Minh Khang | protagonist / first-person narrator | navy blue | NamMinh, `+1%`, `-2Hz` |
| `char_an_nhien` | An Nhiên | ally / slow romance | warm rose | HoaiMy, `+5%`, `+3Hz` |
| `char_tran_vu` | Trần Vũ | rival / ambiguous antagonist | wine red | NamMinh, `-9%`, `-14Hz` |
| `char_ba_hanh` | Bà Hạnh | mentor / secret keeper | olive | HoaiMy, `-14%`, `-12Hz` |
| `char_le_huyen` | Lệ Huyền | mysterious wildcard | violet | HoaiMy, `-5%`, `-6Hz` |

Vietnamese currently has two standard Microsoft neural voices. Rate, volume,
and pitch create five deterministic profiles without referencing nonexistent
voice IDs. Dialogue and narration profiles are stored separately.

## Local prompt UI

```bash
python3 scripts/story_creator_ui.py
```

Open `http://127.0.0.1:8765`. The UI can:

- display the fixed cast and voices;
- choose a 10-30 minute target;
- select first- or third-person narration;
- select the protagonist, genre, and episode premise;
- generate and copy a complete AI prompt;
- paste the AI JSON result;
- validate IDs, narration mode, duration, and story length;
- download a valid `story_source.json`.

The server binds to localhost by default and uses only the Python standard
library.

## CLI prompt generation

```bash
python3 scripts/generate_story_prompt.py \
  --minutes 15 \
  --narration-mode first_person \
  --protagonist char_minh_khang \
  --genre "đô thị, bí ẩn, trùng sinh" \
  --premise "Minh Khang tỉnh lại trước ngày vụ cháy xảy ra" \
  --output output/story_prompt.txt
```

Copy `output/story_prompt.txt` into ChatGPT or another LLM. Paste the returned
JSON into the UI, or save it and validate from the CLI:

```bash
python3 scripts/check_story_source.py output/story_source.json
```

## Output contract

The AI returns one JSON object containing the complete TTS-ready story:

```json
{
  "version": "1.0",
  "series_id": "urban_mystery",
  "title": "Tên truyện",
  "narration_mode": "first_person",
  "narrator_character_id": "char_minh_khang",
  "estimated_minutes": 15,
  "characters_used": ["char_minh_khang", "char_an_nhien"],
  "logline": "Tóm tắt một câu.",
  "full_story_text": "Toàn bộ nội dung dùng cho TTS..."
}
```

This stage creates source fiction, not timestamps or a final storyboard. The
next compiler will split `full_story_text` into attributed utterances, create
TTS, and derive the exact visual timeline.
