"""Policy / guardrail layer between LLM tool intent and tool execution.

This module ships the **policy seam** the runtime calls before every
tool execution. It does not ship the actual `policy/v1.yaml` rule set;
authoring the rules and the policy-gate fixtures is a downstream slice
(see ``docs/policy-gates.md``).

The seam exposes three things:

1. :class:`PolicySpec` — a typed, immutable wrapper around either a
   Python ``dict`` or a YAML file. The YAML import is **lazy**: this
   module does not depend on ``pyyaml`` at import time. Callers that
   only ever pass dicts (tests, programmatic configuration) pay no
   third-party dependency cost. ``PolicySpec.from_yaml_path`` imports
   ``pyyaml`` on call and raises :class:`ImportError` with a helpful
   message when the package is not installed.

2. :class:`PolicyDecision` — the typed result of a check. Carries the
   ``decision`` (``allow`` / ``deny`` / ``escalate``), the ``rule_id``
   that fired (``None`` when allowed), and a small ``metadata`` dict
   that the runtime forwards into the ``policy_check`` span attribute
   set documented in ``docs/runtime-model.md``.

3. :class:`PolicyChecker` — the call-site the agent loop invokes per
   intended tool call. The checker walks the rules registered in the
   :class:`PolicySpec` and returns the first denial; otherwise allows.
   The default ``PermissivePolicyChecker`` allows everything and is
   what the runtime smoke uses in the absence of a real policy spec —
   matching the scope rule that this packet ships seams, not rules.

Rule evaluation is small and stdlib-only at this slice:

- ``url_allowlist`` — ``fetch``-shape calls deny when the target URL's
  host is not in the allowlist; rule_id ``url_allowlist``.
- ``sandbox.path_allowlist`` — ``read`` / ``write``-shape calls deny
  when the target path's resolved real-path is outside the allowlist;
  rule_id ``sandbox_path``.
- ``tool_registry.allowed`` / ``tool_registry.denied`` — calls to a
  tool not in ``allowed`` or explicitly in ``denied`` deny with rule_id
  ``tool_registry``.
- ``loop_budget.max_iterations`` / ``max_tokens`` — the agent loop
  invokes a checker variant for the budget. rule_id ``loop_budget``.
- ``cycle_detection.max_repeats`` — the agent loop invokes a checker
  variant for cycle detection. rule_id ``cycle_detection``.
- ``arg_schema_enforcement`` — when the spec sets this to ``"strict"``,
  callers that supply a JSON-schema for a tool's inputs deny on
  validation failure. The schema validation itself is the caller's
  responsibility at this slice; the policy seam returns the structured
  denial.

The downstream T-POLICY slice authors ``policy/v1.yaml`` covering the
five PG scenarios documented in ``docs/policy-gates.md``. This module
is intentionally rule-light at this packet so the seam is reviewable
in isolation.
"""

from __future__ import annotations

import hashlib
import json
import os.path
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Literal, Mapping, Optional
from urllib.parse import urlparse

DecisionLiteral = Literal["allow", "deny", "escalate"]
DEFAULT_DECISION_ALLOW: DecisionLiteral = "allow"
DEFAULT_DECISION_DENY: DecisionLiteral = "deny"


class PolicyValidationError(ValueError):
    """Raised when ``policy/v1.yaml`` fails meta-schema validation.

    Carries the JSON-pointer-style path to the offending field plus a
    human-readable message. The runtime startup banner names the file
    path and the offending key so misconfiguration surfaces at startup
    rather than on the first denial.
    """

    def __init__(self, *, file_path: str, schema_path: str, message: str) -> None:
        self.file_path = file_path
        self.schema_path = schema_path
        self.message = message
        super().__init__(
            f"Policy validation failed for {file_path}"
            f" at {schema_path or '<root>'}: {message}"
        )


@dataclass(frozen=True)
class PolicyDecision:
    """The typed result of a policy check.

    ``rule_id`` is ``None`` for ``allow`` decisions and the firing
    rule's identifier for ``deny`` / ``escalate`` decisions. The
    ``metadata`` dict carries the ``policy_check`` span attributes
    documented in ``docs/runtime-model.md`` (e.g.,
    ``{"policy.url": "https://evil.test"}`` for a url-allowlist deny).
    """

    decision: DecisionLiteral
    rule_id: Optional[str] = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PolicySpec:
    """An immutable typed view over a policy specification.

    The spec is constructed from either a Python dict (the test path)
    or a YAML file (the operational path; lazy ``pyyaml`` import). The
    ``raw`` field carries the parsed mapping; the ``version`` field is
    the SHA-256 prefix of the canonical JSON serialization, used as the
    ``policy.version`` attribute on every ``policy_check`` span.
    """

    raw: Mapping[str, Any]
    version: str

    @staticmethod
    def _hash_version_from_dict(payload: Mapping[str, Any]) -> str:
        """SHA-256[:12] of the canonical JSON serialization of a dict.

        Used by ``from_dict`` so dict-built specs (the test path) still
        produce a deterministic ``policy.version``.
        """
        canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()[:12]

    @staticmethod
    def _hash_version_from_bytes(content: bytes) -> str:
        """SHA-256[:12] of the YAML file bytes.

        Per the canonical plan, the operational ``policy.version`` is
        the bytes hash so reviewers see byte-identical version strings
        across machines regardless of dict round-trip variations.
        """
        return hashlib.sha256(content).hexdigest()[:12]

    @classmethod
    def from_dict(cls, spec: Mapping[str, Any]) -> "PolicySpec":
        """Build a :class:`PolicySpec` from a dict (the test path)."""
        if not isinstance(spec, Mapping):
            raise TypeError(
                f"PolicySpec.from_dict requires a Mapping; got {type(spec).__name__}"
            )
        return cls(raw=dict(spec), version=cls._hash_version_from_dict(spec))

    @classmethod
    def from_yaml_path(cls, path: str | Path) -> "PolicySpec":
        """Build a :class:`PolicySpec` by parsing a YAML file.

        Steps:

        1. Import :mod:`yaml` lazily — this module's import path stays
           free of third-party dependencies.
        2. Read the file bytes and parse via ``yaml.safe_load``.
        3. Locate the meta-schema at ``<yaml-parent>/v1.schema.json`` and
           validate the parsed dict against it (raises
           :class:`PolicyValidationError` on failure).
        4. Pin ``policy.version`` to ``SHA-256(file-bytes)[:12]`` so two
           reviewers loading the same file produce byte-identical
           version strings.

        Raises:
            ImportError: when ``pyyaml`` is unavailable.
            ValueError: when the YAML does not parse to a mapping.
            PolicyValidationError: when the parsed spec violates the
                meta-schema. The error names the file path, the
                JSON-pointer to the offending field, and a one-line
                message.
        """
        try:
            import yaml  # type: ignore[import-not-found]
        except ImportError as exc:
            raise ImportError(
                "Reading YAML policy specs requires the 'pyyaml' package. "
                "Install with: pip install pyyaml. "
                "Alternatively, use PolicySpec.from_dict() with a parsed mapping."
            ) from exc
        p = Path(path)
        content = p.read_bytes()
        payload = yaml.safe_load(content)
        if payload is None:
            payload = {}
        if not isinstance(payload, Mapping):
            raise ValueError(
                f"Policy YAML at {p} must parse to a mapping; got {type(payload).__name__}"
            )

        # Locate v1.schema.json next to the YAML file and self-validate.
        schema_path = p.parent / "v1.schema.json"
        if schema_path.exists():
            from src.runtime._schema import SchemaError, validate

            with schema_path.open("r", encoding="utf-8") as f:
                schema = json.load(f)
            try:
                validate(dict(payload), schema)
            except SchemaError as exc:
                raise PolicyValidationError(
                    file_path=str(p),
                    schema_path=exc.path,
                    message=exc.message,
                ) from exc

        return cls(
            raw=dict(payload),
            version=cls._hash_version_from_bytes(content),
        )

    @classmethod
    def permissive(cls) -> "PolicySpec":
        """Return a permissive (allow-everything) spec for tests / smokes."""
        return cls.from_dict({})

    def get(self, dotted_key: str, default: Any = None) -> Any:
        """Read a dotted key (e.g. ``"loop_budget.max_iterations"``) from raw."""
        node: Any = self.raw
        for part in dotted_key.split("."):
            if not isinstance(node, Mapping) or part not in node:
                return default
            node = node[part]
        return node


class PolicyChecker:
    """The policy seam invoked per intended tool call.

    The checker is constructed once per agent run with a :class:`PolicySpec`,
    an optional sandbox-root, and an optional per-tool input
    JSON-schema map. Per-call inputs are an intended tool name plus
    the call's arguments. Returns a :class:`PolicyDecision` carrying
    the ``policy_check`` span metadata.

    Rule evaluation order (first-deny wins, locked by the canonical
    plan §1.6):

    1. ``tool_registry.denied`` — explicit denylist
    2. ``tool_registry.allowed`` — when present, only listed tools allowed
    3. ``url_allowlist`` — for tools whose args carry ``url``
    4. ``sandbox.path_template`` — for tools whose args carry ``path``
    5. ``arg_schema`` — when ``arg_schema_enforcement == "strict"`` and
       a tool schema is registered, validate args

    Loop-budget and cycle-detection rules fire on the agent step
    boundary via :meth:`check_loop_budget` and :meth:`check_cycle` and
    are not part of the per-call precedence.

    Args:
        spec: The :class:`PolicySpec` for this run.
        sandbox_root: Optional filesystem root for sandbox-path checks.
            When set, paths whose realpath is not under ``sandbox_root``
            deny with ``rule_id="sandbox_path"``. When ``None``, sandbox
            checks are disabled (used by tests that don't exercise the
            filesystem rule).
        tool_schemas: Optional ``{tool_name: input_json_schema}`` map.
            When the policy spec sets ``arg_schema_enforcement ==
            "strict"``, the constructor requires a schema for every
            allowed tool; absence raises ``ValueError``. The validator
            is :func:`src.runtime._schema.validate`.

    Raises:
        ValueError: when ``arg_schema_enforcement == "strict"`` and any
            tool in ``tool_registry.allowed`` lacks a schema in
            ``tool_schemas``.
    """

    def __init__(
        self,
        spec: PolicySpec,
        *,
        sandbox_root: Optional[str | Path] = None,
        tool_schemas: Optional[Mapping[str, Mapping[str, Any]]] = None,
    ) -> None:
        self.spec = spec
        self.sandbox_root: Optional[Path] = (
            Path(sandbox_root).resolve() if sandbox_root is not None else None
        )
        self.tool_schemas: Mapping[str, Mapping[str, Any]] = dict(tool_schemas or {})

        # Strict-mode init guard: when arg_schema_enforcement="strict",
        # every allowed tool must have a schema. Catches the operational
        # misconfiguration "policy declares strict but tool surface
        # didn't supply schemas" at construction, not at first check().
        enforcement = spec.get("arg_schema_enforcement", "off")
        if enforcement == "strict":
            allowed = spec.get("tool_registry.allowed", []) or []
            missing = [t for t in allowed if t not in self.tool_schemas]
            if missing:
                raise ValueError(
                    "arg_schema_enforcement='strict' requires a schema for every "
                    f"allowed tool; missing schemas for: {missing!r}. "
                    "Pass tool_schemas={...} to PolicyChecker, or set "
                    "arg_schema_enforcement: off in the policy spec."
                )

    def check(
        self,
        *,
        tool_name: str,
        tool_args: Mapping[str, Any],
    ) -> PolicyDecision:
        """Evaluate an intended tool call against the policy spec.

        Returns the first deny decision encountered; otherwise allow.
        """
        # 1. Explicit denylist
        denied = self.spec.get("tool_registry.denied", []) or []
        if tool_name in set(denied):
            return PolicyDecision(
                decision=DEFAULT_DECISION_DENY,
                rule_id="tool_registry",
                metadata={
                    "policy.requested_tool": tool_name,
                    "policy.registry_match": "denied",
                },
            )

        # 2. Allowlist (when present)
        allowed = self.spec.get("tool_registry.allowed", None)
        if allowed is not None and tool_name not in set(allowed):
            return PolicyDecision(
                decision=DEFAULT_DECISION_DENY,
                rule_id="tool_registry",
                metadata={
                    "policy.requested_tool": tool_name,
                    "policy.registry_match": "not_in_allowlist",
                },
            )

        # 3. URL allowlist
        url = tool_args.get("url") if isinstance(tool_args, Mapping) else None
        if url is not None:
            url_allowlist = self.spec.get("url_allowlist", None)
            if url_allowlist is not None:
                host = urlparse(str(url)).hostname or ""
                if host not in set(url_allowlist):
                    return PolicyDecision(
                        decision=DEFAULT_DECISION_DENY,
                        rule_id="url_allowlist",
                        metadata={
                            "policy.tool": tool_name,
                            "policy.url": str(url),
                            "policy.host": host,
                        },
                    )

        # 4. Sandbox path
        path_arg = (
            tool_args.get("path") if isinstance(tool_args, Mapping) else None
        )
        if path_arg is not None and self.sandbox_root is not None:
            real = Path(os.path.realpath(str(path_arg)))
            try:
                real.relative_to(self.sandbox_root)
            except ValueError:
                return PolicyDecision(
                    decision=DEFAULT_DECISION_DENY,
                    rule_id="sandbox_path",
                    metadata={
                        "policy.tool": tool_name,
                        "policy.target_path": str(path_arg),
                        "policy.resolved_path": str(real),
                        "policy.sandbox_root": str(self.sandbox_root),
                    },
                )

        # 5. arg_schema (strict-mode only; only when tool has a schema)
        enforcement = self.spec.get("arg_schema_enforcement", "off")
        if enforcement == "strict" and tool_name in self.tool_schemas:
            from src.runtime._schema import SchemaError, validate

            try:
                validate(dict(tool_args) if isinstance(tool_args, Mapping) else tool_args,
                         self.tool_schemas[tool_name])
            except SchemaError as exc:
                return PolicyDecision(
                    decision=DEFAULT_DECISION_DENY,
                    rule_id="arg_schema",
                    metadata={
                        "policy.tool": tool_name,
                        "policy.schema_error": exc.message,
                        "policy.failed_path": exc.path,
                    },
                )

        return PolicyDecision(decision=DEFAULT_DECISION_ALLOW)

    def check_loop_budget(
        self,
        *,
        iterations: int,
        tokens: int = 0,
    ) -> PolicyDecision:
        """Evaluate the loop budget mid-step.

        Returns a deny decision when ``iterations`` has reached
        ``loop_budget.max_iterations`` or ``tokens`` has reached
        ``loop_budget.max_tokens``. Used by the agent loop to short-
        circuit before another LLM call.
        """
        max_iter = self.spec.get("loop_budget.max_iterations", None)
        if max_iter is not None and iterations >= int(max_iter):
            return PolicyDecision(
                decision=DEFAULT_DECISION_DENY,
                rule_id="loop_budget",
                metadata={
                    "policy.iterations": iterations,
                    "policy.max_iterations": int(max_iter),
                    "policy.limit_kind": "iterations",
                },
            )
        max_tokens = self.spec.get("loop_budget.max_tokens", None)
        if max_tokens is not None and tokens >= int(max_tokens):
            return PolicyDecision(
                decision=DEFAULT_DECISION_DENY,
                rule_id="loop_budget",
                metadata={
                    "policy.tokens": tokens,
                    "policy.max_tokens": int(max_tokens),
                    "policy.limit_kind": "tokens",
                },
            )
        return PolicyDecision(decision=DEFAULT_DECISION_ALLOW)

    def check_cycle(
        self,
        *,
        repeats: int,
    ) -> PolicyDecision:
        """Evaluate cycle detection given the repeat count for the
        ``(tool, args)`` pair currently being attempted.
        """
        max_repeats = self.spec.get("cycle_detection.max_repeats", None)
        if max_repeats is not None and repeats >= int(max_repeats):
            return PolicyDecision(
                decision=DEFAULT_DECISION_DENY,
                rule_id="cycle_detection",
                metadata={
                    "policy.repeats": repeats,
                    "policy.max_repeats": int(max_repeats),
                },
            )
        return PolicyDecision(decision=DEFAULT_DECISION_ALLOW)


class PermissivePolicyChecker(PolicyChecker):
    """A checker that allows everything.

    Used as the agent's default when no policy spec is supplied. The
    ``PolicySpec`` underneath is ``PolicySpec.permissive()`` so the
    ``policy.version`` attribute is still well-defined on emitted span
    metadata.
    """

    def __init__(self) -> None:
        super().__init__(PolicySpec.permissive())
