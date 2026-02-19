# Changelog

## 2026-01-16
- Added `محاكي الجمهور` (Audience Simulation Sandbox, M7).
- Added backend graph pipeline (`load_policy_profile -> sanitize_input -> run_persona_simulation -> compute_scores -> generate_editor_advice -> persist_and_return`).
- Added simulator DB tables (`sim_runs`, `sim_results`, `sim_feedback`, `sim_calibration`, `sim_job_events`).
- Added API routes under `/api/v1/sim`.
- Added frontend page `/simulator` and Smart Editor integration button/tab.
