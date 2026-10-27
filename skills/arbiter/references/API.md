# ARBITER REST API — integration contract

API base: `https://api.grip.fyi`

| Method | Route | JSON request | Operator-described result |
| --- | --- | --- | --- |
| POST | `/v1/compare` | `query: string`, `candidates: string[]`, optional `top_k: integer`, `use_freq: boolean` | `top`, `all` (ranked coherence output) |
| POST | `/v1/embed` | `texts: string[]` | vectors for each supplied text |

The names and top-level result fields above come from the ARBITER operator's API contract, not a live schema snapshot. The exact nested result schema is intentionally **not invented**. Use the live response envelope. There is no assertion that `/docs` or `/openapi.json` exists on the API host.

## Compare

```bash
curl -i --max-time 20 -H 'Content-Type: application/json' \
  --data-binary @examples/compare.json https://api.grip.fyi/v1/compare
```

See [`examples/compare.json`](../examples/compare.json). Supply all candidates together. Rank once; no chunking, pairwise recombination, local invented rescoring, generic cosine substitution, or synthesized rationale.

For every run, keep the original query, supplied candidate set, response ordering, and scores together. Comparisons with different candidate universes must not silently be presented as the same experiment.

## Embed

```bash
curl -i --max-time 20 -H 'Content-Type: application/json' \
  --data-binary @examples/embed.json https://api.grip.fyi/v1/embed
```

The operator-described vectors have 72 dimensions. Do not assume a response JSON key for them if it has not been observed; inspect actual returned JSON.

## HTTP 402 and error handling

The API is listed as x402-paid. For an ordinary client without payment, a response `402 Payment Required` can be a valid service challenge. Preserve response headers/body; hand the challenge to the **authorized** payer. Do not retry payment automatically. Distinguish 402 from 404 (missing route), 405 (unsupported method), 429 (rate limit), 5xx (server error), and network/DNS failures.

Advertised price was $0.001 per request (as of 2026-10-11); verify the currently published price and supported networks before any transaction. A preexisting MCP registry listing and payment records do not by themselves guarantee present availability.

## Security boundaries

Never execute the top-ranked option automatically. Senders are responsible for authorization, PII/classified data restrictions, and logging policies. The ARBITER skill never changes the engine, its geometry, model weights, or server.
