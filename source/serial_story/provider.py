from typing import Any, Protocol

from .records import WritingContext


class StoryProvider(Protocol):
    """Pure story-material boundary; no private project handoff is passed."""

    def plan(self, premise: str) -> dict[str, Any]: ...
    def draft(self, context: WritingContext) -> str: ...


class FakeProvider:
    """Deterministic plumbing fixture, not an LLM or narrative-quality demo."""

    def plan(self, premise: str) -> dict[str, Any]:
        return {
            "fixture": True,
            "premise": premise,
            "arcs": [
                {"start": start, "end": start + 39, "intention": "Placeholder arc"}
                for start in range(1, 201, 40)
            ],
            "character_arcs": {"Mara": "Placeholder: curiosity to responsibility"},
            "beats": [
                {"episode": n, "intention": f"Placeholder discovery {n}; not established history"}
                for n in range(1, 201)
            ],
        }

    def draft(self, context: WritingContext) -> str:
        lead = f"OFFLINE FIXTURE ONLY. Episode {context.episode}. Mara opens the map room."
        sentence = (
            "Mara counted the steps between the door and the table, then compared "
            "her notebook with the marks on the wall. Nothing in this repeated "
            "fixture passage is evidence of real model quality."
        )
        return lead + "\n\n" + "\n\n".join([sentence] * 13) + "\n\nWho had drawn the next door?"
