"""Run the shelf with real writers (Merge models). Not part of the practice-only trial zip.

    .venv/Scripts/python.exe run_shelf_live.py --stories local/author-shelf --port 8770

A series made here can use the practice writer (free) or a live writer. Each live series has its own
spend limit (default $3, at most $5) and its own spend log in its own folder, so one series can never
spend another series' money. Restarting does not reset what was spent.

The key is read by the program itself from the file named .env next to it (or from the MERGE_GATEWAY_API_KEY environment\nvariable) and is never shown or stored in a series.
A live series cannot be opened on a desk that was not started with this file; it is never run on the
practice writer in its place.
"""
import argparse
import os
import sys
import threading
import webbrowser
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from serial_story.live_transport import http_transport  # noqa: E402
from serial_story.studio.server import create_server  # noqa: E402
from serial_story.v1.merge_provider import MergeProvider, find_key  # noqa: E402
from serial_story.v1.provider import ProviderUnavailable, ScriptedProvider  # noqa: E402
from serial_story.v1.shelf import Live, Shelf  # noqa: E402

SAMPLE = HERE / 'serial_story' / 'samples' / 'court-recorder.sample'


def live_builder(key_loader):
    transport = http_transport(key_loader)

    def build(folder: Path, cap_usd: float) -> MergeProvider:
        return MergeProvider(transport=transport, spend_log=folder / 'story.spend.jsonl', cap_usd=cap_usd)
    return build


def main() -> int:
    ap = argparse.ArgumentParser(description='Serial Story Studio shelf with live writers')
    ap.add_argument('--port', type=int, default=8770)
    ap.add_argument('--stories', default=str(HERE / 'local' / 'author-shelf' if (HERE / 'local').exists() else HERE / 'stories'))
    ap.add_argument('--env', default=str(HERE / '.env'), help='file that holds the Merge key')
    ap.add_argument('--max-cap', type=float, default=5.0, help='highest limit a series may be given (at most 5)')
    ap.add_argument('--default-cap', type=float, default=3.0)
    ap.add_argument('--sample', action='store_true', help='also place the practice sample series on the shelf')
    ap.add_argument('--open', action='store_true')
    args = ap.parse_args()
    if not 0 < args.default_cap <= args.max_cap <= 5:
        ap.error('Limits must satisfy 0 < default-cap <= max-cap <= 5.')

    try:
        key = find_key(Path(args.env), os.environ)
    except ProviderUnavailable as problem:
        raise SystemExit(f'{problem}\nPractice mode needs no key: python try_it.py')
    live = Live(build=live_builder(lambda: key), max_cap=args.max_cap, default_cap=args.default_cap)
    shelf = Shelf(Path(args.stories), ScriptedProvider, sample=SAMPLE if args.sample else None, live=live)
    try:
        server = create_server(shelf.root / '.legacy.db', port=args.port, writes=True, shelf=shelf)
    except OSError:
        raise SystemExit(f'Port {args.port} is already in use. Another copy of this program may still be running. '
                         f'Close its window, or start this one on another port: python run_shelf_live.py --port {args.port + 1}')
    url = f'http://127.0.0.1:{args.port}/'
    print(f'LIVE shelf via Merge. Series folder: {shelf.root}')
    print(f'Each live series gets its own limit (default ${args.default_cap:.2f}, at most ${args.max_cap:.2f}).')
    print(f'Open: {url}')
    if args.open:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nstopped')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
