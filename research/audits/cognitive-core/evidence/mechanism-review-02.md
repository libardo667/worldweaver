# Evidence review 02: action feedback, embodiment, and external supports

Status: bounded review, 2026-07-19. This review asks what outside work can contribute to one code decision:
whether a resident's action and its actual consequence need to form a reliable loop.

It does not ask whether WorldWeaver residents are conscious or biologically embodied. The sources below
disagree about representation and the basis of perception. Their common relevance is narrower: a command
proposal alone is not an agent's successful contact with a world.

## Search record

Date: 2026-07-19.

Queries:

- `sensorimotor contingencies O'Regan Noe 2001 DOI primary paper`
- `Wolpert Ghahramani Jordan internal model sensorimotor integration 1995 DOI`
- `sensory prediction errors motor adaptation Tseng 2007 DOI`
- `Rodney Brooks Intelligence without representation 1991 DOI`
- exact-title searches for critical tests and the extended-mind paper

Source roles were kept separate: human motor experiments inform biological comparison, robotics and
sensorimotor papers supply competing theories, and extended mind supplies a philosophical argument about
durable external supports.

## Direct coupling without a central world model

Rodney Brooks argued for building complete situated systems from activity-producing layers that connect
directly to the world through perception and action, rather than beginning with a detached symbolic model:
[“Intelligence without representation”](https://doi.org/10.1016/0004-3702(91)90053-M), 1991.

This is an engineering and theoretical position, not evidence that any perception-action loop is intelligent
or conscious. It does establish a serious design alternative to WorldWeaver's current stack of model prose,
hand-authored inner variables, and then action. On a Brooks-like reading, trustworthy world coupling may be
more important than adding another internal metaphor.

WorldWeaver's typed engine commands fit this direction better than its old free-form narrator. But counting a
declined proposal as “moved” breaks the coupling: the control layer reasons from its own output instead of the
world's response.

## Internal models and sensory prediction error

Wolpert, Ghahramani, and Jordan studied human hand-position estimates after movements and external forces,
reporting results they interpreted as support for an internal model used in sensorimotor integration:
[“An internal model for sensorimotor integration”](https://doi.org/10.1126/science.7569931), 1995.

Tseng and colleagues later compared reaching adaptation in healthy participants and people with cerebellar
ataxia. Their results supported sensory prediction error, rather than online motor correction alone, as a
driver of the cerebellum-dependent adaptation examined in that task:
[“Sensory prediction errors drive cerebellum-dependent adaptation of reaching”](https://doi.org/10.1152/jn.00266.2007),
2007.

These are task- and organism-specific findings. They do not validate WorldWeaver's afterimage, its five nodes,
or a general theory that every agent must maintain a biological-style forward model. They do sharpen one
software distinction: learning from an action requires the observed consequence to remain distinguishable
from the command and predicted consequence. WorldWeaver currently loses that distinction in its act-history
prompt and often withholds the observed outcome from the next model call.

The appropriate implementation response is not to add a “cerebellum” module. It is to preserve request,
prediction, world receipt, and later observation as separately inspectable evidence.

## Sensorimotor-contingency theory and its limits

O'Regan and Noë proposed that vision and visual experience depend on practical mastery of the lawful ways
sensory input changes with action, rather than on a detailed internal picture:
[“A sensorimotor account of vision and visual consciousness”](https://doi.org/10.1017/S0140525X01000115),
2001. The target article was published with extensive peer commentary, reflecting substantial dispute over
its explanatory reach.

A later experiment by Bridgeman and colleagues tested a predicted adaptation of pressure phosphenes under a
deliberately favorable repeated sensorimotor condition and did not observe the predicted change:
[“A Test of the Sensorimotor Account of Vision and Visual Perception”](https://doi.org/10.1068/p5719a), 2008.

That failed prediction is important. “Sensorimotor” is not a magic word that validates any active system, and
theories in this family can make claims that evidence does not support. WorldWeaver should not infer that an
HTTP action endpoint creates perception or consciousness. The useful design question is testable instead:
does a resident learn stable action-dependent regularities better when accurate outcomes are delivered than
when only proposals or later public summaries are available?

## Durable external supports

Clark and Chalmers argued that reliably available external resources can sometimes participate in a cognitive
process rather than serving only as passive aids:
[“The Extended Mind”](https://doi.org/10.1111/1467-8284.00096), 1998.

This is a philosophical argument, not an experiment and not proof that WorldWeaver's ledger or workshop is
part of a resident mind. It does make reliability, accessibility, trust, and ordinary use relevant questions.
A workshop file that persists, can be deliberately revisited, and changes later activity is a stronger
candidate for a functional external support than an operator log the resident never receives. A hidden
failure receipt cannot play that role merely because it exists on disk.

The same caution applies to the hearth. A line saying that a cup was placed is not a reliable external object
if later perception, custody, and action cannot depend on the cup. Persistent prose and persistent physics are
different kinds of support.

## Decisions supported by this review

- Retain typed, permissioned world commands and canonical consequences. They are one of the strongest parts
  of the architecture.
- Give every proposal a separately typed accepted, declined, or unknown outcome and make unobserved outcomes
  available to later resident attention.
- Preserve command, expected result, engine receipt, and later observation as different evidence. Do not call
  a proposal an action history.
- Do not add brain-part names or claim biological motor learning. Compare feedback designs directly in this
  software.
- Describe WorldWeaver's current “body” narrowly as a functional world attachment. Stronger embodied or
  conscious-status claims remain open.
- Treat the ledger, workshop, and hearth objects according to their actual persistence and resident access,
  not according to how body-like their prose sounds.
- Run a paired test: identical residents and public inputs, with accurate private action feedback versus the
  current proposal-only prompt. Measure repeated invalid attempts, successful adaptation to permissions,
  state-consistent later choices, and cost without rewarding activity for its own sake.
