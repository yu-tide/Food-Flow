from typing import Any, Literal

from pydantic import BaseModel, Field


class AssistantSuggestedAction(BaseModel):
    id: str
    type: Literal["open_record_detail", "open_settings", "save_current_record", "export_weekly_report"]
    title: str
    description: str | None = None
    confirm_label: str | None = None
    cancel_label: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    requires_confirmation: bool = True
    risk_level: Literal["low", "medium"] = "low"


class AssistantActionExecuteRequest(BaseModel):
    action_id: str
    type: str
    payload: dict[str, Any] = Field(default_factory=dict)


class AssistantActionExecuteResponse(BaseModel):
    ok: bool
    type: str
    message: str
    result: dict[str, Any] | None = None
    post_action_observation: dict[str, Any] | None = None
    assistant_followup_message: str | None = None
