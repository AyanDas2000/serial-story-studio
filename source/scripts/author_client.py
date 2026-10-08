"""A small client for the shelf's own HTTP API, for an author who works from a terminal instead of the browser.

It does nothing the desk's screens cannot do. Every call goes through the same commands, the same checks and the
same spend limit. It never reads or needs the Merge key: the desk process holds that.

    python scripts/author_client.py shelf
    python scripts/author_client.py new "Title" --live --cap 3
    python scripts/author_client.py state SLUG
    python scripts/author_client.py start SLUG
    python scripts/author_client.py direct SLUG skeleton @skeleton.json     # save and adopt
    python scripts/author_client.py direct SLUG arc @plan.json              # save and adopt (any length, 100 is fine)
    python scripts/author_client.py length SLUG 650 780 900                 # words per episode: shortest, aim, longest (omit numbers to read it)
    python scripts/author_client.py draft SLUG 1 5                          # commission episodes 1 to 5 (this spends money)
    python scripts/author_client.py episode SLUG 3                          # read one draft (and any set-aside draft)
    python scripts/author_client.py use SLUG 3                              # take episode 3's set-aside draft as its draft
    python scripts/author_client.py resume SLUG COMMISSION_ID               # carry on a paused run (spends money; keeps drafted episodes)
    python scripts/author_client.py edit SLUG 6 3 "new text"                 # replace paragraph 3 of episode 6 (or @file.txt); prints what it flags
    python scripts/author_client.py revalidate SLUG 7                       # say a later episode still fits after an earlier one changed
    python scripts/author_client.py accept SLUG 1 5                         # approve episodes 1 to 5 (the author's gate)
    python scripts/author_client.py memory SLUG                             # read what the desk now remembers
    python scripts/author_client.py cmd SLUG NAME '{"payload":...}'         # any other command

Use `--url http://127.0.0.1:8770` if the desk is not on the default port.
"""
import argparse
import json
import sys
import urllib.error
import urllib.request


class Desk:
    def __init__(self, url: str):
        self.url = url.rstrip('/')
        self.host = self.url.split('//', 1)[1]
        self.token = self.get('/api/session')['token']

    def _send(self, method: str, route: str, body=None):
        data = None if body is None else json.dumps(body).encode()
        headers = {'Origin': self.url, 'Content-Type': 'application/json'}
        if method == 'POST':
            headers['X-Studio-Token'] = self.token
        request = urllib.request.Request(self.url + route, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=900) as response:
                return response.status, json.loads(response.read())
        except urllib.error.HTTPError as problem:
            raw = problem.read()
            try:
                return problem.code, json.loads(raw)
            except ValueError:
                return problem.code, {'message': raw.decode('utf-8', 'replace')[:300]}

    def get(self, route: str):
        status, body = self._send('GET', route)
        if status != 200:
            raise SystemExit(f'{route}: {status} {body}')
        return body

    def post(self, route: str, body: dict):
        return self._send('POST', route, body)

    def new_series(self, title: str, live: bool, cap: float | None):
        body = {'title': title, 'writer': 'live' if live else 'practice'}
        if live and cap is not None:
            body['cap_usd'] = cap
        return self.post('/api/shelf/create', body)

    def command(self, slug: str, name: str, payload: dict, expected: dict | None = None):
        return self.post(f'/s/{slug}/api/v1/{name}', {'payload': payload, 'expected': expected or {}})

    def state(self, slug: str):
        return self.get(f'/s/{slug}/api/v1/state')

    def direct(self, slug: str, layer: str, content: dict):
        status, saved = self.command(slug, 'save_direction', {'layer': layer, 'content': content})
        if status != 200:
            return status, saved
        governing = (self.state(slug).get('governing') or {}).get(layer)
        return self.command(slug, 'adopt', {'revision_id': saved['revision_id']},
                            {'governing': governing['revision_id'] if governing else None})

    def edit(self, slug: str, ordinal: int, paragraph: int, text: str):
        episode = next((e for e in self.state(slug)['episodes'] if e['ordinal'] == ordinal and e.get('selection')), None)
        if episode is None:
            raise SystemExit(f'Episode {ordinal} has no draft to edit. Use `use` first if it only has a set-aside draft.')
        if not 1 <= paragraph <= len(episode['blocks']):
            raise SystemExit(f'Episode {ordinal} has {len(episode["blocks"])} paragraphs; choose 1 to {len(episode["blocks"])}.')
        blocks = [{'block_id': b['block_id'], 'text': text if i == paragraph else b['text']} for i, b in enumerate(episode['blocks'], 1)]
        return self.command(slug, 'save_revision', {'ordinal': ordinal, 'base_revision_id': episode['selection']['revision_id'], 'blocks': blocks},
                            {'selection_cas': episode['selection']['cas']})

    def accept(self, slug: str, first: int, last: int):
        snap = self.state(slug)
        picked = [e for e in snap['episodes'] if first <= e['ordinal'] <= last and e.get('selection')]
        group = [{'ordinal': e['ordinal'], 'revision_id': e['selection']['revision_id'], 'sha256': e['selection']['sha256']} for e in picked]
        return self.command(slug, 'accept_prefix', {'episodes': group}, {'canon_seq': snap['story']['canon_seq']})


def warn_if_paused(result) -> None:
    """A paused run still answers with status 200, so say so where a script's author will see it."""
    status, body = result
    if status == 200 and isinstance(body, dict) and body.get('status') == 'paused':
        print(f"PAUSED: {body.get('pause_reason')} (run {body.get('commission_id')}). The run did not finish. "
              "Read the state; `episode SLUG N` shows any set-aside draft.", file=sys.stderr)


def exit_code(result) -> int:
    """0 for success, 1 when the desk refused the request, 3 when a drafting run paused (so a script can tell)."""
    if isinstance(result, (list, tuple)) and len(result) == 2 and isinstance(result[0], int):
        status, body = result
        if status >= 400:
            return 1
        if isinstance(body, dict) and body.get('status') == 'paused':
            return 3
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--url', default='http://127.0.0.1:8770')
    sub = ap.add_subparsers(dest='what', required=True)
    sub.add_parser('shelf')
    new = sub.add_parser('new')
    new.add_argument('title')
    new.add_argument('--live', action='store_true')
    new.add_argument('--cap', type=float, default=None)
    state = sub.add_parser('state')
    state.add_argument('slug')
    cmd = sub.add_parser('cmd')
    cmd.add_argument('slug')
    cmd.add_argument('name')
    cmd.add_argument('payload', help='JSON object, or @file.json')
    cmd.add_argument('--expected', default='{}', help='JSON object, or @file.json')
    sub.add_parser('start').add_argument('slug')
    direct = sub.add_parser('direct')
    direct.add_argument('slug')
    direct.add_argument('layer', choices=['skeleton', 'arc'])
    direct.add_argument('content', help='JSON object, or @file.json')
    use = sub.add_parser('use')
    use.add_argument('slug')
    use.add_argument('ordinal', type=int)
    resume = sub.add_parser('resume')
    resume.add_argument('slug')
    resume.add_argument('commission_id')
    for name in ('draft', 'accept'):
        one = sub.add_parser(name)
        one.add_argument('slug')
        one.add_argument('first', type=int)
        one.add_argument('last', type=int)
    sub.add_parser('memory').add_argument('slug')
    edit = sub.add_parser('edit')
    edit.add_argument('slug')
    edit.add_argument('ordinal', type=int)
    edit.add_argument('paragraph', type=int)
    edit.add_argument('text', help='the new paragraph, or @file.txt')
    reval = sub.add_parser('revalidate')
    reval.add_argument('slug')
    reval.add_argument('ordinal', type=int)
    length = sub.add_parser('length')
    length.add_argument('slug')
    length.add_argument('numbers', nargs='*', type=int, help='shortest aim longest; leave out to read the current setting')
    episode = sub.add_parser('episode')
    episode.add_argument('slug')
    episode.add_argument('ordinal', type=int)
    args = ap.parse_args()

    def load(text: str):
        if text.startswith('@'):
            with open(text[1:], encoding='utf-8') as handle:
                return json.load(handle)
        return json.loads(text)

    desk = Desk(args.url)
    if args.what == 'shelf':
        out = desk.get('/api/shelf')
    elif args.what == 'new':
        out = desk.new_series(args.title, args.live, args.cap)
    elif args.what == 'state':
        snap = desk.state(args.slug)
        out = {'provider': {k: v for k, v in (snap.get('provider') or {}).items() if k != 'calls'},
               'canon_seq': (snap.get('story') or {}).get('canon_seq'),
               'planned': len(((snap.get('governing') or {}).get('arc') or {}).get('content', {}).get('intentions', [])),
               'commissions': snap.get('commissions'),
               'episodes': [{**{k: e.get(k) for k in ('ordinal', 'accepted', 'memory_state', 'words', 'length_warning', 'secret_hits')},
                             **({'set_aside': [{'words': a['words'], 'reason': a['detached_reason']} for a in e['alternatives']]} if e.get('alternatives') else {})}
                            for e in snap.get('episodes', []) if e.get('selection') or e.get('accepted') or e.get('alternatives')]}
    elif args.what == 'start':
        out = desk.command(args.slug, 'create_story', {})
    elif args.what == 'direct':
        out = desk.direct(args.slug, args.layer, load(args.content))
    elif args.what == 'draft':
        out = desk.command(args.slug, 'commission_arc', {'slots': [args.first, args.last]})
        warn_if_paused(out)
    elif args.what == 'resume':
        out = desk.command(args.slug, 'resume_commission', {'commission_id': args.commission_id})
        warn_if_paused(out)
    elif args.what == 'use':
        snap = desk.state(args.slug)
        episode = next((e for e in snap['episodes'] if e['ordinal'] == args.ordinal), None)
        aside = episode['alternatives'][-1] if episode and episode['alternatives'] else None
        if aside is None:
            raise SystemExit(f'Episode {args.ordinal} has no set-aside draft.')
        cas = episode['selection']['cas'] if episode.get('selection') else 0
        out = desk.command(args.slug, 'use_draft', {'ordinal': args.ordinal, 'revision_id': aside['revision_id']}, {'selection_cas': cas})
    elif args.what == 'accept':
        out = desk.accept(args.slug, args.first, args.last)
    elif args.what == 'length':
        if not args.numbers:
            out = desk.state(args.slug)['length']
        elif len(args.numbers) != 3:
            raise SystemExit('Give three numbers: shortest, aim, longest.')
        else:
            low, target, high = args.numbers
            out = desk.command(args.slug, 'set_length', {'low': low, 'target': target, 'high': high})
    elif args.what == 'edit':
        text = open(args.text[1:], encoding='utf-8').read().strip() if args.text.startswith('@') else args.text
        out = desk.edit(args.slug, args.ordinal, args.paragraph, text)
    elif args.what == 'revalidate':
        out = desk.command(args.slug, 'revalidate', {'ordinal': args.ordinal})
    elif args.what == 'memory':
        snap = desk.state(args.slug)
        out = snap.get('memory')
    elif args.what == 'cmd':
        out = desk.command(args.slug, args.name, load(args.payload), load(args.expected))
    else:
        snap = desk.state(args.slug)
        out = [e for e in snap.get('episodes', []) if e.get('ordinal') == args.ordinal] or {'message': 'No such episode yet.'}
    json.dump(out, sys.stdout, indent=2, ensure_ascii=True)
    print()
    return exit_code(out)


if __name__ == '__main__':
    raise SystemExit(main())
