#!/usr/bin/env python3
"""Validate published agent skill content and safety of bundle, without network."""
from pathlib import Path
import json
import re
import sys

BASE = Path(__file__).resolve().parents[1]
SKILL = BASE / 'skills' / 'arbiter'


def main():
    problems = []
    source = (SKILL / 'SKILL.md').read_text(encoding='utf-8')
    if not source.startswith('---\n') or source.count('\n---\n') < 1:
        problems.append('SKILL.md: missing YAML frontmatter')
    else:
        metadata = source.split('\n---\n', 1)[0][4:]
        fields = dict(re.findall(r'^([a-z-]+):\s*(.*)$', metadata, re.M))
        name = fields.get('name', '')
        description = fields.get('description', '')
        if not re.fullmatch('[a-z0-9]+(?:-[a-z0-9]+)*', name) or len(name) > 64 or name != SKILL.name:
            problems.append('name is invalid or differs from skill directory')
        if not 1 <= len(description) <= 1024:
            problems.append('description must have 1..1024 characters')
    for path in SKILL.rglob('*'):
        if path.is_symlink():
            problems.append(f'symlinks not allowed: {path}')
    for rel in ('references/API.md', 'references/MCP.md', 'references/MEASUREMENT.md',
                'scripts/arbiter_client.py', 'scripts/check_public_routes.py',
                'examples/compare.json', 'examples/embed.json'):
        if not (SKILL / rel).is_file():
            problems.append(f'missing: {rel}')
    for fname in ['compare', 'embed']:
        payload = json.loads((SKILL / 'examples' / f'{fname}.json').read_text())
        if fname == 'compare':
            if not payload.get('query') or not payload.get('candidates') or len(payload['candidates']) != payload.get('top_k'):
                problems.append('invalid compare fixture')
        elif not payload.get('texts'):
            problems.append('invalid embed fixture')
    import site as stdlib_site # noqa: F401
    sys.path.insert(0, str(BASE))
    import importlib.util
    spec = importlib.util.spec_from_file_location('arbiter_skill_site', BASE / 'site.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for route in ('/', '/SKILL.md', '/skills/arbiter/SKILL.md',
                  '/.well-known/skills/arbiter/SKILL.md', '/manifest.json',
                  '/openapi.json', '/agents.json', '/llms.txt', '/healthz'):
        data, ctype = module.resolve(route)
        if not data or not ctype:
            problems.append('bad hosted route: ' + route)
    if module.resolve('/.ssh/id_rsa')[0] is not None or module.resolve('/skills/arbiter/../LICENSE')[0] is not None:
        problems.append('path whitelist broken')
    api_spec = module.openapi()
    if set(api_spec['paths']) != {'/v1/compare', '/v1/embed'}:
        problems.append('api contract mismatch')
    if problems:
        for err in problems:
            print('FAIL:', err)
        return 1
    print('PASS: skill metadata, files, fixtures, hosted routes, API contract, path whitelist')
    return 0


if __name__ == '__main__':
    sys.exit(main())
