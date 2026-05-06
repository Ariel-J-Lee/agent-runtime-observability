# Data

The v1 fixture corpus and its supporting attestations.

## Layout

| Path | Purpose |
|---|---|
| `data/DATA-SOURCE.md` | Per-corpus attestation: origin, license, seed, public-safety attestations per PACKET-003 §6 |
| `data/LICENSE.fixture-corpus` | CC0-1.0 license text covering the corpus only; isolated from the Apache-2.0 root LICENSE per PACKET-014 §10 |
| `data/corpus/v1/op-a1.md` … `op-a25.md` | 25 Markdown documents (synthetic operations / policy reports for fictitious entities) |
| `data/corpus/v1/manifest.json` | `{schema_version, seed, generator_path, doc_count, files: [{id, path, sha256, char_count}]}`. No timestamp so reruns produce byte-identical files |

## Determinism

Reproducing the corpus from scratch:

```sh
make fixture-build
```

Verifying the on-disk files match the manifest:

```sh
python3 -m scripts.build_fixture_corpus --check
```

Generator: `scripts/build_fixture_corpus.py`. Seed: `20260506`. Two reviewers running the generator against the same seed produce byte-identical files.

## License posture

The corpus carries a CC0-1.0 license isolated to `data/`. Code (everything else in this repo) carries the Apache-2.0 license at the repository root. The two licenses do not interact.
