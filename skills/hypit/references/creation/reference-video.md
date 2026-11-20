# Reference-media inspection tools

Use when obtaining/probing/transcribing/sampling source media or reopening a specific observation. [Reverse script](reverse-script.md) owns the deliverable; [reference events](reference-events.md) owns reading depth and experience inference. Do not repeat those workflows here.

## Make time visible

Locate an accessible local source; [video downloads](../production/video-downloads.md) handles links. Use actual project paths and the selected executable's current help for available flags. Illustrative existing commands:

```bash
hypit media probe references/drama/source.mp4
hypit transcribe references/drama/source.mp4 --language zh --to references/drama/transcript.json
hypit media boundaries references/drama/source.mp4 --to references/drama/evidence/boundaries.json
hypit media tiles references/drama/source.mp4 --start 6.8 --end 8.4 --every-frame \
  --columns 4 --rows 3 --cell 480 --transcript references/drama/transcript.json \
  --to references/drama/evidence/contact
hypit media cut references/drama/source.mp4 --start 6.2 --end 9.0 --label-time \
  --to references/drama/evidence/contact-with-neighbors.mp4
```

Under [subtitle/visual-first mode](../production/source-audio-policy.md), extract the actual subtitle text/timing first, retaining source/coverage and uncertain words/speakers; transcription is optional supplementation. The transcript must refer to that exact source and clock; choose the spoken language explicitly. Names/coinages require re-listening, and subtitles are not proof of sound. Audio access/selected service resources follow [local tools](../environment/local-tools.md) when needed, not as a universal setup step.

## Choose the sampling needed by the question

- `probe`: duration, dimensions, timebase/stream presence; presence of an audio stream does not prove it was heard.
- `boundaries`: cut proposals, to verify by playback/frame evidence.
- `frames --at` or a range/interval: inspect a specific state; `--every-frame` for a consequential ambiguous short sequence.
- `tile/tiles`: time-labeled overview or paginated dense views. Use `--transcript`, and where supported `--around`, `--padding`, `--occurrence` or `--ranges` to find meaningful passages.
- `cut`: reopen actual motion and sound with enough incoming/outgoing context. A grid cannot settle a pause, delivery or cross-cut rhythm by itself.

First locate the event, then refine time interval and cell size; reopen only uncertainty that matters. Original timestamps matter for variable-rate media. Samples establish sampled moments, not the gaps. Existing evidence can be reused if source/hash/timebase are unchanged; repeated extraction does not increase confidence by itself.

## Preserve a connected account

Keep selected evidence paths/intervals and unresolved facts at their SOURCE_SHOTS/SOURCE_CONTEXT event owners; source context interprets them and links the experience units. Expand TIMELINE only for a genuine cross-shot system. Distinguish the player's controls from content in the film. For target comparison, [snapshots](../production/snapshots.md) captures existing composition; align by meaningful event, not equal source/target seconds.

When a performed action/camera relationship needs temporal control, preserve an appropriate excerpt. Whether it is really submitted to generation is a separate [supported input decision](../playbooks/craft/video-direction.md#let-footage-carry-temporal-behavior-that-matters), not implied by analysis. Current task status belongs in PROGRESS, not another repeated source summary.
