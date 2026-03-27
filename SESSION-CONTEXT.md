## Status

Project initialized. Scaffold created. Starting Phase 1 — dashboard build + harness core in parallel.

## In-Flight

- Creating project scaffold (CLAUDE.md, features.json, git init)
- Next: dashboard app + harness Python structure

## Key Details

- Harness uses `claude-agent-sdk>=0.1.0` (renamed from `claude-code-sdk`)
- Dashboard deploys to Vercel with Upstash Redis for state
- Harness pushes status to dashboard via POST webhook
- Agent-ID standard based on JWT profile with agent-specific claims (AIT)
- Research identified 8 active IETF drafts on agent identity — none adopted

## Next Steps

1. Build and deploy monitoring dashboard
2. Build harness core (client factory, security, orchestrator)
3. Write agent prompts (planner, generator, evaluator)
4. Write app_spec.md (AIT standard)
5. Test harness on trivial spec
6. Run harness on agent-id spec
