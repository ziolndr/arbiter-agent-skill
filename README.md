# ARBITER — Agent Skill

**Deterministic coherence measurement for agent tool routing, candidate arbitration, and embeddings.**

This repository publishes a portable Agent Skill that tells MCP/HTTP-capable agents **when and how** to use the existing ARBITER engine. This is not a new model or a replacement for its current MCP registration, and it never patches the engine.

## Install from GitHub after publishing

```bash
npx skills add <GitHub owner>/arbiter-agent-skill --skill arbiter -g
```

Or install the directory `skills/arbiter/` into `.agents/skills/arbiter/` (Codex and compatible clients) or `.claude/skills/arbiter/` (Claude Code). See [SKILL.md](skills/arbiter/SKILL.md).

## Connect the existing MCP service

```bash
claude mcp add --transport http arbiter https://api.grip.fyi/mcp
```

REST: `POST https://api.grip.fyi/v1/compare`, `POST https://api.grip.fyi/v1/embed`.

## Run tests

```bash
python3 scripts/validate_release.py
python3 -m unittest discover -s tests -v
python3 skills/arbiter/scripts/arbiter_client.py compare --file skills/arbiter/examples/compare.json --dry-run
```

No billing occurs in tests or validation. A 402 from REST is an expected payment challenge, not a missing route. Public API terms may change; inspect live x402 terms and obtain authorization before payment.

## Public documentation host

The optional standalone documentation service (`site.py`) publishes:

- `/` — human-friendly landing page
- `/skills/arbiter/SKILL.md` — canonical raw skill instructions
- `/.well-known/skills/arbiter/SKILL.md` — alternate discoverable URL
- `/agents.json` — machine-readable tool and endpoint discovery
- `/llms.txt` — text-first index
- `/manifest.json` — skill metadata
- `/openapi.json` — **integration contract documentation** (not a claim that the API host supports this route)
- `/healthz` — health check

Hosting separately avoids modifying ARBITER's existing public API server. The one-shot `DEPLOY_ARBITER_SKILL.command` runs without credential prompts or dashboard steps. It reuses existing local Cloudflare and GitHub CLI/SSH credentials to provision a dedicated tunnel and publish the repository; subsequent runs update only its verified managed repository. When established authorization is unavailable, publication fails explicitly (nonzero exit) instead of requesting manual authentication or claiming completion. Existing ARBITER services and unrelated tunnels are untouched.

## Why separate from typed decision models?

Jev-style Choice/Score/Noul returns typed values with calibrated probabilities. ARBITER measures coherence of candidates against context and returns rankings/scores; its outputs are neither probabilities nor generated reasoning. Different contract, different skill.

**Owner:** Actual General Intelligence, Inc. • **License:** MIT
