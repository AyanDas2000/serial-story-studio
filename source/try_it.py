"""Run Serial Story Studio on your own computer, in practice mode.

Practice mode uses a scripted writer: nothing is sent anywhere, no key is needed
and nothing is charged. The desk listens on this computer only.

    python try_it.py            # then open http://127.0.0.1:8766/
    python try_it.py --open     # also opens your browser
    python try_it.py --port 9000 --stories my-series

Your series are kept in the "stories" folder next to this file, one folder per
series. The first time, a sample series is placed there for you to look around.

    python try_it.py --db my-story.db     # one story in one file, no shelf
"""
import argparse
import sys
import threading
import webbrowser
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from serial_story.studio.server import create_server  # noqa: E402
from serial_story.v1.api import claim_database  # noqa: E402
from serial_story.v1.provider import ScriptedProvider  # noqa: E402
from serial_story.v1.shelf import Shelf  # noqa: E402

SAMPLE = HERE / 'serial_story' / 'samples' / 'court-recorder.sample'


def serve(make, port):
    try:
        return make()
    except OSError:
        raise SystemExit(f'Port {port} is already in use. Another copy of this program may still be running. '
                         f'Close its window, or start this one on another port: python try_it.py --port {port + 1}')


def main() -> int:
    ap = argparse.ArgumentParser(description='Serial Story Studio, practice mode')
    ap.add_argument('--port', type=int, default=8766)
    ap.add_argument('--stories', default=str(HERE / 'stories'),
                    help='the folder where your series are kept (created if missing)')
    ap.add_argument('--db', default=None,
                    help='run one story from one file instead of the shelf (created if missing)')
    ap.add_argument('--open', action='store_true', help='open the browser when ready')
    args = ap.parse_args()

    if args.db:
        db = Path(args.db)
        db.parent.mkdir(parents=True, exist_ok=True)
        provider = ScriptedProvider()
        lease = claim_database(db, provider)  # noqa: F841  (held until this process ends)
        server = serve(lambda: create_server(db, port=args.port, writes=True, v1_path=db, v1_provider=provider), args.port)
        url = f'http://127.0.0.1:{args.port}/v1'
        print(f'Your story is kept in: {db.resolve()}')
    else:
        root = Path(args.stories)
        shelf = Shelf(root, ScriptedProvider, sample=SAMPLE)
        server = serve(lambda: create_server(shelf.root / '.legacy.db', port=args.port, writes=True, shelf=shelf), args.port)
        url = f'http://127.0.0.1:{args.port}/'
        print(f'Your series are kept in: {shelf.root}')
    print('Practice mode: nothing is sent anywhere and nothing is charged.')
    print(f'Open this in your browser: {url}')
    print('Press Ctrl+C to stop.')
    if args.open:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nStopped.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
