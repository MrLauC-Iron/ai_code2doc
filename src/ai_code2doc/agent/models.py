"""Data models for the conversational agent."""

from __future__ import annotations

import enum
import json
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class MessageRole(str, enum.Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class ToolParameter(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    type: str  # string, integer, boolean, array
    description: str
    required: bool = True
    enum: list[str] | None = None


class ToolDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    description: str
    parameters: list[ToolParameter] = Field(default_factory=list)

    def to_openai_schema(self) -> dict[str, Any]:
        """Convert to OpenAI function-calling tool schema."""
        properties: dict[str, Any] = {}
        required: list[str] = []
        for p in self.parameters:
            prop: dict[str, Any] = {"type": p.type, "description": p.description}
            if p.enum:
                prop["enum"] = p.enum
            properties[p.name] = prop
            if p.required:
                required.append(p.name)
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        }


class ToolCall(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class ToolResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool_call_id: str
    content: str
    is_error: bool = False


class ConversationMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: MessageRole
    content: str
    tool_calls: list[ToolCall] | None = None
    tool_results: list[ToolResult] | None = None
    timestamp: datetime = Field(default_factory=datetime.now)

    def to_openai_dict(self) -> dict[str, Any]:
        """Convert to OpenAI chat completion message format."""
        d: dict[str, Any] = {"role": self.role.value, "content": self.content}
        if self.tool_calls:
            d["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.name,
                        "arguments": json.dumps(tc.arguments),
                    },
                }
                for tc in self.tool_calls
            ]
        if self.tool_results:
            tr = self.tool_results[0]
            d["tool_call_id"] = tr.tool_call_id
            d["content"] = tr.content
        return d

    def to_openai_messages(self) -> list[dict[str, Any]]:
        """Convert to OpenAI messages, expanding tool results into individual messages."""
        if self.tool_results:
            return [
                {"role": "tool", "tool_call_id": tr.tool_call_id, "content": tr.content}
                for tr in self.tool_results
            ]
        return [self.to_openai_dict()]