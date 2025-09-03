import sys, os
import pytest

# Ensure backend package paths are importable when running tests directly
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.taxi_models import VMRequest, AppEnvironment, AppEnvironmentSubtype


def test_subtype_infers_nonprod_when_env_none():
    req = VMRequest(appEnvironmentSubtype=AppEnvironmentSubtype.DEV)
    assert req.appEnvironment == AppEnvironment.NONPROD


def test_subtype_overrides_prod_to_nonprod():
    req = VMRequest(appEnvironment=AppEnvironment.PROD,
                    appEnvironmentSubtype=AppEnvironmentSubtype.QA)
    assert req.appEnvironment == AppEnvironment.NONPROD


def test_nonprod_without_subtype_is_missing_in_get_missing_fields():
    req = VMRequest(appEnvironment=AppEnvironment.NONPROD)
    missing = req.get_missing_fields()
    assert 'appEnvironmentSubtype' in missing


def test_nonprod_with_subtype_not_missing():
    req = VMRequest(appEnvironment=AppEnvironment.NONPROD,
                    appEnvironmentSubtype=AppEnvironmentSubtype.TEST)
    missing = req.get_missing_fields()
    assert 'appEnvironmentSubtype' not in missing

