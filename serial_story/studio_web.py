"""Writable authoring studio entrypoint. Loopback only, explicit writes switch."""
from pathlib import Path

from .studio.server import create_server


def main():
    import argparse
    parser = argparse.ArgumentParser(
        description='Local authoring studio. Writes stay off unless you pass --enable-writes.')
    parser.add_argument('--db', type=Path, required=True,
                        help='Path to a NEW story database you chose for this studio.')
    parser.add_argument('--port', type=int, default=8766)
    parser.add_argument('--enable-writes', action='store_true',
                        help='Allow setup, planning, drafting and acceptance in this session.')
    parser.add_argument('--enable-merge-catalog', action='store_true',
                        help='Allow the read-only Merge model catalog check (GET only).')
    parser.add_argument('--enable-merge-generation', action='store_true',
                        help='Permit explicit per-call preflight and confirmation, never automatic writing.')
    args = parser.parse_args()
    if args.enable_merge_generation and not (args.enable_writes and args.enable_merge_catalog):
        parser.error('--enable-merge-generation requires --enable-writes and --enable-merge-catalog')
    server = create_server(args.db, port=args.port, writes=args.enable_writes,
                           merge_catalog=args.enable_merge_catalog, merge_generation=args.enable_merge_generation)
    mode = 'writable' if args.enable_writes else 'read-only'
    print(f'Authoring studio ({mode}): http://127.0.0.1:{server.server_port}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
