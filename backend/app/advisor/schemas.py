from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

MAX_ADVISOR_MESSAGE_LENGTH = 2000


class AdvisorChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=MAX_ADVISOR_MESSAGE_LENGTH)

    @field_validator("message")
    @classmethod
    def normalize_message(cls, value: str) -> str:
        cleaned = " ".join(value.strip().split())
        if not cleaned:
            raise ValueError("message must not be empty")
        return cleaned


class AdvisorWarning(BaseModel):
    code: str
    message: str


class AdvisorContextUsed(BaseModel):
    financial: bool = False
    market: bool = False
    memory: bool = False


class AdvisorChatResponse(BaseModel):
    response: str
    warnings: list[AdvisorWarning] = Field(default_factory=list)
    context_used: AdvisorContextUsed
