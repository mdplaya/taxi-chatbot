from pydantic import BaseModel, Field, validator
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
    # E2 Series (Cost Optimized)
    E2_MICRO = "e2-micro"
    E2_SMALL = "e2-small"
    E2_MEDIUM = "e2-medium"
    E2_STANDARD_2 = "e2-standard-2"
    E2_STANDARD_4 = "e2-standard-4"
    E2_STANDARD_8 = "e2-standard-8"
    
    # N1 Series (Previous Gen)
    N1_STANDARD_1 = "n1-standard-1"
    N1_STANDARD_2 = "n1-standard-2"
    N1_STANDARD_4 = "n1-standard-4"
    N1_STANDARD_8 = "n1-standard-8"
    
    # N2 Series (Balanced)
    N2_STANDARD_2 = "n2-standard-2"
    N2_STANDARD_4 = "n2-standard-4"
    N2_STANDARD_8 = "n2-standard-8"
    N2_HIGHMEM_2 = "n2-highmem-2"
    N2_HIGHMEM_4 = "n2-highmem-4"
    
    # C2 Series (Compute Optimized)
    C2_STANDARD_4 = "c2-standard-4"
    C2_STANDARD_8 = "c2-standard-8"

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
    id: Optional[str] = None  # Email address
    
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
        
        # Helper function to safely get enum value
        def get_enum_value(field):
            if field is None:
                return None
            if isinstance(field, str):
                return field
            return field.value  # Enum instance
        
        return {
            "resourceMetadata": {
                "appIdentity": {
                    "type": "cvsappid",
                    "value": "APM0015867"
                },
                "appEnvironment": get_enum_value(self.appEnvironment),
                "appEnvironmentSubtype": get_enum_value(self.appEnvironmentSubtype),
                "lineOfBusiness": get_enum_value(self.lineOfBusiness),
                "costCenter": self.costCenter,
                "sharedEmailAddress": "TAXIAutomation@CVShealth.com"
            },
            "project": self.project or "CORP-dev-broc-sechub-vpc",
            "networkProject": "CVS-securehub-prod",
            "network": "VPC-aacvs-hub-trusted-nonprod-1",
            "subnet": "sn-aacvs-use4-CORP-dev-broc-sechub-vpc-testing",
            "zone": self.zone,
            "os": get_enum_value(self.os),
            "useType": get_enum_value(self.useType),
            "machineType": get_enum_value(self.machineType),
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

class ProgressStep(BaseModel):
    """Individual progress step in the agent pipeline"""
    timestamp: datetime
    agent: str  # Name of the agent performing the step
    step: str  # Description of what's happening
    status: Literal["started", "in_progress", "completed", "failed"]
    percentage: Optional[int] = None  # 0-100 progress percentage
    message: str  # User-friendly message
    metadata: Dict[str, Any] = {}

class ChatSession(BaseModel):
    """Track conversation state with progress tracking"""
    session_id: str
    created_at: datetime
    vm_request: VMRequest
    status: Literal["gathering_info", "ready_to_provision", "provisioning", "complete", "failed"]
    messages: List[Dict[str, Any]] = []
    taxi_payload: Optional[Dict[str, Any]] = None
    taxi_response: Optional[Dict[str, Any]] = None
    
    # Progress tracking fields
    progress_steps: List[ProgressStep] = []
    current_agent: Optional[str] = None
    current_step: Optional[str] = None
    last_progress_update: Optional[datetime] = None
    
    # Metadata for tracking additional context (like asked_fields)
    metadata: Dict[str, Any] = {}
    
    def add_progress(self, agent: str, step: str, message: str, 
                    status: str = "in_progress", percentage: Optional[int] = None) -> ProgressStep:
        """Add a progress step to the session"""
        progress = ProgressStep(
            timestamp=datetime.now(),
            agent=agent,
            step=step,
            status=status,
            percentage=percentage,
            message=message
        )
        self.progress_steps.append(progress)
        self.current_agent = agent
        self.current_step = step
        self.last_progress_update = datetime.now()
        return progress
    
    def get_latest_progress(self, limit: int = 10) -> List[ProgressStep]:
        """Get the most recent progress steps"""
        return self.progress_steps[-limit:] if self.progress_steps else []
