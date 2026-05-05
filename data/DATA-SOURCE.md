# Data Source Attestation

> **v0 PLACEHOLDER.** No data is committed at v0. The full attestation arrives at Tier 4 in a future implementation packet. The expected schema is documented below so the implementation packet has the structure ready.

## Expected schema (when populated at Tier 4)

```
- name: <dataset name>
- origin: <synthetic | public-domain | permissive-license | vendor-reference>
- source_url: <if applicable>
- license: <SPDX identifier or 'public-domain' or 'synthetic'>
- generation_script: <path, if synthetic>
- generation_seed: <integer, if synthetic>
- pii_check: <date and reviewer>
- customer_derivation_check: <statement that no private source was used>
- reconstruction_check: <statement that no private example was reconstructed>
- prompt_provenance: <statement of source for system prompts and user prompts in fixtures>
- tool_schema_provenance: <statement of source for tool JSON schemas>
- policy_spec_provenance: <statement of source for policy rule sets>
- demo_task_provenance: <statement of source for demo task scenarios>
```

## v0 status

No data files committed. No fixture files committed. The schema above is a forward-looking placeholder; its fields will be populated when the implementation packet ships fixtures.
