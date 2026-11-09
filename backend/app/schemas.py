from pydantic import BaseModel, EmailStr, Field, ConfigDict
from typing import Literal

Category = Literal["Technical Issue","Billing & Payments","Account & Login","Product Issue","Subscription","General Inquiry"]
Priority = Literal["Critical","High","Medium","Low"]
Status = Literal["Open","In Progress","Pending","Escalated","Resolved"]

class TicketCreate(BaseModel):
    customer_name: str = Field(min_length=2, max_length=120)
    customer_email: str = Field(min_length=5, max_length=255, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    subject: str = Field(min_length=4, max_length=250)
    description: str = Field(min_length=10, max_length=10000)

class StatusUpdate(BaseModel):
    status: Status
    note: str | None = None

class Classification(BaseModel):
    category: Category
    priority: Priority
    sentiment: Literal["Positive","Neutral","Negative"]
    intent: str
    main_issue: str
    summary: str
    recommended_next_action: str

class Source(BaseModel):
    document_name: str
    chunk_id: str

class Resolution(BaseModel):
    summary: str
    category: Category
    priority: Priority
    sentiment: Literal["Positive","Neutral","Negative"]
    root_cause: str
    resolution_steps: list[str]
    customer_response: str
    sources: list[Source]
    confidence: float = Field(ge=0, le=1)
    escalation_required: bool
    escalation_reason: str | None = None

class NoteCreate(BaseModel):
    note: str = Field(min_length=2, max_length=5000)

class EditResponse(BaseModel):
    customer_response: str = Field(min_length=5, max_length=10000)

class RejectResponse(BaseModel):
    reason: str = Field(min_length=5, max_length=1000)


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=128)

class UserResponse(BaseModel):
    id: int
    email: str
    full_name: str
    role: Literal["Admin", "Agent", "Viewer"]
    is_active: bool

    model_config = ConfigDict(from_attributes=True)

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse

# --------------------------------------------------
# USER MANAGEMENT SCHEMAS
# --------------------------------------------------

class UserCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=120)
    password: str = Field(min_length=12, max_length=128)
    role: Literal["Agent", "Viewer"]    

# --------------------------------------------------
# USER MANAGEMENT - ROLE UPDATE SCHEMA
# --------------------------------------------------

class UserRoleUpdate(BaseModel):
    role: Literal["Agent", "Viewer"]    


class UserStatusUpdate(BaseModel):
    is_active: bool    