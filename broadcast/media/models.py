"""Data models for the Media Agent — charts, text overlays, and assets."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class ChartType(str, Enum):
    BAR = "bar"
    LINE = "line"
    PIE = "pie"


class AssetType(str, Enum):
    CHART = "chart"
    TEXT_OVERLAY = "text_overlay"


class AssetStatus(str, Enum):
    GENERATED = "generated"
    ASSIGNED = "assigned"
    DELETED = "deleted"


class ChartConfig(BaseModel):
    chart_type: ChartType
    title: str = ""
    labels: list[str] = Field(min_length=1)
    datasets: list[dict]  # [{"label": "Series 1", "values": [10, 20, 30]}]
    width: int = 600
    height: int = 400
    colors: list[str] = Field(
        default_factory=lambda: ["#3B82F6", "#10B981", "#F59E0B", "#EF4444", "#8B5CF6"]
    )


class TextOverlayConfig(BaseModel):
    text: str
    font_size: int = 48
    color: str = "#FFFFFF"
    background_color: str = "transparent"
    width: int = 800
    height: int = 200


class MediaAsset(BaseModel):
    id: str
    type: AssetType
    segment_id: str = ""
    svg_content: str
    metadata: dict = {}
    status: AssetStatus = AssetStatus.GENERATED
    created_at: float = 0.0
