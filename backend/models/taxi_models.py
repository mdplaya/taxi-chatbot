from pydantic import BaseModel, Field, EmailStr, validator
from typing import Optional, List, Literal, Dict, Any
from enum import Enum
from datetime import datetime

class AppEnvironment(str, Enum):
    NONPROD = "NONPROD"
    PROD = "PROD"

class AppEnvironmentSubtype(str, Enum):
    DEV = "dev"
    QA = "qa"
    TEST = "test"
    PERF = "perf"

class LineOfBusiness(str, Enum):
    RETAIL = "RETAIL"
    ISTS = "ISTS"
    EDML = "EDML"

class OS(str, Enum):
    LINUX_RHEL8 = "LINUX_RHEL8"
    LINUX_RHEL9 = "LINUX_RHEL9"
    WINDOWS_19 = "WINDOWS_19"
    WINDOWS_22 = "WINDOWS_22"

class UseType(str, Enum):
    APP = "app"
    DATABASE = "database"

class MachineType(str, Enum):
    N1_STANDARD_1 = "n1-STANDARD-1"
    N2_STANDARD_1 = "n2-STANDARD-1"
    N3_STANDARD_1 = "n3-STANDARD-1"
    N4_STANDARD_1 = "n4-STANDARD-1"

class VMRequest(BaseModel):
    """User's VM request with optional fields"""
    appEnvironment: Optional[AppEnvironment] = None
    appEnvironmentSubtype: Optional[AppEnvironmentSubtype] = None
    lineOfBusiness: Optional[LineOfBusiness] = None
    costCenter: Optional[str] = Field(None, pattern=r"^\d{5}$")
    project: Optional[str] = None
    zone: Optional[str] = None
    os: Optional[OS] = None
    useType: Optional[UseType] = None
    machineType: Optional[MachineType] = None
    id: Optional[EmailStr] = None
    
    @validator('costCenter')
    def validate_cost_center(cls, v):
        if v and not (v.isdigit() and len(v) == 5):
            raise ValueError('Cost center must be exactly 5 digits')
        return v
    
    def get_missing_fields(self) -> List[str]:
        """Return list of required fields that are None"""
        required = ['appEnvironment', 'lineOfBusiness', 'costCenter', 
                   'project', 'zone', 'os', 'useType', 'machineType', 'id']
        
        # Add subtype if NONPROD
        if self.appEnvironment == AppEnvironment.NONPROD:
            required.append('appEnvironmentSubtype')
        
        missing = []
        for field in required:
            if getattr(self, field) is None:
                missing.append(field)
        
        return missing
    
    def to_taxi_payload(self) -> Dict[str, Any]:
        """Convert to TAXI API payload format"""
        return {
            "resourceMetadata": {
                "appIdentity": {
                    "type": "cvsappid",
                    "value": "APM0015867"
                },
                "appEnvironment": self.appEnvironment.value if self.appEnvironment else None,
                "appEnvironmentSubtype": self.appEnvironmentSubtype.value if self.appEnvironmentSubtype else None,
                "lineOfBusiness": self.lineOfBusiness.value if self.lineOfBusiness else None,
                "costCenter": self.costCenter,
                "sharedEmailAddress": "TAXIAutomation@CVShealth.com"
            },
            "project": self.project or "CORP-dev-broc-sechub-vpc",
            "networkProject": "CVS-securehub-prod",
            "network": "VPC-aacvs-hub-trusted-nonprod-1",
            "subnet": "sn-aacvs-use4-CORP-dev-broc-sechub-vpc-testing",
            "zone": self.zone,
            "os": self.os.value if self.os else None,
            "useType": self.useType.value if self.useType else None,
            "machineType": self.machineType.value if self.machineType else None,
            "description": "Instance created via TAXI chatbot",
            "additionalDisks": [
                {
                    "diskName": "req-DISK",
                    "diskSize": 100,
                    "vgName": "app_VG"
                }
            ],
            "options": {
                "dryRun": False,
                "requestSource": "ISTS",
                "requestor": {
                    "userType": "EMAIL",
                    "id": self.id
                }
            }
        }

class ChatSession(BaseModel):
    """Track conversation state"""
    session_id: str
    created_at: datetime
    vm_request: VMRequest
    status: Literal["gathering_info", "ready_to_provision", "provisioning", "complete", "failed"]
    messages: List[Dict[str, Any]] = []
    taxi_payload: Optional[Dict[str, Any]] = None
    taxi_response: Optional[Dict[str, Any]] = None
