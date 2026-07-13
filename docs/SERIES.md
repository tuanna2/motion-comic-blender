# Series registry and AI story creation

`series/urban_mystery/series.json` defines the first fixed cast for the series
**Ký Ức Sau Nửa Đêm**. Each character now resolves to a versioned MMD
manifest. The starter manifests reuse the compiled learning model with
different tint/scale values; final production PMX files can replace them
independently without changing IDs.

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
- download a valid `story_source.json`;
- create a second prompt for a compact `episode_plan.json`;
- compile the plan into a complete MMD storyboard;
- monitor frame progress and live logs, cancel, and resume render jobs.

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

This first stage creates source fiction. The second AI prompt returns scenes,
locations, attributed speech and visual beats. `motion_comic.compiler` then
adds the registered MMD asset refs, Edge-TTS profiles, scene templates,
auto-layout, estimated speech timing, camera defaults and expanded action
recipes. Edge-TTS remains the authority for the actual audio and lip-sync.

Five reusable spaces ship with the series: `urban_alley`, `apartment`,
`office`, `temple`, and `lakeside`. They render floor, horizon, back wall,
accent geometry and MMD lighting instead of a single background color.

```bash
python3 scripts/compile_episode.py examples/production/episode_plan.json \
  --output output/production/storyboard.json
```
