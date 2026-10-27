#!/usr/bin/env python3
"""Read-only GET/HEAD route diagnostics. Network failures and 402 reported distinctly."""
import argparse
import sys
import urllib.error
import urllib.request

DEFAULTS = [
    'https://api.grip.fyi/mcp',
    'https://api.grip.fyi/v1/compare',
    'https://api.grip.fyi/v1/embed',
    'https://api.grip.fyi/agents.json',
    'https://api.grip.fyi/x402.json',
    'https://api.grip.fyi/docs',
    'https://arbiter.grip.fyi/docs',
    'https://arbiter-skill.grip.fyi/skills/arbiter/SKILL.md',
]


def check(url, timeout=8):
    try:
        req = urllib.request.Request(url, method='GET', headers={'User-Agent': 'ARBITER-skill-route-check/1.0'})
        with urllib.request.urlopen(req, timeout=timeout) as response:
            status = response.status
    except urllib.error.HTTPError as error:
        status = error.code
    except (urllib.error.URLError, OSError, TimeoutError) as error:
        return 'NETWORK', str(error)
    if status == 402:
        meaning = 'paid route (not 404)'
    elif status == 404:
        meaning = 'missing route'
    elif status == 405:
        meaning = 'GET not supported; verify POST contract'
    elif 200 <= status < 300:
        meaning = 'GET served'
    else:
        meaning = f'HTTP {status}; inspect route/method'
    return str(status), meaning


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('urls', nargs='*', default=DEFAULTS)
    args = p.parse_args()
    for url in args.urls:
        status, meaning = check(url)
        print(f'{status:>8}  {url}  [{meaning}]')
    print('Note: GET of an MCP POST endpoint or paid REST endpoint is not a full availability test.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
