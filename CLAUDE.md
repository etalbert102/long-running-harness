# Agent-ID

## Purpose

Autonomous coding harness + monitoring dashboard that builds an open standard for AI agent identity and trust attestation (Agent Identity Token / AIT). The harness uses a planner/generator/evaluator agent loop to produce three deliverables: an IETF-style spec, a TypeScript reference SDK, and a Vercel-hosted verification service.

## Brain Sync

Search terms: `agent-id`, `agent identity`, `trust attestation`, `AIT`, `harness`, `Avistar`, `open standard`, `RSAC`

## Feature Tracker

See `features.json` for structured phase/feature tracking using STOP framework.

Current phases:
- P0: Direction & Foundation
- P1: Harness (Python orchestrator)
- P2: Dashboard (Next.js monitor)
- P3: Agent-ID Spec (IETF Internet-Draft)
- P4: Reference SDK (@agent-id/sdk)
- P5: Verification Service (Next.js API)

## Project Structure

```
agent-id/
├── dashboard/       # Next.js monitoring app (Vercel-deployed)
├── harness/         # Python autonomous coding orchestrator
├── output/          # Where the harness generates agent-id code
├── north-star.txt   # Strategic vision
└── features.json    # STOP framework feature tracker
```

## Rules

- Branch workflow: work on `dev` branch, merge to `main` only when ready for production
- Debug logging required in all API routes and server actions
- The harness generates code into `output/` — never manually edit that directory
- Dashboard is a personal dev tool — no auth needed, keep it minimal
- `claude-agent-sdk` (not `claude-code-sdk`) is the correct Python package
