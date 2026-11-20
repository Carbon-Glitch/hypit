# Continuity methods: sources and boundaries

Reviewed 2026-09-29. These sources inform Hypit's direction and execution checks; they are not extra
runtime dependencies or proof of this production's output quality. Recheck service capabilities for
the actual endpoint at production time. Instructions below remain Hypit's own scoped workflow.

| Source | Adopted method | Boundary |
| --- | --- | --- |
| [MiniMax official H3 prompt skill](https://github.com/MiniMax-AI/MiniMax-H3/blob/d21241f0a4b3acbb34c97dae47fa417b7065e438/skills/h3-prompt-writing/SKILL.md) and [full-reference guide](https://github.com/MiniMax-AI/MiniMax-H3/blob/d21241f0a4b3acbb34c97dae47fa417b7065e438/skills/h3-prompt-writing/references/ref-en.txt) | Preserve exact mode syntax; distinguish reference guidance from audio reuse and keyframe relationships | A prompt-writing guide does not document a third-party app's actual inputs or prove lip synchronization |
| [drama-skills identity versus variant](https://github.com/zenstory-ai/drama-skills/blob/4e48ccbf0f77da757d7cacc6937b1cc59c124845/skills/short-drama-assets/references/identity-vs-variant.md) | Separate persistent identity, reusable looks and momentary state; avoid unnecessary variants | Keep Hypit's asset IDs and document ownership; do not import another workflow's confirmation rules |
| [drama-skills generated footage](https://github.com/zenstory-ai/drama-skills/blob/4e48ccbf0f77da757d7cacc6937b1cc59c124845/skills/short-drama-edit/references/generated-footage.md) and [cut craft](https://github.com/zenstory-ai/drama-skills/blob/4e48ccbf0f77da757d7cacc6937b1cc59c124845/skills/short-drama-edit/references/cut-craft.md) | Inspect actual usable ranges and choose meaningful in/out points; compare color in comparable regions | Do not inherit default full-frame color statistics, fixed shot lengths or render limitations |
| [drama-skills quality gates](https://github.com/zenstory-ai/drama-skills/blob/4e48ccbf0f77da757d7cacc6937b1cc59c124845/skills/short-drama-review/references/production-quality-gates.md) | Separate deterministic contradictions, observed story failures and contextual craft preferences | Checks and written acceptance cannot substitute for watching/listening |
| [ViMax reference selector](https://github.com/HKUDS/ViMax/blob/b596ca7793c7ec6346ddcc408a9ed1bc97998152/agents/reference_image_selector.py) | Select relevant current look, camera view and prior scene state instead of accumulating references | Its prompt preferences and reference count are not universal model limits or a tested quality guarantee |
| [Runway Act-Two course](https://academy.runwayml.com/course/character-animation-act-two) | Performance transfer is an available specialist direction for expression and gesture | Course page verified; exact API availability, multi-person support and fit for a particular shot still require verification |

GitHub repositories were searched live through the GitHub API and the cited files downloaded at the
listed commits. Browser search could not start because Tabbit's task-scoped page creation failed.
The separate Runway 3D tutorial fetch failed with an SSL EOF, so no current API claim is based on it.
Composite/3D layout is an optional production method, not an installed or verified service here.

No universal consistency percentage, LoRA training duration, fixed reaction duration or guarantee of
model memory is adopted. Source code and documentation establish methods/capabilities; only accepted
media establishes that they worked for a scene.

## Drama Skills integration, 2026-10-08

Downloaded the full repository at
[c2426e03c0e7722bebcc6a488b6658dc38c65ac3](https://github.com/zenstory-ai/drama-skills/tree/c2426e03c0e7722bebcc6a488b6658dc38c65ac3)
(commit date 2026-10-03). The original MIT license is retained in the source snapshot. Added Hypit
instructions and scope checks are independently authored adaptations; no upstream providers or
eleven-skill installation are required.

| Pinned upstream method | Hypit adaptation |
| --- | --- |
| [Coverage audition](https://github.com/zenstory-ai/drama-skills/blob/c2426e03c0e7722bebcc6a488b6658dc38c65ac3/skills/short-drama-storyboard/references/coverage-audition.md) | Compare genuinely different execution when it matters, within source fidelity and settled creative authority |
| [Audience reveal](https://github.com/zenstory-ai/drama-skills/blob/c2426e03c0e7722bebcc6a488b6658dc38c65ac3/skills/short-drama/references/audience-reveal.md) | Per-fact show/withhold/release, protecting both hidden and required information |
| [Keyframe craft](https://github.com/zenstory-ai/drama-skills/blob/c2426e03c0e7722bebcc6a488b6658dc38c65ac3/skills/short-drama-storyboard/references/keyframe-craft.md) | One declared boundary, with no later facts in the start frame; no universal geometry/word quotas |
| [Reference roles](https://github.com/zenstory-ai/drama-skills/blob/c2426e03c0e7722bebcc6a488b6658dc38c65ac3/skills/short-drama/references/reference-roles.md) | Allowed/excluded control carried into the actual H3 prompt; supported multi-role bindings remain possible |
| [Production shot grammar](https://github.com/zenstory-ai/drama-skills/blob/c2426e03c0e7722bebcc6a488b6658dc38c65ac3/skills/short-drama-storyboard/references/production-shot-grammar.md) | Dominant purpose, executable action/speech budget and complete duration accounting |
| [Shot revision identity](https://github.com/zenstory-ai/drama-skills/blob/c2426e03c0e7722bebcc6a488b6658dc38c65ac3/skills/short-drama-storyboard/references/shot-revision-identity.md) and [pickups/alternates](https://github.com/zenstory-ai/drama-skills/blob/c2426e03c0e7722bebcc6a488b6658dc38c65ac3/skills/short-drama/references/pickup-and-alternate.md) | Stable decisions, predecessor/successor links and repair coverage; pickup is not automatic replacement |
| [Project calibration](https://github.com/zenstory-ai/drama-skills/blob/c2426e03c0e7722bebcc6a488b6658dc38c65ac3/skills/short-drama-review/references/project-calibration.md) and [review method](https://github.com/zenstory-ai/drama-skills/blob/c2426e03c0e7722bebcc6a488b6658dc38c65ac3/skills/short-drama-review/references/review-method.md) | Version-specific observations, disposition before rewriting, bounded change/preserve sets |
| [Generated footage](https://github.com/zenstory-ai/drama-skills/blob/c2426e03c0e7722bebcc6a488b6658dc38c65ac3/skills/short-drama-edit/references/generated-footage.md) and [sound/subtitles](https://github.com/zenstory-ai/drama-skills/blob/c2426e03c0e7722bebcc6a488b6658dc38c65ac3/skills/short-drama-edit/references/sound-and-subtitles.md) | Usable intervals, motivated in/out points, Script wording and actual subtitle timing |
| [Scene handoff capsule](https://github.com/zenstory-ai/drama-skills/blob/c2426e03c0e7722bebcc6a488b6658dc38c65ac3/skills/short-drama-write/references/scene-handoff-capsule.md) and [production recovery](https://github.com/zenstory-ai/drama-skills/blob/c2426e03c0e7722bebcc6a488b6658dc38c65ac3/skills/short-drama-produce/SKILL.md) | Owner-cited resume context and recover before resubmitting a paid task |

Do not import per-attempt confirmation, mandatory reviewer agents, fixed reaction timing/counts,
fixed subtitle geometry, generic frame-statistic color gains or bare model adapters. Preserve the
RunningHub H3-only route, official prompt fields, current spending authority, existing Hypit owners
and original-detail/source-versus-output gates. Any local reaction recipe remains a bounded trial
candidate whose result must be observed, not a universal rule.

## Director Workbench integration, 2026-10-09

Downloaded the full [repository](https://github.com/Phantomlau3674/ai-film-director-workbench/tree/ff4791412231b95550db456b58659c4b17dbc6a4)
at commit `ff4791412231b95550db456b58659c4b17dbc6a4` (2026-07-13). Inspected both skill entrypoints,
production/core protocols, director-dense contracts, asset authoring/handoff methods and generator,
preflight and review-promotion code. This is source analysis, not a generated-film quality benchmark.

Adopted into [director contracts](director-contract.md): explicit control carriers, timed action
feedback, frozen action topology/embodied POV, scope-aware conflicts, representation-layer and
semantic-color boundaries, and reverse-reading final requests. Existing asset/scoped-binding owners
are reused. [MIT notice](workbench-license.md) is retained. The third-party original prompt corpus
is not copied; it is explicitly outside the repository's MIT grant.

Do not import Seedance/Dreamina executors, generic output fields, fixed compact prompt limits,
mandatory background movement or an entire parallel project/schema hierarchy. The upstream's
isolated text generator sends only its profile/spec, but that alone is not an independent multimedia
acceptance process. Some case-method gates are policy-only; do not claim upstream validators enforce
them or that lexical lint proves semantic fidelity.

The earlier exclusion of upstream mandatory reviewer agents describes that integration decision.
The user's subsequent explicit request now adds one [independent director/writer gate](short-drama-production.md)
for this installation's new drama generation. It does not import a six-agent system or repeated
per-prompt approval. H3-only routing, settled scope/budget and actual output acceptance remain in force.
