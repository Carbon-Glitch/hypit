# Asset plan: reusable references before shot images

Read this when turning a Brief, Treatment or reversed script into the images a production needs.
It separates the two kinds of generated images and fixes their order: **reusable reference assets
first, shot images bound to them after**.

Have the [designated 当前Agent writer](document-writing.md) author asset direction and image prompts
as one production writing batch using actual accepted geometry/identity constraints. GPT generates,
inspects and binds the images, records their true state and returns creative defects in one grouped
feedback pass. A planned prompt is not an accepted asset. Use built-in Codex imagegen first. On actual tool error, unavailability, timeout or no usable image, continue through the already authorized [OpenRouter Nano Banana 2.1 fallback](../production/image-generation-fallback.md) with the same prompt and actual references; default 2K. Inspect the returned candidate before accepting it.

## Two kinds of images, two different jobs

- **Reference assets (参考资产)** — character 定妆照, scene base views, key prop images. Their job is
  to carry identity and continuity. They are few, individually reviewed, explicitly accepted, and
  then reused across many shots and Builds.
- **Shot images (镜头画面/关键帧)** — a shot's first frame, last frame or keyframe. Their job is to
  serve one shot's start→end state. They are consumed where they are used and bind the accepted
  assets as references; they do not establish identity on their own.

An asset list that reads like a storyboard — one image per shot, each re-describing the character —
is a symptom that this step was skipped. Every shot image then re-invents the person, the place and
the props, and consistency is left to luck. [Reference relationships](../playbooks/craft/generated-dependencies.md)
owns how a finished asset carries its facts into later pictures; this page owns deciding which
assets must exist before finished production shot images are requested. Rough sketches and proxy
layouts may precede them for scene planning; they are not accepted identity assets.

## Identity, variant, transient and persistent relation

Before creating an image, separate what makes this the same entity from what merely changes:
identity → reuse the master; costume/injury/open state → derive only the needed variant; pose/gaze/
camera position → own it in the shot, not a new identity asset. A sustained body-object-space relation
(support, restraint, carrying weight, occupied seat) persists until the story changes it; preserve it
at both shot boundaries. Track an independently recognizable object as an asset when needed.

After composing a start image, re-read the visible people/place/props and their states, then bind actual
references. Do not rely solely on the initial inventory. Freeze only the start instant: end-only text,
reveals, contact results or damaged states must not leak into it. Store these decisions in existing
ASSETS/shot rows, without another extraction or coverage table.

## Build the inventory from the script

Before creating a reference, name its downstream consumer and the uncertainty it removes. Record
its production job, allowed/excluded controls, reuse scope and acceptance evidence beside its ID.
Keep the [four-panel character master and on-demand location assets](drama-reference-sheets.md). For a recurring spatially constrained location, start with one accepted 3/4 overview. Add only the camera/state views actually consumed; a nine-panel sheet is optional. Ordinary one-shot backgrounds and non-narrative dressing need no standalone asset. Separate
reusable masters, scene controls, shot-boundary/action controls and the actual submission selection;
these are responsibilities, not four mandatory folders or image quotas.
Use the [director blueprint](director-blueprint.md) to allocate by actual shot duty and risk:
composition/depth/reveal, native close-up, contact pose, local light/material, temporal acting,
camera/rhythm and voice may need different carriers. Do not assume a master portrait or mother
scene view controls them all. Prepare a temporal/audio reference only for a verified route/use;
otherwise keep it as planning evidence and test text-directed execution honestly.

For reference grids, staging maps and palette cards, exclude panel borders, arrows, typography,
swatches and neutral backgrounds from final imagery unless intentionally part of the piece.
Use a clean shot image where a single-frame operation requires one; a storyboard grid is not an
automatic sequence control. Reject/anti-reference examples belong to review evidence, never an
unqualified positive input. [Director contracts](../production/director-contract.md) adds frozen
action topology, embodied POV and semantic-color control when applicable.

Derive `ASSETS.md` from target DESIGN/existing character and look owners plus the full STORYBOARD (and a literary story body when used), informed by
canonical source-shot table detail duties when adapting. Treatment links those owners and explains design choices:

- **Characters** — one accepted identity anchor and a single four-panel front/profile half-body
  and front/back full-body master for each production character. Add derived angles and
  performance coverage when the shot table needs them; add a look/state variant when the story
  changes costume, hairstyle, injury or transformation. A new look is not a new person. Keep stable
  identity wording separate from the current look and momentary state.
- **Locations** — one useful 3/4 overview for recurring geography, with named camera/state variants only where needed. Keep the accepted layout, scale, fixed anchors and light coherent. Use a multiview/nine-panel sheet only when its views are consumed; it is not proof of shared 3D geometry.
- **Props** — only props whose identity or state carries story (the letter, the phone, the chipped
  mug). Set dressing stays inside scene views.

A workable row shape:

| ID | Kind | Name | Continuity lock (verbatim) | Used by | Status |
| --- | --- | --- | --- | --- | --- |
| CHR-01 | character | 女主·林晚 | a Chinese girl in her late twenties, … | SHOT-03…27 | accepted |
| LOC-02 | location | 旧团部办公室 | … | SHOT-02…07 | generated |
| PRP-01 | prop | 缺口搪瓷茶缸 | chipped white enamel mug | SHOT-02, 07 | planned |

Status runs `planned → generated → accepted`. Only `accepted` assets may be bound into shot work.

Acceptance covers the actual intended role: [spatial continuity](../production/spatial-continuity.md)
requires per-panel geometry and a camera/state-specific input consistency check. An identity-only
image may still contain an incompatible background or pose; remove/derive/test that conflict before
batching rather than relying on a deny clause. Current selected versions and effective facts reach
the [current shot and execution records](../production/short-drama-production.md), not just the asset ledger.

## A character is a dossier, not a photo

A single front-facing portrait cannot hold a character through a production. A production character's
accepted dossier contains the required four-panel sheet and:

- **the anchor portrait** — the 定妆照 everything else derives from; every later angle or expression
  is generated *from this image*, not independently;
- **angle and expression coverage** — the views and registers the shot table actually needs
  (three-quarter/profile and the source's specific mouth, eyes, brow, posture and intensity),
  derived from the anchor. Do not replace particular performances with a fixed generic emotion set;
- **same-plane scale figures** — for scenes where characters share the frame, one standing figure
  that fixes their relative heights and builds; "taller" in a prompt asserts, this demonstrates;
- **the identity description** — concise, stable wording grounded in the accepted appearance:
  age/casting facts, facial structure, build and distinguishing features actually present. Reuse
  it for the same identity version; no arbitrary word count or required mole/scar. Do not invent
  landmarks to satisfy a template. Exclude current costume, expression, props and hairstyle
  changes; those belong to the look or shot state. Mark transformations as explicit variants;
- **a voice reference** — a short clean accepted sample used to guide vocal identity; verify its
  binding and audible result rather than claiming a sample guarantees consistency. See
  [shot blocks](../production/shot-blocks.md#choose-the-sound-and-performance-path);
- **look and momentary state** — a named, versioned outfit/hair/accessory combination owns its
  layer colors and materials. Wetness, tears, injury progression and held props belong to the
  current shot state. CHR-01 can retain identity while LOOK-school-v1 becomes LOOK-stage-v1 at an
  established costume change. Only the current look applies to that request.
- **reference preparation** — preserve the visual information the input is meant to control. Crop,
  normalize or mask only to solve an observed problem, keeping originals and verifying processed
  media. Blanket blur/level flattening can erase expression, texture and atmosphere. A face masked
  beyond readable eyes/mouth cannot be declared an expression reference.
- **identity-mechanism choice** — record what the selected services actually support. If repeated
  identity failures remain, assess better views/composites and any supported image-side technique
  against a representative sample and its setup cost; no universal shot count triggers training.
  This never changes the RunningHub H3-only video restriction or authorizes new spending.

Master assets carry long-term identity; look variants carry intentional appearance changes; shot
states come from scene design and the predecessor's adopted edit boundary. Label each input's
authority: an old outfit reference may supply the face only while the current look supplies clothing.
Prefer a corrected combined reference when the endpoint cannot reliably separate those roles.

## Direct assets for reuse, not for drama

### Derive location lighting without rewriting identity

For a scene that genuinely needs a lighting-adapted reference, reuse accepted identity/look,
scene/camera layout and the actual VISUAL/palette version. Then:

1. Select the relevant source, world-space light direction/softness/color and subject position;
   project it into this camera, including shadow, reflection and contact where meaningful.
2. Give the designated writer the real inputs, allowed light/material changes and protected face,
   costume, scale/state and reveal facts. Derive a scene-look or integrated shot candidate; do
   not relight every master or create variations with no shot consumer.
3. Compare candidate to its identity/wardrobe owner and environment: face, skin, hair/fabric,
   body scale, exposure, direction, occlusion and contact share this scene. A white backdrop
   relight alone does not prove final integration; quality failure cannot justify identity change.
4. Keep the reusable master and derived version/role separately in ASSETS, select only appropriate
   actual inputs, and use a representative H3 passage when motion/turning/occlusion remains unknown.

Character masters retain four panels; location overviews, current-state images and optional multiviews follow actual consumers. Clean single cells,
integrated compositions or derived light references serve current H3 duty; another model's
headless-body convention and post upscale do not establish usable facial/space detail.

### Reusable assets and performance references



For cinematic work, apply [photographic look development](cinematic-look.md) to the production
scene/shot images. Neutral identity sheets may retain their reuse-friendly appearance; derive actual
location-lit frames from them rather than transplanting their studio lighting everywhere. Inspect
skin/makeup, hair, costume material, foreground/background depth and contact at intended output size.
An accepted identity is not automatically an accepted photographic look. Do not add blemishes or
alter a face to claim realism. A low-poly layout or scene-empty plate cannot alone pass the integrated
cinematic frame gate.

Assets serve future pictures, so their direction differs from a shot's:

Identity masters establish a stable person; performance references intentionally carry particular
expressions, poses or action phases. Keep their roles separate so neutral identity preparation does
not neutralize the performance pack. Derive the pack from source detail requirements: expression
onset/peak/release, distinctive gait/posture, contacts and reaction coverage as needed. For complex
contact, settle both bodies, scale, support points and hand/prop relationships in a readable composition
before video. A still cannot establish a movement's unfolding; use a suitable temporal reference or
precise phase direction through the verified RunningHub inputs.

Link each performance/contact/effect reference to the detail IDs it can support and state its limits.
Accept a reference for the face/action readability and intended register, not just identity likeness.
An atmosphere reference needs relevant light/material/background or sound characteristics, not only
an empty location label. Only make assets that the actual scene needs.

Use [reference scopes](../production/reference-scopes.md) for explicit input order, actual app role,
allowed control and excluded carryover. Inspect the finished shot image to identify every visible
character/look, location/view and relevant prop/state that needs accepted visual support; a planned
asset list may miss someone introduced while composing. A generic no-text instruction cannot erase
an intentional readable proof item; surface text treatment follows the authored reveal requirement.

- A scene base view includes the spatial anchors its shots will need — the doorway a character
  enters through, the window the light comes from — even when the base view itself never appears
  in the final video.

## Current state is a separate reference duty

For consequential cross-cut space/hand/prop state, use [scene continuity](../production/spatial-continuity.md). View selected pixels, record visible state facts in the existing image review, then choose current inputs. An intact chair in an old positive reference conflicts with the required overturned chair even if text says to ignore it; repair/crop/remove that image. Capture actual adopted result frames, not discarded tails. Keep original geometry plus state changes as the derivation source.

## Order of work

1. Reconcile inventory and cost with the existing scope and spending agreement; ask only when a
   meaningful choice or spending outside that agreement remains unresolved.
2. Generate and review assets. Acceptance is a decision, not an event: judge each asset against its
   lock and its reuse job; repair or regenerate before it enters shot work.
3. Write shot images against accepted assets: bind them as reference inputs, cite the lock phrase
   verbatim, and let the prompt concentrate on the shot's new action and viewpoint.
4. When a shot drifts, inspect the master, selected look, binding and output. A correct master does
   not become wrong because a generation ignored it. Repair the **asset** when its intended facts
   are wrong; repair the binding, request or **shot** when those caused the failure.

For MiniMax H3 targets, accepted assets become the `<Subject N>` / `<Picture N>` definitions in the
Ref2VA rewrite — the asset ledger is where their labels and reference roles come from
([H3 prompt format](../playbooks/craft/h3-prompts.md)).

## Keep the ledger current

`ASSETS.md` tracks status, accepted Run Candidate, consumers and mother-sheet/panel/derived-input
relationships. Record each sheet's panel duties, look/location state and current palette version;
inspect both every panel and the full sheet, then inspect any extracted clean input.
Record the accepted file/version or content hash and acceptance evidence. Revising it marks consuming
shots for recheck; preserve those still correct and re-derive affected ones. Planned, generated and
accepted remain distinct. Preserve accepted Outputs through Run Candidates like other work.

## Voice and sound assets serve a directing duty

Follow [sound direction](sound-direction.md). CHARACTERS owns accepted vocal identity and
the line-specific tactic lives in the current story/dialogue owner and STORYBOARD. ASSETS records actual voice samples,
dialogue recordings, cue/score files and their allowed/excluded duties, consumers, version and
heard acceptance. A sample is not automatically a soundtrack; a scratch track is not final.
Reference samples can come from accepted supplied/recorded/H3 media or configured authorized
audio preparation. Keep actual input binding and resulting speech acceptance separate.
