# Request controls: prove what the selected route actually receives

Read before submitting continuity-sensitive drama generation, especially through a project runner
or third-party application. This page joins direction to execution; it does not prescribe one vendor.
Use existing project records, Model/Provider contracts and endpoint documentation as owners.

For this installation's video work, [RunningHub H3](runninghub-h3.md) is the permitted route.
Capability gaps are resolved within that route or by changed coverage; general specialist/provider
alternatives below do not override the user's video restriction. For adaptations, also perform
[story transfer](story-transfer.md): a correctly bound request can still omit a critical event.

For adapted work, trace source obligations through the current target rows, actual prompt/input
and executable EDIT; see [field mapping](detail-transfer-format.md). The source catalogue comes from
original inspection, not the adapted job manifest. No separate allocation or review package is needed.
Use [checked_submit](production-gate.md) at the actual transport point to verify the exact request,
bound media/upload receipts, duration, default instance and empty video slots. It does not invoke
independent artistic/source review. Compare actual output separately after generation.

## Establish the exact operation

New schema-driven RunningHub work uses the bundled [slot adapter](runninghub-slot-routing.md).
Its discover/clip/prepare/submit/query path inventories every available modality, binds only selected
references, checks exact pointers/labels/upload receipts and sends the gate's exact bytes. Reuse
the existing preparation and adoption records without adding an approval or review queue.

Record service, model/version, endpoint or app/workflow ID, operation/mode and the relevant runner
version. Inspect current documentation/schema and that runner's actual serialized request, including
node configuration for hosted workflows. A model-wide feature does not establish that an app exposes
it. A field exposed by the app does not establish that the runner sends it. Never infer capability
from a friendly model name, a prompt label, or a remembered number of reference slots.

For each required control, resolve this row before a full scene batch:

| Need | Actual control role | What must be verified |
| --- | --- | --- |
| Recognizable person | Identity reference | Correct face/look version; supported reference input and request binding |
| Scene composition | Composition reference or first frame | Which relationship is supported; only the latter constrains the opening as a keyframe |
| Precise end state | Last frame | Supported operation and compatibility with identity/audio/other inputs |
| Acting/timing | Detailed shot phases and target composition images | Source is local evidence; video input is disabled |
| Recurring voice | Audio reference | Real audio input, speaker mapping; audible result still needs acceptance |
| Exact soundtrack | Audio reuse | Actual waveform reuse rather than timbre guidance; mixing ownership |
| Visible speech against exact audio | Speech/performance drive or lip sync | Exact audio binding plus verified visible synchronization; reuse alone is insufficient |

For the complete chosen mode, verify input combinations, counts, durations, formats, resolution,
aspect ratio and any node switches activating the operation. Save the relevant documentation or
schema excerpt and verification date with the production. Distinguish documented support, serialized
binding, and observed output behavior. An untried feature is not a proved quality improvement.

If a needed control is unsupported or unverified, select a supported operation within the permitted
route or redesign coverage without losing its essential experience and story function. Preserve the user's service constraint.
New spending remains governed by Brief. Do not silently
substitute a weaker role, install a large unrelated stack, or invent a working provider integration.

## Carry audio intent into actual inputs

Begin with the current STORYBOARD sound card and CHARACTERS/ASSETS voice version. Select
only the reference, signal reuse or exact speech control actually needed for this scene.
An exposed AUDIO node must be traced to its real operation; do not equate its presence with
proven waveform copying, multi-speaker lip sync or character consistency.

For a chosen voice-reference route: prepare/accept a clean sample; upload the actual bytes;
record file/hash, receipt, audio label, speaker mapping, allowed timbre/delivery control and
excluded original words/score as applicable; bind its returned resource at the verified
payload pointer. In official Ref2VA fields, define the audio/speaker relationship, use
`reference` for timbre rather than `fully_copy`, and direct the new literary-script line
and performance in the main description. Signal-reuse paths deliberately choose their
appropriate copy relationship and exact-audio synchronization still needs its own proof.

Derive an `audio_reference`, `audio_reuse` or `speech_drive` requirement from each selected
control into the existing binding export. Check the final request, not only prompt labels.
A runner that clears media nodes to `None` and restores only images/video has not connected
voice inputs. Reject null/empty/`None` placeholders as media resources; the checker handles
these declarations without authenticating remote upload identity or listening. A meaningful
file path/receipt still must correspond to actual inspected bytes.

When voice/interaction behavior is still unverified, trial the exact route with the actual cast/language and consequential
delivery or neighbor cut, comparing the accepted sample and returned speech. Check identity,
new words, emotion, listening rhythm, mouth, acoustic perspective and original-audio leakage.
Carry heard results/calibration through the same artistic assessment; do not call text-only
direction a sample lock. No universal node IDs, external lip-sync fallback, new approval
stage or additional reviewer is supplied here.

## Follow the request through submission

Custom runners call `production_gate.checked_submit` at the real transport point and stop on
actual request/input errors. It checks the final serialized request, not an independent review or
frozen preparation package. If upload adaptation changes prompt/binding content, recheck those
bytes. Creative completeness is checked during adoption; actual media is checked after generation.

For newly prepared reference-bound work, use [reference scopes](reference-scopes.md): accepted input,
explicit order, actual node/role, allowed and excluded control, and the real H3 clauses carrying them.
The binding checker supports `--require-control-scopes` (or `validate(..., require_control_scopes=True)`)
for this gate. Do not attach scope metadata without expanding its content in the actual prompt.

1. From the accepted scene/shot rows, enumerate the controls and assets this block requires. Separate
   identity, current look, composition, local state, performance and sound responsibilities.
2. Bind each actual asset into its supported input, with correct mode, labels and speaker mapping.
   Upload receipts must correspond to the same bytes being used; a path/size-only cache can reuse a
   stale upload after an edit. Record file content hashes or equivalent immutable asset versions.
3. Preserve the exact request that will be sent and its request hash. Compare required inputs with
   serialized fields, not just prompt prose. Unknown fields, missing media and unsupported role
   substitutions are errors. Resolve parent adoption and chosen cut point before dependent requests.
4. Submit through the chosen runner only after checks pass; save the task receipt next to that exact
   request. Recheck after any payload, input, upload, route or parent change. Completion means returned
   media exists, not that it is accepted. [Scene acceptance](scene-acceptance.md) owns that decision.

Persist any provider task ID before polling. A timeout/closed observer or missing downloaded file
does not establish remote failure. Query and collect the recorded task before considering a new
submission, following [production calibration](production-calibration.md) and the supported API.

Use Hypit's native `check` and `plan` for Sources/Runs and the Provider's support checks. They are not
substitutes for checking the adapter's real media bindings when implementing or using a custom route.
Do not retrofit an old completed production just because this skill changed; apply these controls to
new or explicitly revised work.

## Lightweight check for custom JSON runners

The bundled `scripts/check_request_bindings.py` performs an offline, read-only check. Integrate it
immediately before submission (or call its `validate()` from the runner), and make a nonzero exit
block that submission. It does not itself submit, upload, inspect media or install a service.

```text
python <hypit-skill>/scripts/check_request_bindings.py <block>/bindings.json
```

`bindings.json` is an export of the current owning records, never an independent creative authority.
Regenerate it when those records change. All file paths are relative to this export unless absolute.
Use lowercase SHA-256 of actual file bytes. `accepted` means accepted for the input's specific use,
backed by the referenced review; it never means the downstream scene has passed. Do not fabricate
reviews or set booleans merely to make this check pass.

Example shape (names and pointers are illustrative, not a real vendor API):

```json
{
  "version": 1,
  "request": {"file": "request.json", "sha256": "<actual hash>"},
  "route": {
    "id": "service/app/version/operation",
    "evidence": {"file": "route-contract.txt", "sha256": "<actual hash>"},
    "supported_roles": ["first_frame", "identity_reference"],
    "selectors": [{"pointer": "/mode", "value": "image-to-video"}]
  },
  "requirements": [{"id": "opening", "role": "first_frame", "binding": "start"}],
  "bindings": [{
    "id": "start", "roles": ["first_frame"], "accepted": true,
    "asset": {"file": "start.png", "sha256": "<actual hash>"},
    "review": {"file": "start-review.md", "sha256": "<actual hash>"},
    "pointer": "/first_frame", "value": "uploaded-file-token"
  }],
  "dependencies": [{
    "id": "previous-adopted-state", "accepted": true,
    "asset": {"file": "previous.mp4", "sha256": "<actual hash>"},
    "review": {"file": "previous-adoption.json", "sha256": "<actual hash>"}
  }]
}
```

The adoption record includes the accepted interval and extraction time; hashing it catches changed
cut points as well as changed media. Use an empty dependencies array for an independent block.
A route selector checks an operation/mode/node field in the payload; if the operation is expressed
solely by the URL, export a local request envelope with method, URL and body, and point into that
same envelope. The runner sends the unchanged body to that recorded URL.

Populate `value` from the actual upload receipt or bound resource value; never manufacture a token.
JSON pointers address the exact field, including array indices for node lists. Roles are local
semantic names: `identity_reference`, `composition_reference`, `first_frame`, `last_frame`,
`video_reference`, `audio_reference`, `audio_reuse`, `speech_drive`.
One physical input may have several documented roles: declare them in that binding's `roles` array
and map multiple requirements to it. Do not create duplicate bindings for the same field. This does
not authorize assigning extra roles that the actual operation and supplied media cannot fulfill.

The checker verifies declared role compatibility, requirement coverage, accepted input flags,
nonempty files, hashes, route selectors and actual payload values. It cannot prove the documented
role's semantics, that a remote token resolves to those bytes, review quality, full provider limits
or the adequacy of an omitted requirement. Inspect the schema/upload receipt and required-control
row for those facts. Do not present its success as a complete provider or scene validation.

## Prove the difficult passage before scaling

Use a passage representative of the required problem: two-person scale, reaction and interruption,
a prop handoff or recurring extras. Carry it through the real endpoint and adjacent-shot playback.
Reuse suitable existing evidence. If a paid trial is needed, keep it within the agreed budget.
Record what actually worked, usable intervals and remaining limitations. A provider change earns
adoption through that evidence, not a ranking, a repository star count or an unsupported percentage.

[Source notes](continuity-sources.md) record the specific external methods behind these choices.
