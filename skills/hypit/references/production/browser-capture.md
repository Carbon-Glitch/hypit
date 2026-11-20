# Capturing story screens and authored graphic assets

Use this only when the storyboard needs a readable message, evidence display or authored title/effect asset. The full target storyboard owns what is revealed and when; the saved image or rendered layer owns its actual pixels. Existing accepted assets are reused.

## Capture a screen or local graphic

Use the available browser/capture path to save the specific story-required state. If the installed Distribution provides the existing capture interface, these are examples:

```bash
hypit capture screenshot ./assets/story-message.html \
  --viewport 540x960 --scale 2 --to assets/story-message.png

hypit capture screenshot ./assets/title-card.html \
  --viewport 1080x300 --transparent --to assets/title-card.png
```

Use actual supplied text, precise font resources and the accepted palette. Make the required clue readable at the final shot's scale without revealing later information. Open the saved file and inspect the glyphs, intended state, crop and alpha; a successful command alone does not prove the image suits the shot. Check the locally installed help before using interface options.

An exact text/screen asset enters H3 through the existing image asset route when it belongs physically in the scene. Its perspective, contact, reflections and occlusion must fit the actual shot. A precise screen-space graphic or title instead enters [post production](editing-and-finishing.md#图形艺术字与调色) as an accepted image or rendered transparent layer; use the existing HyperFrames path for animation.

## Place and verify

Keep the actual file with project assets and record its story role in the existing asset entry. Preserve the adopted frame's perspective and spatial state; use [media placement](media-presentation.md) or the current EDIT overlay interface. Source time and final display time remain distinct.

Inspect the final composite at delivery size: legibility, reveal timing, position, perspective/occlusion, color, alpha and whether it hides faces or important action. Adjust only the affected graphic or shot. No new document or capture task is required when existing material already meets the story need.
