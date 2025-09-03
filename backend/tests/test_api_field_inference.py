import sys
import os

# Ensure backend package is on path when running from repo root
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from api.main import infer_field_from_question


def test_infer_machine_type_from_question():
    q = "Which GCP machine type (e.g., e2-small, n1-standard-1)?"
    assert infer_field_from_question(q) == "machineType"


def test_infer_zone_from_question():
    q = "Which GCP zone should we use (e.g., us-east4-a)?"
    assert infer_field_from_question(q) == "zone"


def test_infer_os_from_question():
    q = "Which OS should we use?"
    assert infer_field_from_question(q) == "os"


def test_infer_use_type_from_question():
    q = "Is this for an app or a database?"
    assert infer_field_from_question(q) == "useType"


def test_infer_project_from_question():
    q = "Which project should this run in?"
    assert infer_field_from_question(q) == "project"

