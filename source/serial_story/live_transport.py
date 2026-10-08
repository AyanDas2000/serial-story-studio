"""HTTP transport for the Merge gateway. Kept outside serial_story/v1 on purpose: the v1 package must not import the network.
"""
import json
import time
import urllib.error
import urllib.request
from typing import Any, Callable

ORIGIN = 'https://api-gateway.merge.dev'
PATH = '/v1/openai/chat/completions'
Transport = Callable[[dict[str, Any]], tuple[int, Any, dict[str, str], float]]


class _NoRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def http_transport(key_supplier: Callable[[], str], timeout: int = 240) -> Transport:
    def send(payload: dict[str, Any]) -> tuple[int, Any, dict[str, str], float]:
        request = urllib.request.Request(
            ORIGIN + PATH, method='POST', data=json.dumps(payload).encode(),
            headers={'Authorization': 'Bearer ' + key_supplier(), 'Content-Type': 'application/json', 'Accept': 'application/json'})
        started = time.time()
        try:
            with urllib.request.build_opener(_NoRedirects).open(request, timeout=timeout) as response:
                headers = {n: response.headers.get(n) or '' for n in ('x-merge-model', 'x-merge-vendor', 'x-request-id')}
                return response.status, json.loads(response.read(4_000_000)), headers, time.time() - started
        except urllib.error.HTTPError as problem:
            raw = problem.read(20_000).decode('utf-8', 'replace')
            try:
                return problem.code, json.loads(raw), {}, time.time() - started
            except ValueError:
                return problem.code, raw, {}, time.time() - started
        except (OSError, ValueError):
            return 0, 'network error', {}, time.time() - started
    return send
