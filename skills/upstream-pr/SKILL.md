---
name: upstream-pr
description: Open small, test-backed HolmesGPT upstream PRs with DCO sign-off and a single-problem scope. Use when preparing Issues or PRs against the holmesgpt fork or upstream.
---

# Upstream PR

## Scope

Keep OpsPilot domain models, benchmark scenarios, and lab policy out of upstream.

Good upstream work:

- PR0: docs, toolset tests, Azure config example, small error handling
- PR1: `approval_required_tools` for custom YAML/MCP — reproduce, test, fix plumbing
- PR2: Azure MCP schema compatibility — exclude/isolate bad tools
- PR3: optional `traceparent` across Holmes → MCP

## Process

1. Open or align on an Issue first for anything larger than a typo
2. One problem per PR
3. Add or extend tests before the fix
4. Commit with `Signed-off-by`
5. Attach unit/integration/eval evidence in the PR body
6. Do not force-push to `main`/`master`

## Commit

```text
<area>: <why>

Signed-off-by: <name> <email>
```

## Local vs upstream

| Stays in OpsPilot | May go upstream |
|---|---|
| Incident lab, scenarios, scorers | Generic approval tests |
| Proposal domain model | Azure schema validation |
| Control-plane executor | MCP tool isolation |
| Verifier experiment | OTel context propagation |
