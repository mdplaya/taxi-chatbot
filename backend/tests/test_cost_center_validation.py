import pytest
import sys, os

# Ensure backend package paths are importable
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pydantic import ValidationError
from models.taxi_models import VMRequest


def test_cost_center_accepts_five_digits_on_init():
    req = VMRequest(costCenter="12345")
    assert req.costCenter == "12345"


@pytest.mark.parametrize("value", [
    "1234",      # too short
    "123456",    # too long
    "12a45",     # non-numeric
    "abcde",     # all non-numeric
])
def test_cost_center_rejects_invalid_on_init(value):
    with pytest.raises(ValidationError):
        VMRequest(costCenter=value)


def test_cost_center_accepts_valid_on_assignment():
    req = VMRequest()
    req.costCenter = "12345"
    assert req.costCenter == "12345"


@pytest.mark.parametrize("value", [
    "1234",
    "123456",
    "12a45",
])
def test_cost_center_rejects_invalid_on_assignment(value):
    req = VMRequest()
    with pytest.raises(ValidationError):
        req.costCenter = value

