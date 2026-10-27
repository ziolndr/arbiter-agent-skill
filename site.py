#!/usr/bin/env python3
"""Read-only ARBITER Agent Skill publication server (stdlib only)."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
import argparse
import json
import os

ROOT = Path(__file__).resolve().parent
SKILL = ROOT / 'skills' / 'arbiter'
HOSTNAME = os.environ.get('ARBITER_SKILL_HOST', 'arbiter-skill.grip.fyi')
ORIGIN = 'https://' + HOSTNAME


def manifest():
    return {
        'name': 'arbiter',
        'version': '1.0.0',
        'description': 'Deterministic coherence ranking and text embeddings for agents.',
        'publisher': 'Actual General Intelligence, Inc.',
        'skill_url': ORIGIN + '/skills/arbiter/SKILL.md',
        'skill_format': 'https://agentskills.io/specification',
        'mcp': {'transport': 'streamable-http', 'url': 'https://api.grip.fyi/mcp',
                'tools': ['arbiter_compare', 'arbiter_embed']},
        'rest': {'compare': 'https://api.grip.fyi/v1/compare',
                 'embed': 'https://api.grip.fyi/v1/embed'},
        'billing': {'scheme': 'x402', 'check_current_terms': True,
                    'requires_explicit_payment_authorization': True}
    }


def openapi():
    # Deliberately specify only verified operator-described top-level fields.
    return {
        'openapi': '3.1.0', 'info': {'title': 'ARBITER integration reference', 'version': '1.0.0',
                                   'description': 'Operator-described request contracts. Exact response envelopes must be read from the live service. API routes may require x402 payment.'},
        'servers': [{'url': 'https://api.grip.fyi'}],
        'paths': {
            '/v1/compare': {'post': {'summary': 'Measure coherence of one complete candidate set',
                                    'requestBody': {'required': True, 'content': {'application/json': {'schema': {
                                        'type': 'object', 'additionalProperties': True,
                                        'required': ['query', 'candidates'],
                                        'properties': {'query': {'type': 'string'}, 'candidates': {'type': 'array', 'minItems': 1, 'items': {'type': 'string'}},
                                                       'top_k': {'type': 'integer', 'minimum': 1}, 'use_freq': {'type': 'boolean'}}}}}},
                                    'responses': {'200': {'description': 'Ranked coherence output with top/all fields',
                                                          'content': {'application/json': {'schema': {'type': 'object', 'properties': {'top': {}, 'all': {}}, 'additionalProperties': True}}}},
                                                  '402': {'description': 'Payment challenge; explicit payer authorization required'}}}},
            '/v1/embed': {'post': {'summary': 'Compute embeddings for supplied texts',
                                  'requestBody': {'required': True, 'content': {'application/json': {'schema': {
                                      'type': 'object', 'required': ['texts'], 'additionalProperties': True,
                                      'properties': {'texts': {'type': 'array', 'minItems': 1, 'items': {'type': 'string'}}}}}}},
                                  'responses': {'200': {'description': 'Embedding results; preserve actual live envelope'},
                                                '402': {'description': 'Payment challenge; explicit payer authorization required'}}}}
        }
    }


def page():
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>ARBITER — Agent Skill</title><meta name="description" content="Deterministic coherence measurement. One call. Complete candidate set.">
<style>*{{box-sizing:border-box}}body{{margin:0;background:#fafafa;color:#101010;font:17px/1.62 -apple-system,BlinkMacSystemFont,Helvetica,Arial,sans-serif}}a{{color:inherit}}main{{max-width:840px;margin:9vh auto 60px;padding:0 24px}}header{{font-size:13px;letter-spacing:.19em;font-weight:700}}h1{{font-size:clamp(46px,8vw,86px);letter-spacing:-.065em;line-height:.95;font-weight:750;margin:56px 0 35px}}.deck{{font-size:24px;letter-spacing:-.025em;line-height:1.35;max-width:690px}}.rule{{height:1px;background:#d1d1d1;margin:46px 0 28px}}p{{max-width:690px}}pre{{background:#151515;color:#fafafa;padding:18px 20px;overflow-x:auto;font-size:14px;line-height:1.6;border-radius:2px}}.rows{{display:grid;grid-template-columns:1fr 1fr;gap:12px}}.item{{display:block;padding:18px 18px;border:1px solid #aaa;text-decoration:none;font-weight:600}}.item:hover{{background:#e6e6e6}}small{{color:#555}}@media(max-width:600px){{.rows{{grid-template-columns:1fr}}main{{margin-top:35px}}}}</style></head>
<body><main><header>ACTUAL GENERAL INTELLIGENCE / ARBITER</header><h1>Agent skill.</h1>
<p class="deck">Deterministic coherence measurement for the choices agents already have.</p>
<p>Supply context, state, constraints, objective, and the full candidate set. ARBITER ranks the alternatives by resonance. No generative inference. No invented justification. No probability masquerading as coherence.</p>
<div class="rule"></div><small>CONNECT EXISTING MCP SERVICE</small>
<pre>claude mcp add --transport http arbiter https://api.grip.fyi/mcp</pre>
<small>READ AGENT INSTRUCTIONS</small><div class="rows"><a class="item" href="/skills/arbiter/SKILL.md">SKILL.md</a><a class="item" href="/manifest.json">Skill manifest</a><a class="item" href="/openapi.json">REST contract</a><a class="item" href="/agents.json">Agent discovery</a><a class="item" href="/skills/arbiter/references/MCP.md">MCP integration</a><a class="item" href="/skills/arbiter/references/MEASUREMENT.md">Measurement rules</a></div>
<div class="rule"></div><p><small>PUBLIC API</small><br><a href="https://api.grip.fyi/mcp">api.grip.fyi/mcp</a> · REST: /v1/compare + /v1/embed</p>
<p><small>Payment may be required via x402. Coherence scores are not calibrated probabilities. ARBITER's computation is unchanged by this skill.</small></p></main></body></html>'''


def resolve(path):
    # Paths not explicitly mapped are never served (no private files, no directory traversal).
    if path in ('/', '/index.html'):
        return page().encode(), 'text/html; charset=utf-8'
    if path == '/healthz':
        return json.dumps({'ok': True, 'skill': 'arbiter'}).encode(), 'application/json'
    if path in ('/manifest.json', '/.well-known/skills.json'):
        return json.dumps(manifest(), indent=2).encode(), 'application/json'
    if path == '/agents.json':
        return json.dumps({'skills': [manifest()], 'tools': ['arbiter_compare', 'arbiter_embed']}, indent=2).encode(), 'application/json'
    if path == '/openapi.json':
        return json.dumps(openapi(), indent=2).encode(), 'application/json'
    if path == '/llms.txt':
        return ('# ARBITER Agent Skill\n\n' + ORIGIN + '/skills/arbiter/SKILL.md\n' +
                ORIGIN + '/skills/arbiter/references/API.md\n' +
                ORIGIN + '/skills/arbiter/references/MCP.md\n' +
                'MCP https://api.grip.fyi/mcp\n').encode(), 'text/plain; charset=utf-8'
    if path == '/robots.txt':
        return b'User-agent: *\nAllow: /\n', 'text/plain; charset=utf-8'
    if path == '/sitemap.xml':
        return (f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>{ORIGIN}/</loc></url><url><loc>{ORIGIN}/skills/arbiter/SKILL.md</loc></url></urlset>').encode(), 'application/xml'
    if path in ('/SKILL.md', '/skill.md', '/.well-known/skills/arbiter/SKILL.md',
                '/.well-known/agent-skills/arbiter/SKILL.md'):
        path = '/skills/arbiter/SKILL.md'
    prefix = '/skills/arbiter/'
    if path.startswith(prefix):
        rel = path[len(prefix):]
        allowed = {'SKILL.md', 'references/API.md', 'references/MCP.md',
                   'references/MEASUREMENT.md', 'examples/compare.json', 'examples/embed.json'}
        if rel in allowed:
            filename = SKILL / rel
            mime = 'application/json' if filename.suffix == '.json' else 'text/markdown; charset=utf-8'
            return filename.read_bytes(), mime
    return None, None


class Handler(BaseHTTPRequestHandler):
    server_version = 'ARBITER-Agent-Skill/1.0'

    def do_HEAD(self):
        self.handle_get(head=True)

    def do_GET(self):
        self.handle_get(head=False)

    def handle_get(self, head=False):
        path = urlsplit(self.path).path
        data, mime = resolve(path)
        if data is None:
            self.send_error(404, 'Not found')
            return
        self.send_response(200)
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'public, max-age=300' if path != '/healthz' else 'no-cache')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        if not head:
            self.wfile.write(data)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=9433)
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f'ARBITER skill docs serving on {args.host}:{args.port}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()


if __name__ == '__main__':
    main()
