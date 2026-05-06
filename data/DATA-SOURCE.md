# Data Source Attestation

## Fixture corpus (`data/corpus/v1/`)

| Field | Value |
|---|---|
| name | `agent-runtime-observability v1 fixture corpus` |
| origin | synthetic |
| source_url | (not applicable — generated locally) |
| license | CC0-1.0 (see `data/LICENSE.fixture-corpus`) |
| generation_script | `scripts/build_fixture_corpus.py` |
| generation_seed | `20260506` |
| pii_check | 2026-05-06 — manual audit by Foundry; zero PII; see "Public-safety attestations" below |
| customer_derivation_check | None of the corpus content was derived from any customer, employer, vendor, or private workflow. |
| reconstruction_check | None of the corpus content reconstructs any private example, internal report, or proprietary template. |
| prompt_provenance | The canonical task fixture (`tasks/canonical/v1.json`) authors a synthetic question over the synthetic corpus. No prompt is sourced from any real workflow. |
| tool_schema_provenance | Tool input JSON-schemas live in `tools/<tool>.py` per PACKET-052 (`INPUT_SCHEMA` constants). |
| policy_spec_provenance | `policy/v1.yaml` per PACKET-048; corpus does not influence policy. |
| demo_task_provenance | Canonical demo task at `tasks/canonical/v1.json`; adversarial fixtures at `tasks/policy_gates/` and `tasks/failure_modes/` per PACKET-049 / PACKET-050. |

## Generator parameters

The generator at `scripts/build_fixture_corpus.py`:

- runs against `random.Random(20260506)`
- emits exactly 25 Markdown documents under `data/corpus/v1/op-a1.md` … `data/corpus/v1/op-a25.md`
- each document fits the structure `# <Title> / ## Summary / ## Findings (4 bullets) / ## Cadence / ## Notes`
- each document is ~750-870 characters (within the PACKET-046 §2.2 ~500-1500-char target)
- uses pure stdlib (`random`, `hashlib`, `json`, `pathlib`, `argparse`); no third-party dependency
- writes a manifest at `data/corpus/v1/manifest.json` carrying `{schema_version, seed, generator_path, doc_count, files: [{id, path, sha256, char_count}]}`
- the manifest carries no timestamp so reruns produce byte-identical files

Re-running the generator against the same seed produces byte-identical output. `python3 -m scripts.build_fixture_corpus --check` validates that the on-disk files match the manifest's recorded SHA-256 values without rewriting them.

## Public-safety attestations (per PACKET-003)

- **§6.3 PII rule.** No real names, no email addresses, no phone numbers, no addresses, no identifying tokens. The corpus only references fictitious entities `Operator-A1` … `Operator-A25` and fictitious organizations `Org-North`, `Org-South`, `Org-East`, `Org-West`. Reviewer audit on the date above confirmed zero PII matches.
- **§6.4 Customer-derivation rule.** None of the corpus content is paraphrased from, summarized from, or otherwise derived from any customer, employer, vendor, or private workflow. The vocabulary is a small fixed list of operations-domain phrases hand-authored for this fixture set.
- **§6.5 Reconstruction-from-private rule.** No private example was reconstructed. The generator builds documents combinatorially from the fixed vocabulary list checked into `scripts/build_fixture_corpus.py`.
- **§6.6 Public-safe vocabulary rule.** The corpus avoids brand-name vocabulary, internal control-plane vocabulary, and any silhouette-leaking vocabulary covered by PACKET-021 §3.

## License

The corpus is licensed CC0-1.0 (see `data/LICENSE.fixture-corpus`). The repository's root `LICENSE` (Apache-2.0) covers code; the corpus license is isolated to `data/` per PACKET-014 §10.

## Slice cap

PACKET-046 §2.2 sets a hard ceiling of 100 documents at v1; this slice ships 25 (the locked PM/QA default). Smaller is fine; the corpus is not a benchmark target.
