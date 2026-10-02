"""Compatible entrypoint for local read-only story review.

No schema initialization, provider calls, key reads, approvals or edit routes.
This development server is not production hosting.
"""
import json
from pathlib import Path

from .review.snapshot import read_connection, story_snapshot, live_graph
from .review.server import create_server

__all__ = ['read_connection', 'story_snapshot', 'live_graph', 'create_server', 'main']


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Local read-only story review. No inference or edits.')
    parser.add_argument('--db', type=Path, required=True)
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--fixture', action='store_true', help='Clearly label demo material')
    parser.add_argument('--provider-receipt', type=Path)
    args = parser.parse_args()
    info = json.loads(args.provider_receipt.read_text(encoding='utf-8')) if args.provider_receipt else None
    server = create_server(args.db, port=args.port, fixture=args.fixture, provider_info=info)
    print(f'Read-only story review: http://127.0.0.1:{server.server_port}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
