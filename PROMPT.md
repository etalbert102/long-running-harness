# Prompt: Build an Autonomous Coding Harness

> Paste this into Claude Code (or any Claude session with tool access) to replicate the core build. Assumes you've read Anthropic's "Effective Harnesses for Long-Running Agents" research.

---

## The Prompt

Build an autonomous coding harness that takes a product spec (markdown file) and builds the software end-to-end without human intervention. The harness is a Python orchestrator using `claude-agent-sdk` that implements a planner/generator/evaluator agent loop.

### Architecture

```
Spec (markdown) → Planner → feature_list.json → Generator → Validators → Evaluator → repeat
```

**Three agent roles, each gets a fresh Claude session:**

1. **Planner** — reads the spec, decomposes into a feature list with BDD scenarios (given/when/then). Each feature has a `complexity` field: `setup`, `simple`, `moderate`, `complex`. Feature count scales to spec size (10-30 small, 50-150 medium, 200-400 large). Outputs `feature_list.json`.

2. **Generator** — picks the next incomplete feature, implements it, writes tests, commits. One feature per session. Fresh context every time. Updates `feature_list.json` (only flips `passes: false` → `true`). Prompt rule: "It is UNACCEPTABLE to remove or edit existing tests."

3. **Evaluator** — adversarial reviewer with a dedicated skeptic system prompt. Scores on 4 dimensions: spec compliance (35%), code quality (25%), security (25%), usability (15%). Minimum 7.0/10 to pass. High-severity security issues = automatic failure. Returns structured JSON with scores, issues, and recommendations.

**Key optimization: complexity tiers.** Setup and simple features skip the evaluator entirely — hard validators (tsc, eslint, build, test) are sufficient. This cuts runtime ~50%.

### Hard Validators (the agent cannot skip these)

After each generator session, run in sequence:
1. `npx tsc --noEmit` — type checking
2. `npx eslint .` — linting
3. `npm run build` — build succeeds
4. `npm test` — tests pass

If any fail, generator gets the error output and retries (max 3 attempts). Only then does the evaluator run (for moderate/complex features).

### The Loop (orchestrator.py)

```
1. Run planner (if no feature_list.json)
2. Loop:
   a. Pick next incomplete feature
   b. If setup/simple → generator + validators only (skip evaluator)
   c. If moderate/complex → generator + validators + evaluator
   d. Validator failures → retry generator with error feedback (max 3)
   e. Evaluator failures → retry generator with score feedback (max 2)
   f. On pass → commit, push timeline event, continue
3. Session complete
```

### Model Tiers

Support per-role model selection:
- `--model-generator claude-sonnet-4-6` (fast, good at coding)
- `--model-evaluator claude-opus-4-6` (deep, good at critique)

### Monitoring Dashboard

Build a lightweight Next.js dashboard (dark mode, Catppuccin Mocha theme) deployed on Vercel:
- Harness POSTs status updates to `/api/ingest` (webhook with bearer auth)
- State stored in Upstash Redis (free tier)
- Browser gets real-time updates via SSE from `/api/stream`
- Cards: status + elapsed timer, timeline, feature progress, sprint info, evaluator scores, cost tracker, commit feed
- Session history captured on completion for historical view

### Security

- Bash command allowlist hook (PreToolUse) — defense-in-depth
- Sandbox mode enabled via claude-agent-sdk
- Filesystem scoped to output directory
- Per-session cost caps (`max_budget_usd`)

### What makes this work

1. **Fresh context per feature** — no context anxiety, no rushing to finish
2. **Adversarial evaluation by a separate agent** — the generator can't grade its own homework
3. **Hard validators that can't be sweet-talked** — linter doesn't care about excuses
4. **Feature complexity tiers** — don't waste 5 minutes evaluating "npm install typescript"
5. **Immutable feature list** — generator can only flip `passes: false` → `true`, never delete or modify features

### Proof

Point this harness at a spec for a "mini JWT library" (ES256, Web Crypto API, zero dependencies). Result: 38/38 features, 76 tests, 96% coverage, 70 minutes, $9.27 on Claude Max.

---

## To replicate

1. `pip install claude-agent-sdk httpx gitpython`
2. Write the orchestrator, agents (planner/generator/evaluator), validators, and prompts
3. Write a product spec in markdown
4. Run: `python -m harness.main spec.md --model claude-sonnet-4-6 -v`
5. Watch it build

Reference implementation: https://github.com/shawnpetros/long-running-harness
