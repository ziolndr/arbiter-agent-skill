#!/usr/bin/env python3
"""ARBITER JSON REST example. Stdlib only, no payment handling."""
import argparse
import json
import sys
import urllib.error
import urllib.request


def call(base, route, payload, timeout):
    url = base.rstrip('/') + route
    request = urllib.request.Request(
        url, data=json.dumps(payload).encode('utf-8'),
        headers={'Content-Type': 'application/json', 'Accept': 'application/json'},
        method='POST')
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read().decode('utf-8', 'replace')
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode('utf-8', 'replace')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=['compare', 'embed'])
    parser.add_argument('--file', required=True, help='JSON request payload path')
    parser.add_argument('--base', default='https://api.grip.fyi')
    parser.add_argument('--timeout', type=float, default=20)
    parser.add_argument('--dry-run', action='store_true', help='Validate and print request; no network use')
    args = parser.parse_args(argv)
    with open(args.file, encoding='utf-8') as f:
        payload = json.load(f)
    if not isinstance(payload, dict):
        parser.error('JSON input must be an object')
    if args.operation == 'compare':
        if not isinstance(payload.get('query'), str) or not payload['query'].strip():
            parser.error('compare.query must be a nonblank string')
        cands = payload.get('candidates')
        if not isinstance(cands, list) or not cands or any(not isinstance(c, str) or not c.strip() for c in cands):
            parser.error('compare.candidates must be a nonempty array of nonblank strings')
        if 'top_k' in payload and (type(payload['top_k']) is not int or not 1 <= payload['top_k'] <= len(cands)):
            parser.error('top_k must be an integer between 1 and the number of candidates')
    elif (not isinstance(payload.get('texts'), list) or not payload['texts'] or
          any(not isinstance(t, str) or not t.strip() for t in payload['texts'])):
        parser.error('embed.texts must be a nonempty array of nonblank strings')
    route = '/v1/' + args.operation
    if args.dry_run:
        print(json.dumps({'method': 'POST', 'url': args.base.rstrip('/') + route, 'body': payload}, indent=2))
        return 0
    try:
        status, body = call(args.base, route, payload, args.timeout)
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        print(f'NETWORK ERROR: {error}', file=sys.stderr)
        return 3
    print(f'HTTP {status}')
    try:
        print(json.dumps(json.loads(body), indent=2))
    except ValueError:
        print(body[:4000])
    if status == 402:
        print('PAYMENT REQUIRED: No payment attempted. Use an explicitly authorized x402 client.', file=sys.stderr)
        return 4
    return 0 if 200 <= status < 300 else 2


if __name__ == '__main__':
    sys.exit(main())
