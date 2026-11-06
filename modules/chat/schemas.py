from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=20000)
    ] = Field(description="发送给大模型的文本内容")
