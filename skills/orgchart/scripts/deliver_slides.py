#!/usr/bin/env python3
"""Send a --split-dir compile to a Google Slides deck without an agent relay.

Reads manifest.json, page-NNN.json and cleanup.json from a split directory and
posts each file to presentations.batchUpdate. Pages already present in the deck
are skipped, so a run can resume. Cleanup is sent last, only after every page
succeeded. After the pages arrive the slides are reordered to geometry order.

Authentication: pass an OAuth access token with the Slides scope through the
environment variable named by --token-env (default ORGCHART_SLIDES_TOKEN). The
token is never printed or written. A failed write is never replayed: a batch
that errors may or may not have applied, so the script stops and says which
page to inspect.
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

API = 'https://slides.googleapis.com/v1/presentations/'


class SlidesError(RuntimeError):
    pass


def http_json(method, url, token, body=None):
    data = None if body is None else json.dumps(body, separators=(',', ':')).encode()
    request = urllib.request.Request(url, data=data, method=method, headers={
        'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            return json.loads(response.read().decode() or '{}')
    except urllib.error.HTTPError as error:
        raise SlidesError(f'HTTP {error.code} from Slides API: {error.read().decode()[:300]}') from None
    except (urllib.error.URLError, TimeoutError) as error:
        raise SlidesError(f'Slides API request did not complete ({error}); outcome unknown') from None


def slide_ids(presentation):
    return [slide['objectId'] for slide in presentation.get('slides', [])]


def page_slide_id(requests):
    for request in requests:
        if 'createSlide' in request:
            return request['createSlide']['objectId']
    raise SlidesError('page file has no createSlide request')


def deliver(directory, presentation_id, token, transport=http_json, reorder=True, cleanup=True, log=print):
    directory = Path(directory)
    manifest = json.loads((directory / 'manifest.json').read_text())
    base = API + presentation_id
    existing = slide_ids(transport('GET', base + '?fields=slides.objectId', token))
    order, sent, skipped = [], [], []
    for entry in manifest['files']:
        requests = json.loads((directory / entry['file']).read_text())
        sid = page_slide_id(requests)
        order.append(sid)
        if sid in existing:
            skipped.append(entry['file']); continue
        try:
            transport('POST', base + ':batchUpdate', token, {'requests': requests})
        except SlidesError as error:
            raise SlidesError(f"{entry['file']} failed: {error}. Do not resend blindly; inspect slide {sid} first.") from None
        sent.append(entry['file']); log(f"sent {entry['file']} ({len(requests)} requests)")
    result = {'sent': sent, 'skipped': skipped, 'reordered': False, 'cleanup': False}
    if reorder and order:
        moves = [{'updateSlidesPosition': {'slideObjectIds': [sid], 'insertionIndex': index}} for index, sid in enumerate(order)]
        current = slide_ids(transport('GET', base + '?fields=slides.objectId', token))
        wanted = [sid for sid in current if sid in order]
        if wanted != order:
            transport('POST', base + ':batchUpdate', token, {'requests': moves})
        result['reordered'] = True
    if cleanup and manifest.get('cleanup'):
        requests = json.loads((directory / manifest['cleanup']['file']).read_text())
        live = set(slide_ids(transport('GET', base + '?fields=slides.objectId', token)))
        requests = [r for r in requests if r.get('deleteObject', {}).get('objectId') in live]
        if requests:
            transport('POST', base + ':batchUpdate', token, {'requests': requests})
        result['cleanup'] = True
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('split_dir')
    parser.add_argument('--presentation-id', required=True)
    parser.add_argument('--token-env', default='ORGCHART_SLIDES_TOKEN')
    parser.add_argument('--no-reorder', action='store_true')
    parser.add_argument('--no-cleanup', action='store_true')
    args = parser.parse_args(argv)
    token = os.environ.get(args.token_env)
    if not token:
        print(f'Set {args.token_env} to a Slides-scoped OAuth access token.', file=sys.stderr); return 2
    try:
        result = deliver(args.split_dir, args.presentation_id, token, reorder=not args.no_reorder, cleanup=not args.no_cleanup)
    except SlidesError as error:
        print(str(error), file=sys.stderr); return 1
    print(json.dumps(result)); return 0


if __name__ == '__main__':
    raise SystemExit(main())
