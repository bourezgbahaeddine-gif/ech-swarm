# Changelog

## 2026-01-16
- Added `محاكي الجمهور` (Audience Simulation Sandbox, M7).
- Added backend graph pipeline (`load_policy_profile -> sanitize_input -> run_persona_simulation -> compute_scores -> generate_editor_advice -> persist_and_return`).
- Added simulator DB tables (`sim_runs`, `sim_results`, `sim_feedback`, `sim_calibration`, `sim_job_events`).
- Added API routes under `/api/v1/sim`.
- Added frontend page `/simulator` and Smart Editor integration button/tab.

## 2026-02-19
- Fixed constitution gate deadlock when no active constitution metadata exists.
- Added fallback responses for `/constitution/latest` and `/constitution/ack` when metadata is missing.
- Added emergency auto-seed on constitution acknowledge flow.
- Fixed Smart Editor Tiptap duplicate `link` extension warning.
- Hardened article HTML rendering to reduce React runtime crashes caused by malformed HTML payloads.
- Added clearer backend error behavior for simulator migration-missing scenarios.
