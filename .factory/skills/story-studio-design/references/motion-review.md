# Purposeful motion specification

Proposed choreography for later approval. Nothing here is runtime verification.

Use existing named tokens: instant 80ms, fast 160ms, base 240ms, standard `cubic-bezier(0.2,0,0,1)`. Do not introduce a parallel curve scale from an upstream recipe. New tokens need an explicit local decision. Default to no movement in repeatedly used reading/editing actions.

| Trigger | Property / token | Purpose | Interruption / repetition | Reduced motion |
| --- | --- | --- | --- | --- |
| Pointer press on task action | Subtle transform, instant / standard; persistent state conveyed in text | Input feedback, not successful save | CSS transition retargets on release; no action waits for animation; keyboard activation does not move the control | No transform; retain focus and immediate status |
| Saved revision acknowledged | Status opacity, fast / standard | Separate local edits from durable save | Retarget on a new save; keep receipt available after transient status disappears | Immediate text or brief opacity only |
| Authorized request pending | Static status; delayed content-shaped placeholder only if appropriate | Tell the writer what is waiting without suggesting progress we do not know | No typewriter, fake percentage or pulsing prose; preserve prior candidate | Same static status |
| Complete candidate arrives | Opacity on new status, base / standard; prose itself appears stably | Mark candidate availability without moving text | Never replay on refresh; preserve selection and reading position; allow immediate editing | Immediate prose and status, optional brief opacity |
| Revision comparison opened by pointer | Opacity, fast / standard | Make the optional comparison's arrival legible | Close/retarget immediately; no forced entrance replay or moving manuscript | Immediate panel |
| Prose acceptance acknowledged | Checkpoint label opacity, fast / standard | Explain transition to memory review, not celebration | Focus on new task heading after actual persistence; double activation handled by backend, not an animation lock | Immediate task and accessible announcement |
| Memory proposal selected | Static selected border and source highlight; optional highlight opacity, fast / standard | Connect interpretation to its final passage | Rapid selection retargets; restore source-return position; never pan graph automatically | Static selection and source |
| Memory confirmation acknowledged | Row status opacity, fast / standard | Show confirmed/rejected state and remaining work | Do not remove row while focused; retain undo/correction path according to backend policy | Immediate status |
| Ready for next episode | Static checkpoint and primary action | Availability must be clear, not theatrical | No confetti, gate-opening sweep or delayed action | Same |
| Typing, keyboard navigation, recurring refresh, scroll-back | None | Protect concentration and response time | Never re-stagger lists or reset selection | Same |

## Resolve supplied-skill conflicts explicitly

The stack `motion` minimum mandates screen transitions and first-list entrances; `animate` correctly begins by asking whether the action should animate and rejects keyboard/high-frequency motion. The local rule is purpose and frequency first, not “add motion everywhere.”

Stack `motion` specifies 400ms route motion and an exit curve; `animate` and `review-animations` prefer sub-300ms UI and different curves. Reuse the existing fast/base standard tokens for the proposed workflow. Escalate an actual need for a new route/exit token rather than silently switching systems.

`review-animations` flags pure-fade entrances, but also calls for gentler reduced motion. A subtle status fade is acceptable for a reading tool; it is not a reason to add unnecessary translation. Log this proposed local exception for Ayan rather than changing the supplied skill.

## Movement evidence checklist

- [ ] Record actual trigger, implementation property, token and source location.
- [ ] Drive pointer and keyboard paths, rapid repeat, reversal and dismissal mid-transition.
- [ ] Verify selection, cursor, scroll position and focus survive background refresh.
- [ ] Toggle reduced motion and fine/coarse pointer behavior.
- [ ] Watch candidate arrival, acceptance → memory and confirmation → next direction at normal speed.
- [ ] Use a recording or an observed driven session for feel. Screenshots prove only a static frame.
- [ ] Performance claims require a trace on stated hardware/load; transform/opacity source alone does not prove 60fps.
- [ ] If not run, report “specified/source-inspected, movement unverified,” not “motion passed.”

Do not copy portfolio ambience, infinite cues, grain, glow, scrolling choreography or repeated entrance delays into the writer's reading surface.
