from collections.abc import Callable
from time import perf_counter
from typing import Any, TypeVar

from .budget import BudgetAccounting, SQLiteBudget
from .provider import FakeProvider, StoryProvider
from .memory import SQLiteMemory

from .records import AcceptedEpisode, Episode, Plan, StoryError, WritingContext
from .repository import SQLiteRepository, StoryRepository

T = TypeVar("T")
R = TypeVar("R")


class StoryService:
    """Application rules independent of terminal prompts or a future web surface."""

    def __init__(self, repository: StoryRepository, provider: StoryProvider | None = None,
                 max_context_characters: int = 18000, budget: BudgetAccounting | None = None):
        if budget is None:
            if not isinstance(repository, SQLiteRepository):
                raise StoryError("Supply an accounting implementation with a non-SQLite repository.")
            budget = SQLiteBudget(repository)
        self.budget = budget
        self.max_context_characters = max_context_characters
        self.repository = repository
        self.memory = SQLiteMemory(repository) if isinstance(repository, SQLiteRepository) else None
        self.provider = provider if provider is not None else FakeProvider()

    def initialize(self, premise: str) -> None:
        self.repository.initialize(premise)

    def propose_plan(self) -> Plan:
        current = self.repository.plan()
        if current is not None:
            return current
        premise = self.repository.story()["premise"]
        return self._operation(0, "plan", lambda: self.provider.plan(premise), self.repository.save_plan)

    def approve_plan(self, plan_id: int) -> Plan:
        return self.repository.approve_plan(plan_id)

    def context(self, focus_entity_ids: tuple[int, ...] = ()) -> WritingContext:
        story = self.repository.story()
        plan = self.repository.plan()
        if plan is None or plan.status != "approved":
            raise StoryError("Approve the plan before drafting an episode.")
        number = story["next_episode"]
        if number > 200:
            raise StoryError("The approved episode range is complete.")
        beat = plan.content["beats"][number - 1]
        accepted = self.repository.accepted()
        text = "Premise: " + story["premise"] + "\nIntention: " + beat["intention"]
        memory_start = self.memory.revision() if self.memory else 0
        memory_text, fact_ids, direction_ids, memory_revision = self.memory.prepare_context(number, focus_entity_ids) if self.memory else ('', (), (), 0)
        if memory_text:
            text += '\n' + memory_text
        if len(text) > self.max_context_characters:
            raise StoryError("Essential context exceeds the limit. Shorten or explicitly compact it before drafting.")
        included: list[int] = []
        for episode in reversed(accepted[-2:]):
            addition = "\nAccepted history:\n" + episode.text
            if len(text) + len(addition) <= self.max_context_characters:
                text += addition
                included.append(episode.revision_id)
        omitted = tuple(e.revision_id for e in accepted if e.revision_id not in included)
        if story['history_revision'] != self.repository.story()['history_revision'] or memory_start != memory_revision or (self.memory and self.memory.revision() != memory_revision):
            raise StoryError('Story state changed during context selection. Read it again before generating.')
        return WritingContext(number, text, tuple(included), omitted, memory_revision=memory_revision,
                              history_revision=story['history_revision'], fact_ids=fact_ids,
                              direction_ids=direction_ids, focus_entity_ids=focus_entity_ids)

    def draft(self, focus_entity_ids: tuple[int, ...] = ()) -> Episode:
        pending = self.repository.pending()
        if pending is not None:
            return pending
        context = self.context(focus_entity_ids)
        history = context.history_revision
        return self._operation(
            context.episode, "draft", lambda: self.provider.draft(context),
            lambda text: self.repository.save_draft(text, context.episode, history, context.memory_revision),
            {"included": context.included_revision_ids, "omitted": context.omitted_revision_ids,
             "characters": len(context.text), 'facts': context.fact_ids,
             'directions': context.direction_ids, 'memory_revision': context.memory_revision,
             'history_revision': context.history_revision, 'active_cast': context.focus_entity_ids},
        )

    def _operation(self, episode: int, stage: str, generate: Callable[[], T],
                   persist: Callable[[T], R], manifest: dict[str, Any] | None = None) -> R:
        call_id = self.budget.reserve(episode, stage, manifest=manifest)
        started = perf_counter()
        try:
            result = persist(generate())
        except BaseException:
            # Fail closed. Even a persistence failure may follow a completed call.
            self.budget.mark_uncertain(call_id, int((perf_counter() - started) * 1000))
            raise
        self.budget.settle(call_id, 0, int((perf_counter() - started) * 1000))
        return result

    def accept(self, revision_id: int, edited_text: str | None = None) -> AcceptedEpisode:
        return self.repository.accept(revision_id, edited_text)

    def reject(self, revision_id: int, note: str = "") -> None:
        self.repository.reject(revision_id, note)

    def read(self, number: int) -> AcceptedEpisode:
        return self.repository.read(number)

    def status(self) -> dict[str, Any]:
        story = self.repository.story()
        pending = self.repository.pending()
        plan = self.repository.plan()
        return {"next_episode": story["next_episode"], "history_revision": story["history_revision"],
                "pending_revision_id": pending.id if pending else None,
                "plan_status": plan.status if plan else "not proposed", "provider": "fake",
                "budget": self.budget.snapshot(story["next_episode"]),
                'project_budget': self.budget.project_snapshot() if isinstance(self.budget, SQLiteBudget) else None,
                'memory_revision': self.memory.revision() if self.memory else 0}
