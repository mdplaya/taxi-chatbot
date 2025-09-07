import pytest

# Mark legacy modules that rely on removed classes or outdated interfaces
LEGACY_SKIP = {
    'test_llm_fix.py': 'Legacy learning engine not present in current codebase',
    'test_phase4_demo.py': 'Legacy learning engine not present in current codebase',
    'test_agentic_implementation.py': 'Legacy Thought/Action API removed',
    'test_learning_system.py': 'Legacy LearningEngine removed',
    'test_llm_manager.py': 'Legacy LLMManager class removed; use utils.llm_manager.llm_manager',
    'test_timeout_config.py': 'Legacy LLMManager class removed',
    'test_valkey_integration.py': 'Legacy Thought interfaces removed',
}

def pytest_collection_modifyitems(config, items):
    for item in list(items):
        fname = item.fspath.basename
        if fname in LEGACY_SKIP:
            item.add_marker(pytest.mark.skip(reason=LEGACY_SKIP[fname]))

