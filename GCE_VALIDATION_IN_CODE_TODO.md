# GCE Validation (In‑Code Catalog) — Implementation TODO

This plan implements deterministic, in‑code validation for GCE machine types and regions, while preserving the agentic, conversational flow. It merges the strengths of the existing GCE_VALIDATION_IMPLEMENTATION_TODO (clear separation and testability) with your preference to avoid CSV/pandas at runtime by moving the data into a code catalog module.

## Summary

- Replace CSV/pandas runtime dependency with a pure‑Python catalog (`backend/utils/gcp_catalog.py`).
- Add small, deterministic helpers to validate:
  - Submitted machine types
  - Regions and zones
  - Machine family support in a region
- Wire validation into `GCESpecialistAgent._build_taxi_payload` to request clarifications (no defaults, no auto‑fixing).
- Extend tests in `backend/tests/test_gce_no_defaults.py` to cover invalid machine type, invalid zone/region, and unsupported family in region.
- Keep agentic behavior: LLM handles extraction/clarification; catalog enforces hard facts only.

## Rationale

- You prefer information to be in code over managing CSVs.
- Deterministic validation prevents invalid payloads from reaching provisioning.
- Minimal “rules engine”: we validate factual constraints only (types, regions, compatibility). All conversational correction and inference stays with the LLM agents.
- Lower runtime risk: no file I/O or heavy dependencies (pandas) in the hot path.

## Files To Add / Modify

- Add: `backend/utils/gcp_catalog.py`
- Modify: `backend/agents/gce_specialist.py`
- Modify: `backend/tests/test_gce_no_defaults.py`
- Optional (dev‑only): `automation/gen_gcp_catalog.py` to regenerate constants from CSVs, never used at runtime.

## Implementation Details

### 1) backend/utils/gcp_catalog.py (new)

Purpose: Provide in‑code constants and helper functions for GCE validation.

- Constants (committed in code):
  - `SUPPORTED_MACHINE_TYPES: set[str]` — full curated list of supported GCP machine types.
  - `SUPPORTED_ZONES: set[str]` — zones from the dataset (e.g., `us-east4-a`).
  - `SUPPORTED_REGIONS: set[str]` — derived from zones (prefix before the trailing zone letter, e.g., `us-east4`).
  - `REGION_SUPPORTED_FAMILIES: dict[str, set[str]]` — e.g., `{ 'us-west2': {'E2','N2','N2D','N1','C4','C3','C3D','T2D'} }` using union across that region’s zones.

- Helper functions (all type‑hinted):
  - `def is_valid_machine_type(machine_type: str) -> bool` — exact match against `SUPPORTED_MACHINE_TYPES`.
  - `def is_valid_zone(zone: str) -> bool` — exact match against `SUPPORTED_ZONES`.
  - `def parse_region(zone_or_region: str) -> str` — from `us-east4-a` → `us-east4`; from `us-east4` → `us-east4`.
  - `def is_valid_region(region: str) -> bool` — exact match against `SUPPORTED_REGIONS`.
  - `def machine_family(machine_type: str) -> str` — returns uppercased family prefix (e.g., `n4-standard-2` → `N4`, `e2-small` → `E2`, `n2d-standard-16` → `N2D`).
  - `def is_family_supported_in_region(family: str, region: str) -> bool` — checks `REGION_SUPPORTED_FAMILIES[region]`.
  - Optional: `def get_all_machine_types() -> list[str]` for future Compute Agent normalization prompts.

Notes:
- The initial constants can be generated once from your CSVs (dev‑only script) and then committed. No runtime CSV reads.
- Keep the module pure (no side effects, no I/O) and stable.

### 2) backend/agents/gce_specialist.py (modify)

In `_build_taxi_payload` (after verifying all required fields are present and before returning the payload):

1. Import helpers from `backend.utils.gcp_catalog`.
2. Validate machine type:
   - If `not is_valid_machine_type(machineType)`, return `needs_clarification=True` with a targeted question and a short reason.
3. Validate zone and region:
   - If `not is_valid_zone(zone)`, return `needs_clarification=True` with a question for a valid zone.
   - Compute `region = parse_region(zone)`; if `not is_valid_region(region)`, return clarification for region/zone.
4. Validate region/family support:
   - Determine `family = machine_family(machineType)`.
   - If `not is_family_supported_in_region(family, region)`, return clarification suggesting supported families for that region.

Contract:
- DO NOT introduce defaults.
- DO NOT silently “fix” values.
- Preserve all existing behavior for success path; enriched only with validation checks for correctness.

### 3) backend/tests/test_gce_no_defaults.py (modify)

Add tests while keeping current tests intact:

- Invalid machine type:
  - `machineType='e2-notreal'` and a valid zone → expect `needs_clarification=True`, missing field ‘machineType’ in questions, include a reason mentioning invalid type.

- Invalid zone:
  - `zone='us-mars1-a'` (or malformed) with otherwise valid fields → expect `needs_clarification=True`, field ‘zone’.

- Unsupported family in region:
  - Use `zone` in a region that lacks a family entirely (e.g., `us-west2-a` has no `N4` in any zone). With `machineType='n4-standard-2'` → expect `needs_clarification=True`, reason indicates N4 unsupported in region, suggest supported families.

- Valid configuration (existing test) remains unchanged and returns a valid TAXI payload.

### 4) Optional Dev Tool: automation/gen_gcp_catalog.py

Small script to regenerate constants from the CSVs for maintainers. Output is a Python file that defines the constant sets and dicts. This script is not used at runtime.

## Acceptance Criteria

- Deterministic validation in `_build_taxi_payload` prevents invalid machine types/zones/regions and unsupported families from producing a TAXI payload.
- When invalid, agent returns `needs_clarification=True` with targeted questions; no defaults added.
- Existing tests still pass; new tests for invalid cases pass.
- No runtime CSV parsing or pandas dependency in the validation path.

## Test Plan

- Run: `pytest -q backend`
- Verify: all tests in `backend/tests/test_gce_no_defaults.py` pass, including new cases.
- Sanity: manual checks against a few machine types and regions to ensure happy path unchanged.

## Build & Run

- Rebuild containers: `docker-compose up --build -d`
- API: http://localhost:8000, UI: http://localhost:3000
- Local backend (optional):
  - `cd backend && pip install -r requirements.txt`
  - `uvicorn api.main:app --reload --host 0.0.0.0 --port 8000`

## Notes on Agentic Integrity

- Model stays `gpt-5-mini` (temperature remains unchanged from current config).
- Clarification and extraction remain conversational and powered by LLMs; the catalog only enforces factual validation.
- Minimal rule‑based surface: no heuristics, only exact matches and compatibility by documented support.

## Step‑By‑Step TODO (Checklist)

1) Add catalog module
- [ ] Create `backend/utils/gcp_catalog.py` with constants and helpers listed above.

2) Wire validations into GCE Specialist
- [ ] Import helpers in `backend/agents/gce_specialist.py`.
- [ ] In `_build_taxi_payload`, after required fields are present:
  - [ ] Validate `machineType` via `is_valid_machine_type`.
  - [ ] Validate `zone` via `is_valid_zone`.
  - [ ] Derive `region = parse_region(zone)` and validate `is_valid_region`.
  - [ ] Validate `machine_family(machineType)` is supported in `region`.
  - [ ] On failure, return `needs_clarification=True` with targeted questions and a one‑line reason.

3) Update tests
- [ ] Extend `backend/tests/test_gce_no_defaults.py` with cases for: invalid machine type, invalid zone, and unsupported family in region. Keep current tests intact.

4) Verify
- [ ] `pytest -q backend` passes.
- [ ] `docker-compose up --build -d` succeeds; manual sanity checks.

