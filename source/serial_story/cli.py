import argparse
import json
import os
import sqlite3
import uuid
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Sequence

from .records import StoryError
from .graph import render_graph
from .repository import SQLiteRepository
from .service import StoryService


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Local fake-only writing workflow. Not real model output.")
    result.add_argument("--db", type=Path, default=Path("local/story.db"))
    result.add_argument("--provider", choices=["fake"], default="fake")
    commands = result.add_subparsers(dest="command", required=True)
    initialize = commands.add_parser("init", help="Create a story without generating anything")
    initialize.add_argument("--premise", required=True)
    commands.add_parser("plan", help="Propose or read the existing fixture plan")
    approval = commands.add_parser("approve-plan", help="Approve the displayed plan proposal")
    approval.add_argument("plan_id", type=int)
    draft = commands.add_parser("draft", help="Create a fixture draft or reopen pending review")
    draft.add_argument("--out", type=Path, help="Save prose for local review without overwriting different text")
    accept = commands.add_parser("accept", help="Accept final prose, optionally from your edited file")
    accept.add_argument("revision_id", type=int)
    accept.add_argument("--text-file", type=Path)
    reject = commands.add_parser("reject", help="Reject this draft without changing accepted history")
    reject.add_argument("revision_id", type=int)
    reject.add_argument("--note", default="")
    read = commands.add_parser("read", help="Read accepted prose, optionally save a plain text copy")
    read.add_argument("episode", type=int)
    read.add_argument("--out", type=Path)
    commands.add_parser("status", help="Inspect progress and current episode's call allowance")
    context = commands.add_parser("context", help="Inspect the offline context and its inclusion manifest")
    context.add_argument("--character", type=int, action="append", default=[])
    draft.add_argument("--character", type=int, action="append", default=[])
    commands.add_parser("trace", help="Inspect durable call and review receipts")
    entity = commands.add_parser('entity-add', help='Register an author-approved character or location')
    entity.add_argument('--name', required=True)
    entity.add_argument('--kind', choices=['character', 'location'], required=True)
    entity.add_argument('--role', choices=['protagonist', 'core', 'supporting'], default='')
    commands.add_parser('entities', help='Read the cast and location registry')
    situation = commands.add_parser('situation-add', help='Confirm an accepted-source situation')
    situation.add_argument('--title', required=True)
    situation.add_argument('--revision', type=int, required=True)
    situation.add_argument('--evidence', required=True)
    fact = commands.add_parser('fact-propose', help='Propose an interpretation with exact accepted evidence')
    fact.add_argument('--subject', type=int, required=True)
    fact.add_argument('--predicate', required=True)
    fact.add_argument('--value', required=True)
    fact.add_argument('--revision', type=int, required=True)
    fact.add_argument('--evidence', required=True)
    fact.add_argument('--object', type=int)
    fact.add_argument('--situation', type=int)
    for name in ('fact-show', 'fact-confirm', 'fact-reject'):
        command = commands.add_parser(name)
        command.add_argument('fact_id', type=int)
        if name == 'fact-confirm':
            command.add_argument('--supersedes', type=int)
        if name == 'fact-reject':
            command.add_argument('--note', default='')
    facts = commands.add_parser('facts', help='Query confirmed facts, optionally including earlier developments')
    facts.add_argument('--subject', type=int)
    facts.add_argument('--history', action='store_true')
    facts.add_argument('--search', default='')
    direction = commands.add_parser('direction-set', help='Record or revise a future intention, never an established event')
    direction.add_argument('--key', required=True)
    direction.add_argument('--text', required=True)
    direction.add_argument('--from-episode', type=int)
    direction.add_argument('--through-episode', type=int, default=200)
    direction.add_argument('--subject', type=int)
    commands.add_parser('storyboard', help='Inspect current confirmed facts versus active future directions')
    graph = commands.add_parser('graph', help='Read graph JSON or export a self-contained read-only HTML view')
    graph.add_argument('--subject', type=int)
    graph.add_argument('--out', type=Path)
    return result


def export_without_overwrite(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Publish only complete text. A hard link creates the final name exclusively,
    # unlike replace(), which could overwrite existing human work.
    staged = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    created = False
    try:
        with staged.open("x", encoding="utf-8", newline="") as output:
            created = True
            output.write(text)
            output.flush()
            os.fsync(output.fileno())
        try:
            os.link(staged, path)
        except FileExistsError:
            with path.open("r", encoding="utf-8", newline="") as existing:
                if existing.read() != text:
                    raise StoryError("The output file already contains different text. Choose another path.") from None
    finally:
        if created:
            staged.unlink(missing_ok=True)


def main(argv: Sequence[str] | None = None) -> int:
    arguments = parser().parse_args(argv)
    try:
        with SQLiteRepository(arguments.db) as repo:
            studio = StoryService(repo)
            match arguments.command:
                case "init":
                    studio.initialize(arguments.premise)
                    output = {"message": "Story created. Propose a plan next.", **studio.status()}
                case "plan":
                    output = asdict(studio.propose_plan())
                case "approve-plan":
                    output = asdict(studio.approve_plan(arguments.plan_id))
                case "draft":
                    draft = studio.draft(focus_entity_ids=tuple(arguments.character))
                    output = {**asdict(draft), "words": len(draft.text.split()),
                              "message": "Read this fixture, then accept final prose or reject it."}
                    if arguments.out:
                        export_without_overwrite(arguments.out, draft.text)
                        output["saved_to"] = str(arguments.out.resolve())
                case "accept":
                    edited = arguments.text_file.read_text(encoding="utf-8") if arguments.text_file else None
                    accepted = studio.accept(arguments.revision_id, edited_text=edited)
                    output = {**asdict(accepted), "next_episode": studio.status()["next_episode"]}
                case "reject":
                    studio.reject(arguments.revision_id, arguments.note)
                    output = {"message": "Draft rejected. Draft again only when you choose.", **studio.status()}
                case "read":
                    accepted = studio.read(arguments.episode)
                    output = asdict(accepted)
                    if arguments.out:
                        export_without_overwrite(arguments.out, accepted.text)
                        output["saved_to"] = str(arguments.out.resolve())
                case "status":
                    output = studio.status()
                case "context":
                    output = asdict(studio.context(focus_entity_ids=tuple(arguments.character)))
                case 'entity-add':
                    output = asdict(studio.memory.add_entity(arguments.name, arguments.kind, arguments.role))
                case 'entities':
                    output = {'entities': [asdict(e) for e in studio.memory.entities()]}
                case 'situation-add':
                    output = asdict(studio.memory.add_situation(arguments.title, arguments.revision, arguments.evidence))
                case 'fact-propose':
                    output = asdict(studio.memory.propose_fact(arguments.subject, arguments.predicate, arguments.value, arguments.revision, arguments.evidence, object_id=arguments.object, situation_id=arguments.situation))
                case 'fact-show':
                    output = asdict(studio.memory.fact(arguments.fact_id))
                case 'fact-confirm':
                    output = asdict(studio.memory.confirm_fact(arguments.fact_id, supersedes=arguments.supersedes))
                case 'fact-reject':
                    output = asdict(studio.memory.reject_fact(arguments.fact_id, arguments.note))
                case 'facts':
                    output = {'facts': [asdict(f) for f in studio.memory.query_facts(arguments.subject, current_only=not arguments.history, search=arguments.search)]}
                case 'direction-set':
                    output = asdict(studio.memory.set_direction(arguments.key, arguments.text, start_episode=arguments.from_episode, end_episode=arguments.through_episode, subject_id=arguments.subject))
                case 'storyboard':
                    output = studio.memory.storyboard_snapshot()
                case 'graph':
                    graph = studio.memory.graph_snapshot(subject_id=arguments.subject)
                    if arguments.out:
                        export_without_overwrite(arguments.out, render_graph(graph))
                        output = {'saved_to': str(arguments.out.resolve()), 'node_count': len(graph['nodes']),
                                  'edge_count': len(graph['edges']), 'memory_revision': graph['memory_revision'],
                                  'warning': graph['warning']}
                    else:
                        output = graph
                case "trace":
                    output = {
                        "calls": [dict(r) for r in repo.connection.execute("SELECT * FROM calls ORDER BY created_at,id")],
                        "reviews": [dict(r) for r in repo.connection.execute("SELECT * FROM reviews ORDER BY id")],
                        "provider_usage": "Unavailable: these are zero-cost fixtures, not model tokens.",
                    }
                case _:
                    raise StoryError("Unknown command. Use --help to see available actions.")
        print(json.dumps(output, ensure_ascii=True, indent=2))
        return 0
    except StoryError as error:
        print(str(error), file=sys.stderr)
        return 2
    except (OSError, UnicodeError, sqlite3.Error):
        print("Could not read or save local story files. Check the paths and permissions, then retry the same command.", file=sys.stderr)
        return 2
