import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.clarification import ClarificationAgent


def test_reorder_questions_business_resource_specialist():
    agent = ClarificationAgent()

    # Mixed order: specialist first, then resource, then business
    mixed = [
        {"field": "machineType", "question": "mt?", "description": ""},
        {"field": "os", "question": "os?", "description": ""},
        {"field": "lineOfBusiness", "question": "lob?", "description": ""},
        {"field": "zone", "question": "zone?", "description": ""},
        {"field": "appEnvironment", "question": "env?", "description": ""},
    ]

    business = ["lineOfBusiness", "id", "appEnvironment", "appEnvironmentSubtype", "costCenter"]
    resource = ["useType", "os"]
    specialist = ["zone", "machineType"]

    ordered = agent._reorder_questions(mixed, business, resource, specialist)

    fields = [q["field"] for q in ordered]
    # Business fields should come first (lineOfBusiness, appEnvironment), preserve in-group order
    # Resource (os) next, Specialist (zone, machineType) last
    assert fields == [
        "lineOfBusiness", "appEnvironment",  # Business group (original relative order preserved)
        "os",                                  # Resource group
        "machineType", "zone"                 # Specialist group (original relative order preserved)
    ]
