# Designing a good component

Read this when deciding how to organize a picture, a transition or a recurring visual system.
Design it with the taste of a director and the care of someone who will use it in a real composition.
A useful component makes a particular idea legible and keeps its behavior understandable within the
production. Its author interface can be as small as the work requires.

[Graphic composition](../playbooks/craft/graphic-compositions.md) owns visual hierarchy;
[motion graphics](../playbooks/craft/motion-graphics.md) owns changes in the picture over time;
[Track authoring](track-authoring.md) owns the implementation. A new Caption family also draws on
[Caption craft](../playbooks/craft/captions.md) and [Caption authoring](caption-authoring.md).

## Find the relationship worth giving a name

Start with the viewer's experience: a comparison becomes clear, an answer resolves a question, a
a narrative clue accumulates, or a phrase lands with particular emphasis. Explain what appears, why it appears
there, what changes, and what the viewer should retain afterward. That explanation suggests both
the visual design and the component boundary.

Existing components are useful expressions of familiar relationships. Use one when its behavior
fits, or define a project component for the role this work needs. Its content and timing can vary
while the relationship remains clear. A new component can combine existing helpers with its own
drawing and animation; ordinary authoring includes both using and extending that vocabulary.

A board whose rows share layout and persistent state benefits from one component. An independent
photo and title can remain peer Tracks. An object that survives several camera cuts keeps the same
authored identity while its state develops. Let shared behavior define the unit.

A performance moving from full screen into a side viewport and a diagram filling the released space
can share one component. It owns their relative layout, overlap, masking and coordinated motion.
A-roll supplies the performed passage; visual ownership follows the behavior being designed.
Existing footage can use [Performance Styles](performance.md); independent assets use Media. A
one-off scene is a useful component too. Caption and independent overlays can remain separate.

Decompose a scene further where its parts have meaningful independent responsibilities. Keep
coordinated geometry, state and transitions together where that makes their behavior clear. Internal
functions and subcomponents can organize this code without each becoming another Track or package.
The useful division preserves the relationship through change; more layers alone do not improve it.

## Separate responsibility, parameters and reuse

Adaptive composition introduces structure where it makes the work easier to understand and direct.
A boundary gives a responsibility an owner; a parameter expresses a choice supplied from outside
that owner; reuse preserves a relationship across uses. These decisions serve different needs.

| Decision | What justifies it |
| --- | --- |
| Independent organization | A distinct visual responsibility, lifetime or behavior benefits from its own owner. Parts sharing geometry, state or motion can stay together. |
| Parameterization | The production needs an external choice: an asset, a spoken trigger, a placement or a setting the author will actually adjust. |
| Reusable design | Actual uses share a relationship or treatment. Share that behavior and generalize only the variation those uses need. |

An author input is not a requirement to publish a package or provide a Studio control. A shared
internal function is not necessarily another Track. Numeric and qualitative choices use the same
criterion: does an external dependency or a useful directing decision belong here? A color, mood,
layout mode or easing name does not deserve a public parameter merely because it could vary.

One-off effects can be independently organized with fixed designs. A future edit may appropriately
change their implementation. Consider likely revisions to reveal tangled responsibilities or useful
inputs, rather than treating every possible edit as a parameter to implement in advance. Even repeated
use can share the same fixed treatment. Interface breadth and reuse count do not measure component quality.

Fine Caption similarly offers reusable flowing text, while a custom Caption family can own a new
relationship among words and graphics. Both consume Script wording and semantic timing. Shared
behavior can keep these visuals together; [Caption authoring](caption-authoring.md) explains the
specialized text inputs and the same freedom to compose.

Give a reusable scene the prepared performance, its outer Window and the Moment that changes its
layout through the Timeline and shared temporal projections. Replacing a scene asset or rewriting the
Script then changes content and semantic anchors while preserving the behavior. The final frame
positions come from the placed Takes.

Use the current drama storyboard and actual title/effect handoff as the concrete
component brief. Trace what drives the timing and what a changed scene should replace.

## Let meaning drive the behavior

Prefer Script Selections, Moments and Segments for events that respond to the argument or performance.
The Surface projects them through the accepted Timeline; the component consumes the resulting
Windows or Instants. A different delivery can then move the event while preserving its purpose.
Explicit time remains useful for an authored lead, a short entrance or another clock-based decision.
In a pure MG piece, name the events that carry its meaning and direct their reading rhythm. A useful
component accepts resolved Instants or Windows so the same reveal can follow a Script Moment or an
authored time. Keep message content and its trigger together in Source; repeated children can each
have their own trigger. Use semantic examples first for speech-led roles, showing how a new performance
preserves the relationship. [Authored animation](rendering.md#compose-an-authored-animation) covers
the film clock when there is no performance.

A semantic outer Window alone does not establish the timing of its internal events. In a drag-and-drop
scene, selecting a picture, dropping it into an editor and revealing the result may answer three
different phrases. Give those actions their own semantic inputs. Placing them at fixed seconds or
at 20%, 50% and 80% of the outer Window preserves neither their identities nor their relationship
to unevenly changed speech.

The Surface can accept an outer Selection and separate Moments for those events, projecting each
through Timeline. The implementation derives movement between the resulting events and keeps its
pointer path, button geometry, click rebound and decoration local. A movement that simply unfolds
inside one authored event interval may use normalized progress there; it needs no marker for every
animation key. Meaningful event location and the designed duration/shape of motion are different choices.

Choose the temporal input from what the component does. A picture covering an explanation occupies
its Selection. An answer revealed on a word can remain visible after that word ends. A clue
may move during a reveal Window and stay in its settled row afterward. The board's outer lifetime,
the trigger and the resulting state each have a clear meaning.

Direct motion through that relationship. Arrival draws attention, settling establishes a new state,
replacement makes a change readable, and departure releases space for the next idea. Choose how much
time each needs relative to the meaning it carries. When an authored interval changes length, decide
which part follows that interval and which part keeps its own readable duration. Document that choice.

One authored event can also coordinate peer Tracks: a reveal, sound and flash can use the same
Moment. A shared event is enough when each contribution already has a useful independent component.
[Track authoring](track-authoring.md#keep-selection-projection-and-consumption-distinct) explains the
projection and consumption boundary in detail.

## Expose the choices the work needs

A good parameter earns its place by enabling a useful directing choice or connecting a real dependency.
Keep Script wording and semantic anchors connected to their existing owners, and supplied media
explicitly wired. Illustrative text, decorative geometry and purpose-built animation may remain local
to a one-off scene. A fixed design is complete when it serves the piece; adding controls is a separate
decision. If a label later needs repeated variation, promote that choice to an input then.

For the inputs that matter, sketch their Source use before implementing them. Related authored visual
choices can form a Style or Recipe. A comparison may need labels, images and a reveal relationship;
its internal layout can derive from those few inputs. One meaningful control can coordinate many
details while preserving a designed whole. Semantic triggers remain valuable even for a scene used
once: they connect its behavior to the actual performance without exposing every animation detail.

When reuse is needed, support the actual variation: longer names, another scene asset or a different
number of rows. A new visual relationship may deserve another component.
[Caption craft](../playbooks/craft/captions.md#caption-families-styles-and-parameters) illustrates
family, Style and parameter choices for a commonly reused role.

## Design the component in its frame

Judge it beside the character, coverage, Caption and other graphics it will share the picture with.
Give the eye a clear entry point, useful grouping and a settled state that remains readable. The
component's local palette, density and motion should support the whole composition's hierarchy.

Use the chosen Frame to express placement and derive the internal layout from it. Decide how real
text and media occupy that space: what wraps, what crops, what scales, and what stays aligned. A useful
fixed layout can suit the present work; expose placement or size when the composition needs to direct
them externally. Let a genuinely unsupported configuration produce an actionable explanation of the
content or space that needs changing.
[Spatial layout](spatial.md) owns fitting and coordinate relationships; [Fonts and text](fonts-and-text.md)
owns text resources and placement.

Look at the important states in the actual composition: before the reveal, during the change, after
it settles, and when the system leaves. A preview with representative content can answer hierarchy,
readability, collisions and timing together. Make the correction at its owner: a semantic anchor,
the chosen Recipe, the component's behavior or the visual idea itself. Reuse the production's media
while refining those relationships.

## Make the idea easy to use and revise

Give the component vocabulary and an example that show its purpose, required inputs, public outputs
and the meaning of its timing. For persistent state, explain what remains after activation. A preview
should reveal the behavior that makes someone choose this component, with useful default content.

For a production the user will explore in Studio, make its useful objects recognizable: a board's
lifetime, a row's reveal, a Caption Cue's actual Style. Watching and understanding the work are useful
on their own; a read-only scene with a clear identity can be complete. Expose controls for the real
adjustments the user needs, such as Caption position and color, through the existing author inputs.
An empty parameter panel alone is no reason to widen the component interface.
[Companion authoring](studio-companions.md) owns those bindings.

Read the installed author-kit and the closest necessary component to resolve the
specific implementation question; carry only that mechanism into this drama.
