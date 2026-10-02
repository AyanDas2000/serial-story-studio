"""Self-contained, read-only graph export; no server, dependencies or network."""
import base64
import hashlib
import html
import json
from pathlib import Path
import re
from typing import Any

from .records import StoryError


ASSETS = Path(__file__).with_name('assets')


def render_graph(graph: dict[str, Any]) -> str:
    nodes, edges = graph.get('nodes', []), graph.get('edges', [])
    ids = {n['id'] for n in nodes}
    if len(ids) != len(nodes) or any(re.fullmatch(r'(entity|fact|episode|situation|direction)-[1-9][0-9]*', i) is None for i in ids):
        raise StoryError('Graph nodes need unique, recognized identifiers.')
    if any(e['source'] not in ids or e['target'] not in ids for e in edges):
        raise StoryError('A graph connection is missing its source or target.')
    data = json.dumps(graph, ensure_ascii=False).replace('&', '\\u0026').replace('<', '\\u003c').replace('>', '\\u003e').replace('\u2028', '\\u2028').replace('\u2029', '\\u2029')
    script = (ASSETS / 'graph.js').read_text(encoding='utf-8')
    script_hash = base64.b64encode(hashlib.sha256(script.encode('utf-8')).digest()).decode('ascii')
    font = base64.b64encode((ASSETS / 'IBMPlexSans[wdth,wght].ttf').read_bytes()).decode('ascii')
    styles = (ASSETS / 'tokens.css').read_text(encoding='utf-8').replace('__FONT_DATA__', font)
    license_text = html.escape((ASSETS / 'OFL.txt').read_text(encoding='utf-8'))
    csp = f"default-src 'none'; script-src 'sha256-{script_hash}'; style-src 'unsafe-inline'; font-src data:; img-src data:; connect-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none'"
    page = (ASSETS / 'graph-template.html').read_text(encoding='utf-8')
    values = {'__CSP__': csp, '__STYLES__': styles, '__FONT_LICENSE__': license_text,
              '__GRAPH_DATA__': data, '__GRAPH_SCRIPT__': script}
    # Single substitution pass: inserted story text cannot act as a template marker.
    return re.sub('|'.join(re.escape(k) for k in values), lambda match: values[match.group()], page)
