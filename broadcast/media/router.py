"""Media REST API endpoints — chart generation, text overlays, asset management."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from broadcast.auth import verify_api_key
from broadcast.media.engine import MediaAgent
from broadcast.media.models import AssetType, ChartConfig, ChartType, TextOverlayConfig

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/media", tags=["media"], dependencies=[Depends(verify_api_key)])

# Module-level singleton
_agent = MediaAgent()


@router.post("/chart")
def create_chart(body: dict) -> dict:
    """Generate a chart (bar/line/pie)."""
    chart_type_str = body.get("chart_type", "bar")
    if chart_type_str not in (t.value for t in ChartType):
        raise HTTPException(status_code=422, detail=f"Invalid chart_type: {chart_type_str}")
    labels = body.get("labels", [])
    if not labels:
        raise HTTPException(status_code=422, detail="Labels are required")
    datasets = body.get("datasets", [])
    if not datasets:
        raise HTTPException(status_code=422, detail="At least one dataset is required")
    config = ChartConfig(
        chart_type=ChartType(chart_type_str),
        title=body.get("title", ""),
        labels=labels,
        datasets=datasets,
        width=body.get("width", 600),
        height=body.get("height", 400),
        colors=body.get("colors", ["#3B82F6", "#10B981", "#F59E0B", "#EF4444", "#8B5CF6"]),
    )
    asset = _agent.generate_chart(config)
    return asset.model_dump()


@router.post("/text")
def create_text_overlay(body: dict) -> dict:
    """Generate a text overlay."""
    text = body.get("text", "").strip()
    if not text:
        raise HTTPException(status_code=422, detail="Text is required")
    config = TextOverlayConfig(
        text=text,
        font_size=body.get("font_size", 48),
        color=body.get("color", "#FFFFFF"),
        background_color=body.get("background_color", "transparent"),
        width=body.get("width", 800),
        height=body.get("height", 200),
    )
    asset = _agent.generate_text_overlay(config)
    return asset.model_dump()


@router.get("/assets")
def list_assets(
    segment_id: Optional[str] = None,
    type: Optional[str] = None,
) -> list[dict]:
    """List assets with optional filters."""
    asset_type = None
    if type:
        if type not in (t.value for t in AssetType):
            raise HTTPException(status_code=422, detail=f"Invalid type: {type}")
        asset_type = AssetType(type)
    return [a.model_dump() for a in _agent.list_assets(segment_id or "", asset_type)]


@router.get("/assets/{asset_id}")
def get_asset(asset_id: str) -> dict:
    """Get a specific asset with SVG content."""
    asset = _agent.get_asset(asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    return asset.model_dump()


@router.delete("/assets/{asset_id}")
def delete_asset(asset_id: str) -> dict:
    """Delete an asset."""
    if not _agent.delete_asset(asset_id):
        raise HTTPException(status_code=404, detail="Asset not found")
    return {"deleted": True, "asset_id": asset_id}


@router.post("/assets/{asset_id}/assign")
def assign_asset(asset_id: str, body: dict) -> dict:
    """Assign an asset to a segment."""
    segment_id = body.get("segment_id", "").strip()
    if not segment_id:
        raise HTTPException(status_code=422, detail="segment_id is required")
    if not _agent.assign_to_segment(asset_id, segment_id):
        raise HTTPException(status_code=404, detail="Asset not found")
    return {"assigned": True, "asset_id": asset_id, "segment_id": segment_id}
