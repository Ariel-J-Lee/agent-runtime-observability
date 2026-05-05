# Architecture

The v1 release ships a single-agent governed runtime. The architectural idea, in plain prose:

A single LLM reasons about a task and proposes tool calls. Every proposed tool call passes through a policy layer that checks the tool name, the arguments, and the runtime context against a declarative rule set; the policy decision is recorded as a first-class trace span before any tool actually runs. Allowed tool calls execute through deterministic stubs by default. Tool failures route through a bounded retry policy with a hard cap; exhaustion is itself a first-class failure mode in the catalog. State is recorded per step as JSONL so any run is rerunnable from the committed manifest. Traces are OpenTelemetry-shaped JSON, loadable in Jaeger or Grafana Tempo. Failure modes are detected and classified into a documented catalog with reproducible triggers.

## Diagram posture

There is no diagram at v0. A diagram lands at v1 once Tier-4 evidence makes it accurate; a diagram before evidence risks misrepresenting the implementation.

## Composition discipline

The v1 implementation deliberately avoids cloning any private agent-runtime composition. The orchestrator is a lightweight in-process agent loop, not a named workflow framework. The policy spec is YAML, declarative, and named with generic categories (URL allowlist, sandbox path, iteration budget, tool registry, argument schema). The trace exporter writes OpenTelemetry-shaped JSON without taking a hard SDK dependency at v1. The sandbox is filesystem-path-based at v1; container isolation is a v2 concern.

## Out of scope

This repo does not implement retrieval evaluation (a sibling repo owns that lane). It does not implement cloud-deployment infrastructure (another sibling repo owns that lane). It does not implement an engineering-enablement field kit. Cross-repo deployment is not part of any version of this repo.
