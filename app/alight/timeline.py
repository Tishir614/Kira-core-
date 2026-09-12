from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class TimelineKeyframe(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    layer: str = Field(max_length=128)
    property: Literal["position", "scale", "rotation", "opacity", "anchor", "blur", "glow", "shake", "camera", "mask", "layer_order"]
    time: float = Field(ge=0)
    value: float | list[float] | str
    easing: Literal["linear", "ease_in", "ease_out", "ease_in_out", "ease_out_back"] = "linear"


class Timeline(BaseModel):
    model_config = ConfigDict(extra="forbid")
    duration: float = Field(gt=0)
    keyframes: list[TimelineKeyframe]
