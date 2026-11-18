from typing import Literal
from pydantic import BaseModel, Field

DepartmentId = Literal["VP", "KT", "VHXH", "NNMT"]
AssistantMode = Literal["soan_thao", "nghiep_vu", "tham_dinh"]
DocTier = Literal["trung_uong", "dia_phuong", "kho_rieng"]
SessionProcessAction = Literal["tom_tat", "trich_xuat", "doi_chieu", "tong_hop"]
TaskStatus = Literal["cho_xu_ly", "dang_thuc_hien", "sap_den_han", "hoan_thanh"]
PriorityLevel = Literal["thap", "trung_binh", "cao", "khan"]


class ChatRequest(BaseModel):
    session_id: str = Field(..., min_length=1, max_length=128)
    department_id: DepartmentId = "VP"
    mode: AssistantMode = "nghiep_vu"
    message: str = Field(..., min_length=1, max_length=10000)


class ExtendedAnalyzeRequest(BaseModel):
    department_id: DepartmentId = "VP"
    topic: str = Field(..., min_length=3, max_length=1000)
    context: str = Field(default="", max_length=4000)


AuthorityMode = Literal["auto", "ubnd", "chu_tich"]


class DraftRequest(BaseModel):
    department_id: DepartmentId = "VP"
    doc_type: str = Field(default="Công văn", min_length=2, max_length=64)
    title: str = Field(..., min_length=3, max_length=500)
    key_points: str = Field(default="", max_length=6000)
    recipient: str = Field(default="Các bộ phận chuyên môn trực thuộc UBND", max_length=300)
    authority_mode: AuthorityMode = "auto"


class AuditRequest(BaseModel):
    department_id: DepartmentId = "VP"
    doc_type: str = Field(default="Công văn", min_length=2, max_length=64)
    draft_text: str = Field(..., min_length=5, max_length=50000)


class CreateDocRequest(BaseModel):
    doc_number: str = Field(..., min_length=2, max_length=120)
    title: str = Field(..., min_length=3, max_length=500)
    doc_type: str = Field(default="Văn bản hướng dẫn", max_length=100)
    tier: DocTier = "kho_rieng"
    department_id: Literal["VP", "KT", "VHXH", "NNMT", "ALL"] = "VP"
    issuer: str = Field(default="UBND Xã/Phường", max_length=200)
    issued_date: str = Field(default="2026-11-01", max_length=32)
    status: str = Field(default="con_hieu_luc", max_length=32)
    summary: str = Field(default="", max_length=2000)
    content: str = Field(..., min_length=5, max_length=50000)


class DocUpdateRequestCreate(BaseModel):
    doc_number: str = Field(..., min_length=2, max_length=120)
    title: str = Field(..., min_length=3, max_length=500)
    tier: DocTier = "trung_uong"
    department_id: DepartmentId = "VP"
    reason: str = Field(..., min_length=3, max_length=2000)
    requested_by: str = Field(default="", max_length=200)


class DocUpdateReviewRequest(BaseModel):
    status: Literal["da_duyet", "tu_choi"]
    issuer: str = Field(default="Cơ quan nhà nước có thẩm quyền", max_length=200)
    issued_date: str = Field(default="2026-11-18", max_length=32)
    doc_type: str = Field(default="Văn bản pháp quy", max_length=100)
    summary: str = Field(default="", max_length=2000)
    content: str = Field(default="", max_length=50000)


class ProcessSessionRequest(BaseModel):
    action: SessionProcessAction = "tom_tat"
    department_id: DepartmentId = "VP"


class TaskCreateRequest(BaseModel):
    title: str = Field(..., min_length=3, max_length=400)
    description: str = Field(default="", max_length=3000)
    department_id: DepartmentId = "VP"
    assignee: str = Field(..., min_length=2, max_length=200)
    due_date: str = Field(..., min_length=8, max_length=32)
    priority: PriorityLevel = "trung_binh"
    ref_doc_number: str = Field(default="", max_length=120)


class TaskPatchRequest(BaseModel):
    progress: int | None = Field(default=None, ge=0, le=100)
    status: TaskStatus | None = None
    remind: bool = False


class UserCreateRequest(BaseModel):
    email: str = Field(..., min_length=5, max_length=200)
    full_name: str = Field(..., min_length=2, max_length=200)
    position: str = Field(default="Công chức chuyên môn", max_length=200)
    role: Literal["owner", "officer"] = "officer"
    department_id: DepartmentId = "VP"
    private_repo_access: bool = True


class InstructionUpdateRequest(BaseModel):
    instruction: str = Field(..., min_length=5, max_length=8000)


class ConnectorUpdateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=200)
    provider: str = Field(default="openai-compatible", max_length=64)
    base_url: str = Field(..., min_length=8, max_length=500)
    model_name: str = Field(..., min_length=2, max_length=120)
    api_key: str | None = Field(default=None, max_length=500)
    active: bool = False


class CloneTenantRequest(BaseModel):
    commune_name: str = Field(..., min_length=3, max_length=200)
    admin_email: str = Field(..., min_length=5, max_length=200)

