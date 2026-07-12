# Bundled sample VMD motions

The VMD files in `source/` come from the `KAIMyEntity.zip` asset in the
`requiredFiles` release of `Gengorou-C/KAIMyEntity-C`:

- Repository: https://github.com/Gengorou-C/KAIMyEntity-C
- Release: https://github.com/Gengorou-C/KAIMyEntity-C/releases/tag/requiredFiles
- Original archive: `KAIMyEntity.zip`
- Retrieved: 2026-07-12

The author's README states that files inside `KAIMyEntity.zip` may be used
freely, require no credit, may be modified, and may be redistributed. This
provenance file is retained even though attribution is not required.

Mapping from the original archive:

| Local file | Original file |
|---|---|
| `idle.vmd` | `DefaultAnim/idle.vmd` |
| `walk.vmd` | `DefaultAnim/walk.vmd` |
| `run.vmd` | `DefaultAnim/sprint.vmd` |
| `sneak.vmd` | `DefaultAnim/sneak.vmd` |
| `crawl.vmd` | `DefaultAnim/crawl.vmd` |
| `sleep.vmd` | `DefaultAnim/sleep.vmd` |
| `lie_down.vmd` | `DefaultAnim/lieDown.vmd` |
| `fall_down.vmd` | `DefaultAnim/die.vmd` |
| `swim.vmd` | `DefaultAnim/swim.vmd` |
| `climb.vmd` | `DefaultAnim/onClimbableUp.vmd` |
| `swing_weapon.vmd` | `DefaultAnim/swingRight.vmd` |

These motions were made for generic MMD/Minecraft playback and may need
retargeting or cleanup for a particular PMX skeleton. `wave` and `point` use
the right-arm swing as a temporary visible fallback; replace them with proper
VMD motions before production.
