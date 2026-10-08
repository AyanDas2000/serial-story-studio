from dataclasses import dataclass
from typing import Any, Literal


class StoryError(ValueError):
    """An actionable workflow refusal, rather than a hidden recovery."""


@dataclass(frozen=True)
class Plan:
    id: int
    status: Literal["proposed", "approved"]
    content: dict[str, Any]


@dataclass(frozen=True)
class Episode:
    id: int
    number: int
    status: Literal["pending", "accepted", "rejected"]
    text: str
    accepted_text: str | None
    parent_history: int
    parent_memory: int = 0


@dataclass(frozen=True)
class AcceptedEpisode:
    revision_id: int
    number: int
    text: str


@dataclass(frozen=True)
class WritingContext:
    episode: int
    text: str
    included_revision_ids: tuple[int, ...]
    omitted_revision_ids: tuple[int, ...]
    memory_revision: int = 0
    history_revision: int = 0
    fact_ids: tuple[int, ...] = ()
    direction_ids: tuple[int, ...] = ()
    focus_entity_ids: tuple[int, ...] = ()
