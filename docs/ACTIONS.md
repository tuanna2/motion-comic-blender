# Semantic action system

Storyboards may use `action` instead of the older `preset` field. The action
catalog contains 306 keys across locomotion, poses, gestures, interactions,
dialogue, emotions, thinking, fights, daily activity, motion-comic simulation,
camera moves, effects, and backward-compatible specialized presets.

```json
{
  "target": "hero",
  "action": "punch",
  "start": 1.2,
  "end": 2.5,
  "params": {"with": "rival", "recoil": 1.0}
}
```

Print the exact current catalog for an LLM prompt or external editor:

```bash
python3 scripts/list_actions.py
python3 scripts/list_actions.py --format json
python3 scripts/list_actions.py --format markdown
python3 scripts/list_actions.py --category fight --format json
```

## Common parameters

- `distance`: horizontal movement or interaction reach
- `height`: jump/climb height
- `cycles`: repeated gesture, shake, or walk cycles
- `return`: return to the starting pose at the end
- `with`: second character/object for interaction and fight actions
- `recoil`: distance applied to the second target after impact
- `follow` / `focus`: target ID for camera actions
- `target` / `listener`: character ID for `face_target`
- `color`, `size`, `text`: optional effect overlay overrides

## Character facing

MMD characters rotate their scene root instead of mirroring the mesh. The
turn is held by default, so later walking and acting preserve the new heading.

```json
{
  "target": "hero",
  "action": "face_target",
  "start": 0,
  "end": 0.45,
  "params": {"target": "friend", "hold": true}
}
```

`turn_left`, `turn_right`, and `turn_around` accept `degrees`, `direction`, and
`hold`. The episode compiler generates paired `face_target` motions for visible
dialogue. In scenes with more than two characters, set `speech[].listener` so
the intended pair is unambiguous.

Subtitles are camera-space overlays. Camera pan, shake, tilt, and zoom therefore
do not move or resize the text.

## Motion-comic fight composition

Fight handlers use the economical 2D sequence:

1. wind-up pose
2. fast root/limb position shift
3. impact frame and optional screen flash
4. second-target recoil
5. settle pose

This is intentionally sprite-driven rather than full skeletal combat. Add
`camera_shake`, `impact_flash`, `reaction_pop`, and an on-screen text element
to increase impact without generating extra animation frames.

## Interaction convention

Actions involving another entity use `params.with`:

```json
{
  "target": "hero",
  "action": "help_up",
  "start": 2,
  "end": 3.5,
  "params": {"with": "friend"}
}
```

The current MVP animates reach, pose, root displacement, and recoil. Permanent
prop ownership transfer and hand IK are intentionally deferred to a future
attachment-event system.

## Effects

Symbol effects such as `question_mark`, `exclamation_mark`, `anger_mark`, and
`speed_lines` are generated procedurally and follow the target. Screen flashes
and character auras are also procedural. `blush_overlay` and `tear_stream` use
the character's face layers. `screen_blur`, `freeze_frame`, and `slow_motion`
currently use deterministic approximations and do not retime audio.
