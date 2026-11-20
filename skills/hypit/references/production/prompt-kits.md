# Choosing and authoring Prompt Kits

Read this when choosing a reusable prompt treatment, assembling its Text inputs, or preserving useful
direction in a new Kit. A Kit can preserve proven wording even for one image or Take. Ordinary
`text:Value` elements carry the parts authored specifically for the current work.

A Prompt Kit is a data-only TextTemplate Source. It owns reusable wording and meaningful choices;
it does not own a model, Provider, media reference, output size, or production workflow. Keep fluent
shot direction fluent. Turn something into a Kit when preserving the exact text or exposing a small
repeated choice improves real productions, rather than splitting every sentence into a parameter.

## Choose an existing treatment by its relationship

[Image direction](../playbooks/craft/image-direction.md) and
[video direction](../playbooks/craft/video-direction.md) guide what the prompt should accomplish.
Choose a Kit whose fixed assumptions serve that intention:

For drama, use the current VISUAL/ASSETS and [cinematic look](../creation/cinematic-look.md)
when applicable. Keep a project-local image/look treatment and compile video through the
[official H3 format](../playbooks/craft/h3-prompts.md). Read any chosen installed template
for exact fields, avoiding inherited capture/acting assumptions that conflict with this scene.
After Kit expansion, apply [reference-first compilation](../playbooks/craft/h3-dense-direction.md#参考负责静态事实正文负责差异与过程)
to the actual final text: a fixed block must not repeat appearance supplied by connected assets,
and a shared camera/voice/scope clause must not be appended again by every slot. Preserve all
unique process, dialogue and attention conditions when consolidating duplicate wording.

These are packaged Sources, so their README and exported `.svs` files supply the template names,
Text slots, defaults and Recipe choices. A package's Surface vocabulary serves a different role:
`hypit vocabulary @hypit/text --tag Render` describes assembly, and the selected model's vocabulary
describes generation. Read the chosen template when its fixed text or a choice's exact wording matters.

For an ordinary speaking passage, connect the Segment's `.dialogue` and this passage's action;
the selected Recipe supplies recurring performance choices. For an image, bring Person, Shot and
Setting direction from Craft. Keep reference responsibilities consistent with the actual media
connected to the model. The owning package documents that order.

Fit includes assumptions as well as available knobs. A two-view conversation and a combined
split-screen opening may need different prompt structures. Keep the useful Kit for passages it
serves, and use authored Text or a project template for a different relationship. A Prompt Kit is
also distinct from a Run Fragment that supplies substitute media; [Runs](runs.md) owns that use.

## Declare the reusable text program

An `.svs` file selects Text's Recipe Frontend and declares one template root. This example preserves
one fixed capture direction, requires the current shot and direction, offers a reusable camera choice,
and includes a screen note only when the render selects it:

```svs
<?svml using="@hypit/text/svs@1"?>

<sheet version="1" id="drama-shot">
  text-template.drama-shot {
    separator: paragraph;
    default-camera: handheld;
    default-screen: false;
  }

  text-template.drama-shot.block.capture {
    kind: fixed;
    order: 10;
    text: "A photographed drama frame with coherent material, light and spatial relationships.";
  }

  text-template.drama-shot.block.camera {
    kind: axis;
    order: 20;
    parameter: camera;
  }
  text-template.drama-shot.choice.camera.handheld {
    text: "The camera has a believable handheld relationship to the subject.";
  }
  text-template.drama-shot.choice.camera.locked {
    text: "The camera remains still while the subject carries the action.";
  }

  text-template.drama-shot.block.screen-note {
    kind: variant;
    order: 30;
  }
  text-template.drama-shot.choice.screen-note.present {
    when-param-screen: true;
    text: "Keep the supplied interface physically contained and readable on its screen.";
  }

  text-template.drama-shot.block.shot {
    kind: slot;
    order: 40;
    slot: shot;
  }
  text-template.drama-shot.block.direction {
    kind: slot;
    order: 50;
    slot: direction;
  }
  text-template.drama-shot.block.references {
    kind: slot;
    order: 60;
    slot: references;
    optional: true;
    label: "REFERENCE ROLES:";
  }
</sheet>
```

The root joins blocks by one blank line. Its `default-<name>` properties supply scalar bindings.
Blocks are ordered by unique non-negative `order` values:

| Block | What it contributes |
| --- | --- |
| `fixed` | Exact reusable Text from `text` |
| `slot` | Text connected at render time; `optional: true` omits an absent slot, and `label` adds one literal heading |
| `axis` | Exactly the choice whose id equals the scalar named by `parameter` |
| `variant` | A choice whose `when-param-<name>` or `when-select-<name>` scalar conditions all match |

Choices live at `text-template.<template>.choice.<block>.<choice>`. Defaults, conditions, axis
parameters and literal `text:Param` values are finite text, number or boolean scalars. Text that is
produced elsewhere remains a graph edge rather than being copied into a scalar binding.

## Render it in an Author Source

```svml
<?svml using="@hypit/markup@1"?>
<svml>
  <import as="text" from="@hypit/text@1"/>
  <import as="kit" source="./drama-shot.svs"/>
  <import as="recipes" source="./look.svs"/>

  <text:Value id="shot">A medium close-up of the listener with the doorway visible behind her.</text:Value>
  <text:Value id="direction">She waits for an answer, keeping the sealed envelope out of view.</text:Value>
  <text:Value id="reference-roles">The first image supplies the listener's accepted identity and current look.</text:Value>

  <text:Render id="prompt" template={kit.drama-shot} recipe={recipes.prompt.main}>
    <text:Param name="camera" value="locked"/>
    <text:Param name="screen" value="true" type="boolean"/>
    <text:Set name="shot" text={shot}/>
    <text:Set name="direction" text={direction}/>
    <text:Set name="references" text={reference-roles}/>
  </text:Render>
</svml>
```

Save the template above as `drama-shot.svs`. For this example, `look.svs` can be:

```svs
<?svml using="@hypit/svs@1"?>
<sheet version="1">
  prompt.main { camera: handheld; }
</sheet>
```

The optional Recipe supplies scalar properties consumed by the template. Template defaults apply
first, Recipe values replace those defaults, and explicit `text:Param` children replace Recipe
values. `text:Set` replaces one Text binding through a graph edge; `text:Append` adds another Text
after that binding. Their order is authored and visible.

The rendered `{prompt}` is an ordinary Text Output. Connect it to a model's prompt port, or target it
in a small Run and inspect or export that Result before using the Kit elsewhere. This checks the
assembled words without calling the image or video model. The model Surface still owns aspect ratio,
duration, resolution and reference Resource children; prose describing what a reference supplies
does not create the reference edge.

Keep a Kit project-local while it serves one project. When its owner wants the same program in other
projects, export the `.svs` file from an ordinary versioned data package and import that package Source
directly. [Component sharing](component-sharing.md#data-packages-remain-data) owns that distribution
boundary; no activation code or Hypit-specific registry is involved.
