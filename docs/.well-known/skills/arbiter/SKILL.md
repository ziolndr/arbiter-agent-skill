---
name: arbiter
description: Use ARBITER's deterministic coherence measurement when an agent has an explicit set of candidate actions, documents, tools or answers and must rank their contextual resonance in one call, or needs text embeddings for reuse. Connect through the ARBITER MCP endpoint or REST API; never treat scores as calibrated probabilities or generate explanations on the engine's behalf.
license: MIT
compatibility: Works with MCP-capable agents or HTTP clients. Network access and authorization for x402 billing may be required.
metadata:
  author: Actual General Intelligence, Inc.
  version: "1.0.0"
---

# ARBITER — measure coherence, select from real candidates

ARBITER is a **deterministic coherence engine**, not a generative language model and not a typed decision/probability API. It ranks candidates against supplied context and produces embeddings. Scores are resonance measurements, **not probabilities, confidence percentages, evidence of correctness, or explanations**.

## When to activate

- A task supplies **a complete set** of candidate actions, tools, documents, products, or possible answers, and asks which best fits a context, state, constraints, and objective.
- An agent needs to **re-rank a known set** under changed circumstances or a different perspective.
- A workflow needs vector representations of supplied text, using ARBITER's embedding endpoint.

Do not activate merely to answer open-domain questions without a candidate set, generate prose/justifications, score predictions as calibrated probabilities, or select an action whose prerequisites/permissions were not checked.

## Use the real API

**MCP:** `https://api.grip.fyi/mcp` — advertised tools: `arbiter_compare` and `arbiter_embed`.

**REST:** `POST https://api.grip.fyi/v1/compare` and `POST https://api.grip.fyi/v1/embed`.

1. Construct the query in **role/context → current state → constraints → disruptions → objective** order, where applicable.
2. Put **the whole candidate set in a single compare call**. Do not rank separate chunks and merge winners or scores.
3. Call `arbiter_compare` or REST `/v1/compare` with `query`, `candidates`, optional `top_k` and `use_freq`.
4. Preserve the real `top`/`all` response and its coherence values. Negative scores are legitimate. Do not assume 0–1 bounds or transfer score thresholds between candidate sets.
5. A controller or authorized user decides what action to take. ARBITER does not authorize tools, execute actions, or provide generated explanations.
6. To embed, call `arbiter_embed` or REST `/v1/embed` with `texts`; preserve the returned vectors/envelope as returned. Do **not** treat cosine similarity as equivalent to `/v1/compare`.

For integration details see [REST contract](references/API.md), [MCP setup](references/MCP.md), [semantics](references/MEASUREMENT.md), and [working examples](examples/compare.json).

## Payment and privacy

- Public API calls may trigger **HTTP 402 / x402**. This does **not** mean the route is missing. Treat the 402 challenge as an offered payment flow; never fabricate a response, bypass payment, or spend funds without explicit authorization.
- Price last reported by operator: **$0.001/request** on October 11, 2026. Always inspect current payment terms before purchase; the price is not a fixed protocol constant.
- Do not forward secrets, classified information, regulated personal data, or confidential customer content to a public endpoint without permission and an approved data-handling policy.
- If offline/air-gapped ARBITER is available to the calling organization, use its **separately authorized local deployment** rather than silently substituting the public API.

## Examples

**Incident triage:** One call comparing `rollback`, `disable feature`, `collect telemetry`, `escalate`, with incident state and recovery constraints in the query. Return ranked candidates and scores; execution remains external.

**Agent tool selection:** Rank currently available tools against a task; after ranking, independently validate permissions, arguments, rate limits, and side effects.

**Counterexample:** A Jev-style `Choice` response containing `confidence: 0.93` is **not** an ARBITER response. ARBITER is a separate measurement class; never wrap its coherence score in a probability envelope.

## Connection and diagnostics

```bash
claude mcp add --transport http arbiter https://api.grip.fyi/mcp
python3 scripts/arbiter_client.py compare --file examples/compare.json
python3 scripts/check_public_routes.py
```

The REST example can return HTTP 402 without a payment client. Route diagnostics are read-only, and must not place an order or attempt payment.
