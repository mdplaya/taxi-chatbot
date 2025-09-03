# GCE Validation and Normalization Implementation TODO

This file outlines the actionable steps to implement the GCE validation and normalization features.

## 0. Setup

- [ ] Create and switch to a new git branch for this feature. (e.g., `feature/gce-validation`)
- [ ] Ensure Docker environment is running.

## 1. Phase 1: Build the Data Foundation (`GCPDataManager`)

- [ ] Create new file: `backend/utils/gcp_data_manager.py`.
- [ ] Implement the `GCPDataManager` class as a singleton.
- [ ] In `GCPDataManager`, add logic to load `gcp_machine_types.csv` and `gcp_regions_and_supported_machine_types.csv` using pandas.
- [ ] Implement public method: `is_valid_machine_type(self, machine_type: str) -> bool`.
- [ ] Implement public method: `is_valid_region(self, region: str) -> bool`.
- [ ] Implement public method: `is_machine_type_supported_in_region(self, machine_type: str, region: str) -> bool`.
- [ ] Implement public method: `get_all_machine_types(self) -> list[str]`.
- [ ] Create new test file: `backend/tests/test_gcp_data_manager.py`.
- [ ] Write unit tests for `GCPDataManager` using mock CSV data, covering success and failure cases for all public methods.

## 2. Phase 2: Implement Strict Validation (`GCE_Specialist_Agent`)

- [ ] Modify file: `backend/agents/gce_specialist.py`.
- [ ] Import and instantiate `GCPDataManager` in the `GCE_Specialist_Agent`.
- [ ] Add validation logic to the agent's execution flow to call the `GCPDataManager` methods.
- [ ] Modify file: `backend/tests/test_gce_no_defaults.py`.
- [ ] Write integration tests for the `GCE_Specialist_Agent`, mocking the `GCPDataManager` to test the agent's response to both successful and failed validation.

## 3. Phase 3: Implement Intelligent Normalization (`Compute Agent`)

- [ ] Modify file: `backend/agents/compute.py`.
- [ ] Import and instantiate `GCPDataManager` in the `Compute Agent`.
- [ ] Add logic to call `gcp_data_manager.get_all_machine_types()`.
- [ ] Add logic to construct the LLM prompt for normalization.
- [ ] Add logic to call the LLM and process the response (either use the normalized value or trigger clarification).
- [ ] Modify file: `backend/tests/test_compute.py`.
- [ ] Write integration tests for the `Compute Agent`, mocking the `GCPDataManager` and the LLM to test successful normalization and the clarification fallback path.

## 4. Finalization and Verification

- [ ] Rebuild the Docker containers to ensure all new dependencies and changes are correctly integrated. Command: `docker-compose up --build -d`.
- [ ] Run all tests to confirm that the new features work and have not introduced any regressions.
- [ ] Review and commit the changes.
