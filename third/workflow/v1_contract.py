"""Java-facing third workflow v1 HTTP contract shared by third and third_two."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator


def _to_camel(value: str) -> str:
    head, *tail = value.split("_")
    return head + "".join(part[:1].upper() + part[1:] for part in tail)


class CamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=_to_camel,
        validate_by_alias=True,
        validate_by_name=False,
        extra="forbid",
    )

    @classmethod
    def from_internal(cls, **values: Any):
        return cls.model_validate(values, by_alias=True, by_name=True)


class ExtensibleCamelModel(CamelModel):
    model_config = ConfigDict(
        alias_generator=_to_camel,
        validate_by_alias=True,
        validate_by_name=False,
        extra="allow",
    )


class WorkflowStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    WAITING_USER = "waiting_user"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


class InteractionKind(str, Enum):
    CLARIFY = "clarify"
    CONFIRM = "confirm"
    CHOOSE_CANDIDATE = "choose_candidate"


class InteractionResponse(str, Enum):
    APPROVE = "approve"
    ANSWER = "answer"
    MODIFY = "modify"
    CANCEL = "cancel"


class ContentPart(CamelModel):
    text: str = ""


class FeishuPublicMetadata(CamelModel):
    config_id: str | None = None
    display_name: str | None = None
    table_id: str | None = None
    view_id: str | None = None


class WorkflowMetadata(ExtensibleCamelModel):
    business_session_id: str | None = None
    business_record_id: str | None = None
    operation: str | None = None
    mode: str | None = None
    idempotency_key: str | None = None
    feishu: FeishuPublicMetadata | None = None


class FeishuAccountMetadata(CamelModel):
    enabled: bool = True
    app_id: str | None = None
    app_secret: str | None = None
    tenant_access_token: str | None = None
    user_id_type: str | None = None


class FeishuTableMetadata(CamelModel):
    enabled: bool = True
    display_name: str | None = None
    app_token: str | None = None
    table_id: str | None = None
    table_name: str | None = None
    view_id: str | None = None
    field_name_map: dict[str, JsonValue] = Field(default_factory=dict)


class FeishuPrivateMetadata(CamelModel):
    config_id: str | None = None
    account: FeishuAccountMetadata | None = None
    table: FeishuTableMetadata | None = None


class WorkflowPrivateMetadata(CamelModel):
    feishu: FeishuPrivateMetadata | None = None

    def to_internal_dict(self) -> dict[str, Any]:
        return self.model_dump(by_alias=False, exclude_none=True)


class InvokeWorkflowV1Request(CamelModel):
    content: list[ContentPart] = Field(default_factory=list)
    metadata: WorkflowMetadata = Field(default_factory=WorkflowMetadata)
    private_metadata: WorkflowPrivateMetadata = Field(default_factory=WorkflowPrivateMetadata)


class ResumeWorkflowV1Request(CamelModel):
    confirmation_id: str
    approved: bool
    response: InteractionResponse
    content: list[ContentPart] = Field(default_factory=list)


class FeishuTableCheckV1Request(CamelModel):
    private_metadata: WorkflowPrivateMetadata = Field(default_factory=WorkflowPrivateMetadata)


class WorkflowResponseV1(CamelModel):
    session_id: str
    status: WorkflowStatus
    content: list[ContentPart] = Field(default_factory=list)
    error_text: str | None = None

    @model_validator(mode="after")
    def validate_identity(self) -> "WorkflowResponseV1":
        if not self.session_id.strip():
            raise ValueError("sessionId 不能为空。")
        return self


class SnapshotSessionV1(CamelModel):
    session_id: str
    status: WorkflowStatus
    current_step_id: str | None = None
    original_input: str
    final_answer: str | None = None
    error_text: str | None = None
    metadata: WorkflowMetadata = Field(default_factory=WorkflowMetadata)
    created_at: datetime | str | None = None
    updated_at: datetime | str | None = None


class WorkflowDecisionV1(CamelModel):
    plan_id: str | None = None
    plan_version: str | int | None = None
    template_key: str | None = None
    intent: str | None = None
    risk_level: str | None = None
    requires_confirmation: bool = False
    final: dict[str, JsonValue] = Field(default_factory=dict)


class WorkflowConfirmationV1(CamelModel):
    confirmation_id: str
    status: str
    request_text: str
    preview: JsonValue = Field(default_factory=dict)
    step_id: str | None = None
    user_response: str | None = None
    interaction_kind: InteractionKind
    options: list[JsonValue] = Field(default_factory=list)
    created_at: datetime | str | None = None
    decided_at: datetime | str | None = None
    expires_at: datetime | str | None = None


class WorkflowOutputsV1(CamelModel):
    draft: JsonValue | None = None
    write_payload: JsonValue | None = None
    write_result: JsonValue | None = None
    table_schema: JsonValue | None = None
    records: JsonValue | None = None
    final_answer: JsonValue | None = None


class WorkflowArtifactV1(CamelModel):
    artifact_id: str
    session_id: str
    source_step_id: str | None = None
    artifact_key: str
    content_text: str = ""
    data: JsonValue = Field(default_factory=dict)
    schema_data: JsonValue = Field(default_factory=dict, alias="schema")
    created_at: datetime | str | None = None
    expires_at: datetime | str | None = None


class WorkflowSnapshotV1(CamelModel):
    session: SnapshotSessionV1
    decision: WorkflowDecisionV1 | None = None
    confirmation: WorkflowConfirmationV1 | None = None
    outputs: WorkflowOutputsV1
    artifacts_by_key: dict[str, WorkflowArtifactV1] = Field(default_factory=dict)
    artifacts: list[WorkflowArtifactV1] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_waiting_confirmation(self) -> "WorkflowSnapshotV1":
        if self.session.status != WorkflowStatus.WAITING_USER:
            return self
        confirmation = self.confirmation
        if not confirmation:
            raise ValueError("waiting_user snapshot 必须包含 confirmation。")
        if not confirmation.confirmation_id.strip():
            raise ValueError("waiting_user confirmationId 不能为空。")
        if not confirmation.request_text.strip():
            raise ValueError("waiting_user requestText 不能为空。")
        return self


class WorkflowTimelineV1(CamelModel):
    session: SnapshotSessionV1
    decision: WorkflowDecisionV1 | None = None
    steps: list[JsonValue] = Field(default_factory=list)
    confirmations: list[WorkflowConfirmationV1] = Field(default_factory=list)
    artifacts: list[WorkflowArtifactV1] = Field(default_factory=list)


class WorkflowArtifactsV1(CamelModel):
    session_id: str
    artifacts: list[WorkflowArtifactV1] = Field(default_factory=list)


class FeishuTableCheckV1Response(CamelModel):
    status: str
    message: str
    table_name: str | None = None
    field_count: int = 0
    field_names: list[str] = Field(default_factory=list)
