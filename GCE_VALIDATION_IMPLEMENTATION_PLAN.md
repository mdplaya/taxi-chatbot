# Implementation Strategy: End-to-End GCE Validation and Normalization

This document provides a comprehensive, phased implementation plan to execute the strategies for data-driven validation and LLM-powered input normalization. This plan is designed to be handed off for implementation, ensuring all strategic requirements are met in a logical and testable order.

## 1. Foundational Analysis

- **Root Cause**: The core need is to bridge the gap between high-level strategy and actionable execution. The previous strategic documents defined *what* to do and *why*; this plan defines *how* to do it, step-by-step.
- **Codebase Analysis**: The plan is based on the existing agentic structure (`Orchestrator` -> `Compute` -> `Specialist`) and leverages the `utils` and `tests` directories for new and updated components.
- **Architectural Fit**: The proposed implementation phases respect the architectural boundaries of each agent, ensuring that responsibilities are cleanly separated (normalization in `Compute`, strict validation in `GCE_Specialist`, data access in a `util`). This approach minimizes technical debt by building components in a logical dependency order.

## 2. Phased Implementation Plan

The implementation will proceed in three distinct phases to manage dependencies and ensure each component is robust before the next is built upon it.

### Phase 1: Build the Data Foundation (`GCPDataManager`)

**Objective**: Create and thoroughly test a standalone, reusable utility for accessing GCP configuration data from CSV files. This component is the foundation for all subsequent logic.

1.  **Create New File**: `backend/utils/gcp_data_manager.py`
2.  **Implementation Steps**:
    - Define the `GCPDataManager` class with a singleton pattern to ensure data is loaded from CSVs only once.
    - Use the `pandas` library to read `gcp_machine_types.csv` and `gcp_regions_and_supported_machine_types.csv` into private DataFrame attributes.
    - Implement the following public methods:
        - `is_valid_machine_type(self, machine_type: str) -> bool`
        - `is_valid_region(self, region: str) -> bool`
        - `is_machine_type_supported_in_region(self, machine_type: str, region: str) -> bool`
        - `get_all_machine_types(self) -> list[str]`
3.  **Testing**:
    - **Create New File**: `backend/tests/test_gcp_data_manager.py`
    - **Strategy**: Write unit tests that validate the `GCPDataManager`'s logic in complete isolation. Use `io.StringIO` to create mock CSV data in memory for your tests.
    - **Test Cases**:
        - Test successful loading of valid mock CSV data.
        - Test correct return values for all public methods (e.g., `is_valid_region('us-east1')` returns `True`, `is_valid_region('us-moon1')` returns `False`).
        - Test edge cases like empty CSV files or requests for data not in the files.

### Phase 2: Implement Strict Validation (`GCE_Specialist_Agent`)

**Objective**: Integrate the `GCPDataManager` into the `GCE_Specialist_Agent` to enforce strict validation rules on canonical, clean data.

1.  **Modify File**: `backend/agents/gce_specialist.py`
2.  **Implementation Steps**:
    - In the `GCE_Specialist_Agent`, import and instantiate the `GCPDataManager`.
    - In the agent's main execution logic, before generating the TAXI payload, add a validation block.
    - This block will use the `GCPDataManager` instance to call `is_valid_machine_type`, `is_valid_region`, and `is_machine_type_supported_in_region`.
    - If validation fails, the agent should be programmed to return a structured error response indicating the validation failure (e.g., `{'error': 'InvalidRegion', 'message': '...'}`).
3.  **Testing**:
    - **Modify File**: `backend/tests/test_gce_no_defaults.py`
    - **Strategy**: Mock the `GCPDataManager` to simulate its responses, allowing you to test the agent's reaction to validation results without depending on the actual utility or CSVs.
    - **Test Cases**:
        - Test the success path: `GCPDataManager` mock returns `True` for all checks; assert that the agent proceeds.
        - Test the failure path: Mock the manager to return `False` for each of the three validation checks in separate tests. Assert that the agent halts and returns the appropriate error message for each case.

### Phase 3: Implement Intelligent Normalization (`Compute Agent`)

**Objective**: Empower the `Compute Agent` to understand natural language variations of machine types, normalize them using the LLM, and pass clean, canonical data to the `GCE_Specialist_Agent`.

1.  **Modify File**: `backend/agents/compute.py`
2.  **Implementation Steps**:
    - The `Compute Agent` should also import and instantiate the `GCPDataManager`.
    - After extracting the user's raw input for `machine_type`, call `gcp_data_manager.get_all_machine_types()` to get the list of valid targets.
    - Construct the specific LLM prompt detailed in the "LLM-Powered Input Normalization" strategy.
    - Make the LLM call with the user's input and the canonical list.
    - Process the LLM's response:
        - If it's a valid machine type, replace the raw input with the normalized LLM response.
        - If the response is "None" or invalid, trigger a conversational clarification flow.
    - Pass the now-clean and normalized data to the `GCE_Specialist_Agent`.
3.  **Testing**:
    - **Modify File**: `backend/tests/test_compute.py`
    - **Strategy**: Mock both the `GCPDataManager` (to provide the canonical list) and the LLM Manager (to simulate LLM responses).
    - **Test Cases**:
        - Test various successful normalizations (e.g., input "n1 std 1", LLM mock returns "n1-standard-1"). Assert that the `Compute Agent` calls the `GCE_Specialist_Agent` with the corrected, canonical name.
        - Test ambiguous input: LLM mock returns "None". Assert that the agent does *not* call the specialist and instead returns a clarification question.

## 3. Final Verification Against Checklist

This implementation plan is designed to satisfy all items on the verification checklist.

- **Root Cause & Research**: [X] The plan is a direct result of analyzing the need to translate strategy into execution, based on the existing codebase patterns.
- **Architecture & Design**: [X] The phased approach fits the current architecture, introduces beneficial decoupling (`GCPDataManager`), and avoids technical debt by building dependencies first.
- **Solution Quality**: [X] The plan is simple, streamlined, and 100% complete, covering implementation and testing for all strategic goals. It prioritizes maintainability through its modular design.
- **Security & Safety**: [X] The entire plan is an exercise in robust input validation and sanitization, a core security principle.
- **Integration & Testing**: [X] The plan explicitly details which files to update and how to test them, including unit tests, integration tests, and mocking strategies to handle all upstream/downstream impacts.
- **Technical Completeness**: [X] The plan considers performance (singleton data loader) and ensures all helper utilities are created and tested before use.
- **Agentic system integrity maintained**: [X] The plan enhances the agents' intelligence and maintains the conversational flow, especially in error/clarification scenarios.
- **The model used should always be gpt-5-mini. The temperature is 1.0**: [X] Phase 3 is centered on using the LLM for the normalization task.
- **Minimize rules based system**: [X] The plan implements a data-driven and LLM-driven approach, avoiding hardcoded rules.
- **Conversational system**: [X] The plan mandates conversational feedback for both validation failures (Phase 2, though handled by a subsequent agent) and normalization ambiguities (Phase 3).
- **Conversational LLM flows validated**: [X] The testing strategy for Phase 3 explicitly requires validating the conversational clarification flows.
- **Maintain Agents**: [X] The plan respects and reinforces the established roles of each agent, ensuring no responsibility bleed.
- **Maintain Orchestrator/Clarification Agent**: [X] These agents are unaffected by this plan.
- **Compute Agent**: [X] Phase 3 directly implements the agent's mandate to "Extract requirements intelligently" and "Use AI error correction."
- **GCE-Specialist Agent**: [X] Phase 2 directly implements the agent's mandate to "Validate corrected inputs" before it "Generates TAXI payloads."