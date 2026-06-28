"""Media engine — SVG chart generation, text overlays, and media agent."""

from __future__ import annotations

import asyncio
import logging
import math
from time import time
from typing import Optional

from broadcast.agents.base import BaseAgent
from broadcast.events.bus import EventBus
from broadcast.media.models import (
    AssetStatus,
    AssetType,
    ChartConfig,
    ChartType,
    MediaAsset,
    TextOverlayConfig,
)

logger = logging.getLogger(__name__)


# ── SVG Helpers ─────────────────────────────────────────────────────

def _svg_wrap(content: str, width: int, height: int) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {width} {height}" '
        f'width="{width}" height="{height}">'
        f'{content}</svg>'
    )


def _render_axis_lines(width: int, height: int, bottom_margin: int, left_margin: int) -> str:
    """Render X and Y axis lines."""
    x1 = left_margin
    y1 = height - bottom_margin
    return (
        f'<line x1="{x1}" y1="{y1}" x2="{width - 20}" y2="{y1}" '
        f'stroke="#666" stroke-width="1"/>'
        f'<line x1="{x1}" y1="20" x2="{x1}" y2="{y1}" '
        f'stroke="#666" stroke-width="1"/>'
    )


def _render_gridlines(
    chart_h: int, left_margin: int, chart_w: int, bottom_margin: int, num_lines: int = 4
) -> str:
    """Render horizontal gridlines."""
    lines = ""
    for i in range(num_lines + 1):
        y = chart_h - bottom_margin - (i * (chart_h - bottom_margin - 20) // num_lines)
        lines += (
            f'<line x1="{left_margin}" y1="{y}" '
            f'x2="{left_margin + chart_w}" y2="{y}" '
            f'stroke="#e0e0e0" stroke-width="0.5" stroke-dasharray="4,4"/>'
        )
    return lines


def _escape_xml(text: str) -> str:
    """Escape special XML characters."""
    return (text
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;"))


# ── Chart Renderer ──────────────────────────────────────────────────

class ChartRenderer:
    """Renders SVG charts from structured configuration."""

    LEFT_MARGIN = 60
    BOTTOM_MARGIN = 50
    TOP_MARGIN = 40

    def render_bar(self, config: ChartConfig) -> str:
        """Render an SVG bar chart."""
        lm = self.LEFT_MARGIN
        bm = self.BOTTOM_MARGIN
        chart_w = config.width - lm - 20
        chart_h = config.height - bm - 20
        bar_area_w = chart_w - lm

        # Collect all values
        all_values: list[float] = []
        for ds in config.datasets:
            all_values.extend(ds.get("values", []))
        if not all_values:
            all_values = [0]
        max_val = max(all_values) if all_values else 1
        if max_val == 0:
            max_val = 1

        bars_svg = ""
        labels_svg = ""
        legend_svg = ""
        total_bars = sum(len(ds.get("values", [])) for ds in config.datasets)
        if total_bars == 0:
            total_bars = 1
        bar_width = max(8, min(40, (bar_area_w - 10) // total_bars))
        gap = max(2, bar_width // 4)

        x_offset = lm + 10
        for ds_idx, ds in enumerate(config.datasets):
            values = ds.get("values", [])
            color = config.colors[ds_idx % len(config.colors)]
            for val in values:
                bar_h = (val / max_val) * (chart_h - bm - 20)
                y = chart_h - bm - bar_h
                bars_svg += (
                    f'<rect x="{x_offset}" y="{y}" '
                    f'width="{bar_width - gap}" height="{bar_h}" '
                    f'fill="{color}" rx="2"/>'
                )
                x_offset += bar_width

        # X axis labels
        x_offset = lm + 10
        for label in config.labels:
            labels_svg += (
                f'<text x="{x_offset + (bar_width - gap) / 2}" '
                f'y="{chart_h - bm + 16}" '
                f'text-anchor="middle" font-size="10" fill="#666">'
                f'{_escape_xml(label)}</text>'
            )
            x_offset += bar_width * (sum(len(ds.get("values", [])) for ds in config.datasets) // max(len(config.labels), 1))

        # Y axis labels
        for i in range(5):
            val = (max_val / 4) * i
            y = chart_h - bm - (i * (chart_h - bm - 20) // 4)
            labels_svg += (
                f'<text x="{lm - 8}" y="{y + 4}" '
                f'text-anchor="end" font-size="10" fill="#666">'
                f'{int(val)}</text>'
            )

        # Title
        title_svg = ""
        if config.title:
            title_svg = (
                f'<text x="{config.width / 2}" y="20" '
                f'text-anchor="middle" font-size="14" font-weight="bold" fill="#333">'
                f'{_escape_xml(config.title)}</text>'
            )

        # Legend
        legend_y = config.height - 8
        lx = lm
        for ds_idx, ds in enumerate(config.datasets):
            color = config.colors[ds_idx % len(config.colors)]
            label = ds.get("label", f"Series {ds_idx + 1}")
            legend_svg += (
                f'<rect x="{lx}" y="{legend_y - 8}" width="10" height="10" fill="{color}" rx="1"/>'
                f'<text x="{lx + 14}" y="{legend_y}" font-size="10" fill="#666">'
                f'{_escape_xml(label)}</text>'
            )
            lx += 100

        content = (
            title_svg
            + _render_gridlines(chart_h, lm, chart_w - lm, bm)
            + _render_axis_lines(config.width, chart_h, bm, lm)
            + bars_svg
            + labels_svg
            + legend_svg
        )
        return _svg_wrap(content, config.width, config.height)

    def render_line(self, config: ChartConfig) -> str:
        """Render an SVG line chart."""
        lm = self.LEFT_MARGIN
        bm = self.BOTTOM_MARGIN
        chart_w = config.width - lm - 20
        chart_h = config.height - bm - 20

        all_values: list[float] = []
        for ds in config.datasets:
            all_values.extend(ds.get("values", []))
        if not all_values:
            all_values = [0]
        max_val = max(all_values) if all_values else 1
        if max_val == 0:
            max_val = 1

        num_points = len(config.labels)
        if num_points <= 1:
            num_points = 2
        step_x = (chart_w - lm - 20) / (num_points - 1)

        lines_svg = ""
        points_svg = ""
        labels_svg = ""

        for ds_idx, ds in enumerate(config.datasets):
            values = ds.get("values", [])
            color = config.colors[ds_idx % len(config.colors)]
            if not values:
                continue

            # Build polyline points
            pts: list[str] = []
            for i, val in enumerate(values):
                x = lm + 10 + i * step_x
                y = chart_h - bm - ((val / max_val) * (chart_h - bm - 20))
                pts.append(f"{x:.1f},{y:.1f}")
                points_svg += (
                    f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" '
                    f'fill="{color}" stroke="#fff" stroke-width="2"/>'
                )

            if pts:
                lines_svg += (
                    f'<polyline points="{" ".join(pts)}" '
                    f'fill="none" stroke="{color}" stroke-width="2.5" stroke-linejoin="round"/>'
                )

        # X axis labels
        for i, label in enumerate(config.labels):
            x = lm + 10 + i * step_x
            labels_svg += (
                f'<text x="{x}" y="{chart_h - bm + 16}" '
                f'text-anchor="middle" font-size="10" fill="#666">'
                f'{_escape_xml(label)}</text>'
            )

        # Y axis labels
        for i in range(5):
            val = (max_val / 4) * i
            y = chart_h - bm - (i * (chart_h - bm - 20) // 4)
            labels_svg += (
                f'<text x="{lm - 8}" y="{y + 4}" '
                f'text-anchor="end" font-size="10" fill="#666">'
                f'{int(val)}</text>'
            )

        # Title
        title_svg = ""
        if config.title:
            title_svg = (
                f'<text x="{config.width / 2}" y="20" '
                f'text-anchor="middle" font-size="14" font-weight="bold" fill="#333">'
                f'{_escape_xml(config.title)}</text>'
            )

        # Legend
        legend_svg = ""
        legend_y = config.height - 8
        lx = lm
        for ds_idx, ds in enumerate(config.datasets):
            color = config.colors[ds_idx % len(config.colors)]
            label = ds.get("label", f"Series {ds_idx + 1}")
            legend_svg += (
                f'<rect x="{lx}" y="{legend_y - 8}" width="10" height="10" fill="{color}" rx="1"/>'
                f'<text x="{lx + 14}" y="{legend_y}" font-size="10" fill="#666">'
                f'{_escape_xml(label)}</text>'
            )
            lx += 100

        content = (
            title_svg
            + _render_gridlines(chart_h, lm, chart_w - lm, bm)
            + _render_axis_lines(config.width, chart_h, bm, lm)
            + lines_svg
            + points_svg
            + labels_svg
            + legend_svg
        )
        return _svg_wrap(content, config.width, config.height)

    def render_pie(self, config: ChartConfig) -> str:
        """Render an SVG pie/donut chart with segment labels."""
        cx = config.width // 2
        cy = config.height // 2
        radius = min(config.width, config.height) // 2 - 40

        # Collect all values across datasets (flatten)
        all_values: list[float] = []
        all_labels: list[str] = []
        for ds in config.datasets:
            values = ds.get("values", [])
            label = ds.get("label", "")
            for v in values:
                all_values.append(v)
                all_labels.append(label)

        if not all_values:
            all_values = [100]

        total = sum(all_values)
        if total == 0:
            total = 1

        # Render pie segments
        paths_svg = ""
        labels_svg = ""
        current_angle = -90  # Start from top
        for i, val in enumerate(all_values):
            if val <= 0:
                continue
            fraction = val / total
            angle = fraction * 360
            end_angle = current_angle + angle
            color = config.colors[i % len(config.colors)]

            # SVG arc path
            start_rad = math.radians(current_angle)
            end_rad = math.radians(end_angle)
            x1 = cx + radius * math.cos(start_rad)
            y1 = cy + radius * math.sin(start_rad)
            x2 = cx + radius * math.cos(end_rad)
            y2 = cy + radius * math.sin(end_rad)
            large_arc = 1 if angle > 180 else 0

            paths_svg += (
                f'<path d="M {cx} {cy} L {x1:.1f} {y1:.1f} '
                f'A {radius} {radius} 0 {large_arc} 1 {x2:.1f} {y2:.1f} Z" '
                f'fill="{color}" stroke="#fff" stroke-width="2"/>'
            )

            # Label at midpoint of arc
            mid_rad = math.radians(current_angle + angle / 2)
            label_r = radius * 0.65
            lx = cx + label_r * math.cos(mid_rad)
            ly = cy + label_r * math.sin(mid_rad)
            pct = (val / total) * 100
            labels_svg += (
                f'<text x="{lx:.1f}" y="{ly:.1f}" '
                f'text-anchor="middle" dominant-baseline="central" '
                f'font-size="11" font-weight="bold" fill="#fff">'
                f'{pct:.1f}%</text>'
            )

            current_angle = end_angle

        # Title
        title_svg = ""
        if config.title:
            title_svg = (
                f'<text x="{config.width / 2}" y="20" '
                f'text-anchor="middle" font-size="14" font-weight="bold" fill="#333">'
                f'{_escape_xml(config.title)}</text>'
            )

        # Legend
        legend_svg = ""
        legend_y = config.height - 16
        if config.labels:
            lx = max(20, (config.width - len(config.labels) * 100) // 2)
            for i, lbl in enumerate(config.labels):
                color = config.colors[i % len(config.colors)]
                legend_svg += (
                    f'<rect x="{lx}" y="{legend_y - 8}" width="10" height="10" fill="{color}" rx="1"/>'
                    f'<text x="{lx + 14}" y="{legend_y}" font-size="10" fill="#666">'
                    f'{_escape_xml(lbl)}</text>'
                )
                lx += 100

        content = title_svg + paths_svg + labels_svg + legend_svg
        return _svg_wrap(content, config.width, config.height)

    def render_text_overlay(self, config: TextOverlayConfig) -> str:
        """Render an SVG text overlay with optional background."""
        rect_svg = ""
        if config.background_color != "transparent":
            rect_svg = (
                f'<rect x="0" y="0" width="{config.width}" '
                f'height="{config.height}" fill="{config.background_color}" rx="8"/>'
            )

        text_svg = (
            f'<text x="{config.width / 2}" y="{config.height / 2}" '
            f'text-anchor="middle" dominant-baseline="central" '
            f'font-size="{config.font_size}" fill="{config.color}" '
            f'font-family="Arial, sans-serif">'
            f'{_escape_xml(config.text)}</text>'
        )

        content = rect_svg + text_svg
        return _svg_wrap(content, config.width, config.height)


# ── Media Engine ────────────────────────────────────────────────────

class MediaEngine:
    """Manages media asset lifecycle — generate, store, retrieve."""

    MAX_ASSETS = 100

    def __init__(self) -> None:
        self._assets: dict[str, MediaAsset] = {}
        self._renderer = ChartRenderer()
        self._id_counter: int = 0

    def generate_chart(self, config: ChartConfig) -> MediaAsset:
        """Generate a chart SVG and store it as a media asset."""
        if config.chart_type == ChartType.BAR:
            svg = self._renderer.render_bar(config)
        elif config.chart_type == ChartType.LINE:
            svg = self._renderer.render_line(config)
        elif config.chart_type == ChartType.PIE:
            svg = self._renderer.render_pie(config)
        else:
            svg = self._renderer.render_bar(config)

        asset = MediaAsset(
            id=self._next_id(),
            type=AssetType.CHART,
            svg_content=svg,
            metadata={
                "chart_type": config.chart_type.value,
                "title": config.title,
                "labels": config.labels,
                "dataset_count": len(config.datasets),
            },
            created_at=time(),
        )
        self._assets[asset.id] = asset
        self._enforce_cap()
        return asset

    def generate_text_overlay(self, config: TextOverlayConfig) -> MediaAsset:
        """Generate a text overlay SVG and store it."""
        svg = self._renderer.render_text_overlay(config)
        asset = MediaAsset(
            id=self._next_id(),
            type=AssetType.TEXT_OVERLAY,
            svg_content=svg,
            metadata={
                "text": config.text,
                "font_size": config.font_size,
                "color": config.color,
            },
            created_at=time(),
        )
        self._assets[asset.id] = asset
        self._enforce_cap()
        return asset

    def get(self, asset_id: str) -> Optional[MediaAsset]:
        """Get an asset by ID."""
        return self._assets.get(asset_id)

    def list(self, segment_id: str = "", type: Optional[AssetType] = None) -> list[MediaAsset]:
        """List assets, optionally filtered by segment_id and/or type."""
        results = list(self._assets.values())
        if segment_id:
            results = [a for a in results if a.segment_id == segment_id]
        if type:
            results = [a for a in results if a.type == type]
        return sorted(results, key=lambda a: a.created_at, reverse=True)

    def delete(self, asset_id: str) -> bool:
        """Delete an asset by ID. Returns True if deleted."""
        if asset_id in self._assets:
            del self._assets[asset_id]
            return True
        return False

    def assign_to_segment(self, asset_id: str, segment_id: str) -> bool:
        """Assign an asset to a segment. Returns True if successful."""
        asset = self._assets.get(asset_id)
        if asset is None:
            return False
        asset.segment_id = segment_id
        asset.status = AssetStatus.ASSIGNED
        return True

    def _next_id(self) -> str:
        """Generate a unique asset ID using timestamp and counter."""
        self._id_counter += 1
        return f"asset_{int(time() * 1000)}_{self._id_counter}"

    def _enforce_cap(self) -> None:
        """Remove oldest assets if over the cap."""
        while len(self._assets) > self.MAX_ASSETS:
            oldest = min(self._assets.items(), key=lambda kv: kv[1].created_at)
            del self._assets[oldest[0]]


# ── Media Agent ─────────────────────────────────────────────────────

class MediaAgent(BaseAgent):
    """Agent that manages media asset lifecycle and integrates with EventBus."""

    def __init__(self, event_bus: Optional[EventBus] = None) -> None:
        super().__init__()
        self._engine = MediaEngine()
        self._event_bus = event_bus or EventBus()

    @property
    def agent_name(self) -> str:
        return "Media"

    @property
    def agent_type(self) -> str:
        return "media"

    @property
    def engine(self) -> MediaEngine:
        return self._engine

    def generate_chart(self, config: ChartConfig) -> MediaAsset:
        """Generate a chart and publish EventBus event."""
        asset = self._engine.generate_chart(config)
        self._publish_created(asset)
        return asset

    def generate_text_overlay(self, config: TextOverlayConfig) -> MediaAsset:
        """Generate a text overlay and publish EventBus event."""
        asset = self._engine.generate_text_overlay(config)
        self._publish_created(asset)
        return asset

    def get_asset(self, asset_id: str) -> Optional[MediaAsset]:
        """Get an asset by ID."""
        return self._engine.get(asset_id)

    def list_assets(self, segment_id: str = "", type: Optional[AssetType] = None) -> list[MediaAsset]:
        """List assets with optional filters."""
        return self._engine.list(segment_id, type)

    def delete_asset(self, asset_id: str) -> bool:
        """Delete an asset."""
        return self._engine.delete(asset_id)

    def assign_to_segment(self, asset_id: str, segment_id: str) -> bool:
        """Assign an asset to a segment."""
        return self._engine.assign_to_segment(asset_id, segment_id)

    def _publish_created(self, asset: MediaAsset) -> None:
        """Publish a media.asset.created event."""
        payload = {
            "type": "media.asset.created",
            "asset_id": asset.id,
            "asset_type": asset.type.value,
            "timestamp": time(),
        }
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            asyncio.run(self._event_bus.publish("media", payload))
        else:
            loop.create_task(self._event_bus.publish("media", payload))
