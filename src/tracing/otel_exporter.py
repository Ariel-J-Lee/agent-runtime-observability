"""OpenTelemetry-shaped JSON trace exporter (OTLP JSON spec subset).

v0 PLACEHOLDER. Real implementation arrives at Tier 4 in a future
implementation packet. This module exists only as a scaffold so the
project structure is visible. Importing this module succeeds; the
exporter is not implemented at v0.

See `docs/runtime-model.md` for the v1 trace shape (spans for
agent_step, llm_call, tool_call, policy_check, retry_attempt with
the documented attribute set).
"""
