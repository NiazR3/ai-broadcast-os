"""Tests for M5 — Media Agent models, chart renderer, engine, and agent."""

from __future__ import annotations

from time import time

import pytest
from pydantic import ValidationError

from broadcast.media.models import (
    AssetStatus,
    AssetType,
    ChartConfig,
    ChartType,
    MediaAsset,
    TextOverlayConfig,
)
from broadcast.media.engine import (
    ChartRenderer,
    MediaAgent,
    MediaEngine,
)


# ── Model tests ─────────────────────────────────────────────────────

class TestChartConfigModel:
    def test_minimal_config(self):
        config = ChartConfig(chart_type=ChartType.BAR, labels=["A", "B"], datasets=[])
        assert config.width == 600
        assert config.height == 400

    def test_config_with_data(self):
        config = ChartConfig(
            chart_type=ChartType.LINE,
            title="Test",
            labels=["Q1", "Q2"],
            datasets=[{"label": "Series 1", "values": [10, 20]}],
        )
        assert len(config.datasets) == 1
        assert config.colors[0] == "#3B82F6"

    def test_config_rejects_empty_labels(self):
        with pytest.raises(ValidationError):
            ChartConfig(chart_type=ChartType.BAR, labels=[], datasets=[])


class TestTextOverlayConfigModel:
    def test_minimal_config(self):
        config = TextOverlayConfig(text="Hello")
        assert config.font_size == 48
        assert config.width == 800

    def test_custom_config(self):
        config = TextOverlayConfig(text="Alert", font_size=72, color="#FF0000", background_color="#000000")
        assert config.color == "#FF0000"


class TestMediaAssetModel:
    def test_minimal_asset(self):
        asset = MediaAsset(
            id="a1", type=AssetType.CHART,
            svg_content="<svg></svg>",
        )
        assert asset.status == AssetStatus.GENERATED
        assert asset.segment_id == ""

    def test_asset_all_fields(self):
        asset = MediaAsset(
            id="a1", type=AssetType.TEXT_OVERLAY,
            segment_id="seg_1", svg_content="<svg></svg>",
            metadata={"key": "val"}, status=AssetStatus.ASSIGNED,
            created_at=100.0,
        )
        assert asset.status == AssetStatus.ASSIGNED
        assert asset.metadata["key"] == "val"


# ── ChartRenderer tests ─────────────────────────────────────────────

class TestChartRenderer:
    def test_render_bar_returns_svg(self):
        renderer = ChartRenderer()
        config = ChartConfig(
            chart_type=ChartType.BAR,
            title="Sales",
            labels=["Q1", "Q2"],
            datasets=[{"label": "Revenue", "values": [100, 200]}],
        )
        svg = renderer.render_bar(config)
        assert svg.startswith("<svg")
        assert "viewBox" in svg
        assert "rect" in svg
        assert "Sales" in svg

    def test_bar_chart_has_axis_lines(self):
        renderer = ChartRenderer()
        config = ChartConfig(
            chart_type=ChartType.BAR,
            labels=["A", "B"], datasets=[{"label": "S1", "values": [10, 20]}],
        )
        svg = renderer.render_bar(config)
        assert "stroke=\"#666\"" in svg

    def test_bar_chart_has_legend(self):
        renderer = ChartRenderer()
        config = ChartConfig(
            chart_type=ChartType.BAR,
            title="Test",
            labels=["A", "B"],
            datasets=[{"label": "Series 1", "values": [10, 20]}],
        )
        svg = renderer.render_bar(config)
        assert "Series 1" in svg

    def test_render_line_returns_svg(self):
        renderer = ChartRenderer()
        config = ChartConfig(
            chart_type=ChartType.LINE,
            title="Trend",
            labels=["Jan", "Feb", "Mar"],
            datasets=[{"label": "Growth", "values": [10, 25, 15]}],
        )
        svg = renderer.render_line(config)
        assert svg.startswith("<svg")
        assert "polyline" in svg
        assert "Trend" in svg

    def test_line_chart_has_data_points(self):
        renderer = ChartRenderer()
        config = ChartConfig(
            chart_type=ChartType.LINE,
            labels=["A", "B", "C"],
            datasets=[{"label": "S1", "values": [5, 10, 8]}],
        )
        svg = renderer.render_line(config)
        assert "circle" in svg

    def test_render_pie_returns_svg(self):
        renderer = ChartRenderer()
        config = ChartConfig(
            chart_type=ChartType.PIE,
            title="Distribution",
            labels=["A", "B", "C"],
            datasets=[{"label": "S1", "values": [30, 50, 20]}],
        )
        svg = renderer.render_pie(config)
        assert svg.startswith("<svg")
        assert "path" in svg

    def test_pie_chart_has_percentages(self):
        renderer = ChartRenderer()
        config = ChartConfig(
            chart_type=ChartType.PIE,
            labels=["X", "Y"],
            datasets=[{"label": "S1", "values": [25, 75]}],
        )
        svg = renderer.render_pie(config)
        assert "25.0%" in svg or "75.0%" in svg

    def test_render_text_overlay_returns_svg(self):
        renderer = ChartRenderer()
        config = TextOverlayConfig(text="Hello World", font_size=48)
        svg = renderer.render_text_overlay(config)
        assert svg.startswith("<svg")
        assert "Hello World" in svg

    def test_text_overlay_with_background(self):
        renderer = ChartRenderer()
        config = TextOverlayConfig(
            text="Alert", background_color="#000000"
        )
        svg = renderer.render_text_overlay(config)
        assert "rect" in svg
        assert "#000000" in svg

    def test_render_bar_empty_labels_fallback(self):
        """Should handle gracefully — no crash with empty labels list."""
        renderer = ChartRenderer()
        config = ChartConfig(
            chart_type=ChartType.BAR,
            labels=["Default"],
            datasets=[{"label": "S1", "values": [10]}],
        )
        svg = renderer.render_bar(config)
        assert svg.startswith("<svg")

    def test_render_bar_mismatched_data(self):
        """More values than labels should not crash."""
        renderer = ChartRenderer()
        config = ChartConfig(
            chart_type=ChartType.BAR,
            labels=["A"],
            datasets=[{"label": "S1", "values": [10, 20, 30]}],
        )
        svg = renderer.render_bar(config)
        assert svg.startswith("<svg")


# ── MediaEngine tests ───────────────────────────────────────────────

class TestMediaEngine:
    def test_generate_chart_returns_asset(self):
        engine = MediaEngine()
        config = ChartConfig(
            chart_type=ChartType.BAR,
            labels=["A", "B"], datasets=[{"label": "S1", "values": [10, 20]}],
        )
        asset = engine.generate_chart(config)
        assert asset.type == AssetType.CHART
        assert "svg" in asset.svg_content

    def test_generate_bar_chart(self):
        engine = MediaEngine()
        config = ChartConfig(
            chart_type=ChartType.BAR,
            labels=["A", "B"], datasets=[{"label": "S1", "values": [10, 20]}],
        )
        asset = engine.generate_chart(config)
        assert "rect" in asset.svg_content

    def test_generate_line_chart(self):
        engine = MediaEngine()
        config = ChartConfig(
            chart_type=ChartType.LINE,
            labels=["A", "B"], datasets=[{"label": "S1", "values": [10, 20]}],
        )
        asset = engine.generate_chart(config)
        assert "polyline" in asset.svg_content

    def test_generate_pie_chart(self):
        engine = MediaEngine()
        config = ChartConfig(
            chart_type=ChartType.PIE,
            labels=["A", "B"], datasets=[{"label": "S1", "values": [30, 70]}],
        )
        asset = engine.generate_chart(config)
        assert "path" in asset.svg_content

    def test_generate_text_overlay(self):
        engine = MediaEngine()
        config = TextOverlayConfig(text="Live Now!")
        asset = engine.generate_text_overlay(config)
        assert asset.type == AssetType.TEXT_OVERLAY
        assert "Live Now!" in asset.svg_content

    def test_get_asset(self):
        engine = MediaEngine()
        config = ChartConfig(
            chart_type=ChartType.BAR,
            labels=["A"], datasets=[{"label": "S1", "values": [10]}],
        )
        asset = engine.generate_chart(config)
        fetched = engine.get(asset.id)
        assert fetched is not None
        assert fetched.id == asset.id

    def test_get_asset_not_found(self):
        engine = MediaEngine()
        assert engine.get("nonexistent") is None

    def test_list_assets(self):
        engine = MediaEngine()
        c1 = ChartConfig(chart_type=ChartType.BAR, labels=["A", "B"], datasets=[{"label": "S1", "values": [10, 20]}])
        c2 = ChartConfig(chart_type=ChartType.LINE, labels=["A", "B"], datasets=[{"label": "S1", "values": [10, 20]}])
        engine.generate_chart(c1)
        engine.generate_chart(c2)
        assert len(engine.list()) == 2

    def test_list_assets_filter_by_type(self):
        engine = MediaEngine()
        c1 = ChartConfig(chart_type=ChartType.BAR, labels=["A"], datasets=[{"label": "S1", "values": [10]}])
        engine.generate_chart(c1)
        to = TextOverlayConfig(text="Test")
        engine.generate_text_overlay(to)
        charts = engine.list(type=AssetType.CHART)
        overlays = engine.list(type=AssetType.TEXT_OVERLAY)
        assert len(charts) >= 1
        assert len(overlays) >= 1

    def test_delete_asset(self):
        engine = MediaEngine()
        config = ChartConfig(chart_type=ChartType.BAR, labels=["A"], datasets=[{"label": "S1", "values": [10]}])
        asset = engine.generate_chart(config)
        assert engine.delete(asset.id) is True
        assert engine.get(asset.id) is None

    def test_delete_asset_not_found(self):
        engine = MediaEngine()
        assert engine.delete("nonexistent") is False

    def test_assign_to_segment(self):
        engine = MediaEngine()
        config = ChartConfig(chart_type=ChartType.BAR, labels=["A"], datasets=[{"label": "S1", "values": [10]}])
        asset = engine.generate_chart(config)
        assert engine.assign_to_segment(asset.id, "seg_1") is True
        assert asset.segment_id == "seg_1"
        assert asset.status.value == "assigned"

    def test_assign_not_found(self):
        engine = MediaEngine()
        assert engine.assign_to_segment("nonexistent", "seg_1") is False

    def test_enforces_cap(self):
        engine = MediaEngine()
        # Set max to 3 temporarily
        old_max = engine.MAX_ASSETS
        engine.MAX_ASSETS = 3
        config = ChartConfig(chart_type=ChartType.BAR, labels=["A", "B"], datasets=[{"label": "S1", "values": [10, 20]}])
        for _ in range(5):
            engine.generate_chart(config)
        assert len(engine.list()) == 3
        engine.MAX_ASSETS = old_max  # Restore


# ── MediaAgent tests ────────────────────────────────────────────────

class TestMediaAgent:
    def test_agent_identity(self):
        agent = MediaAgent()
        assert agent.agent_name == "Media"
        assert agent.agent_type == "media"

    def test_agent_start_stop(self):
        agent = MediaAgent()
        assert not agent.running
        agent.start()
        assert agent.running
        agent.start()  # idempotent
        assert agent.running
        agent.stop()
        assert not agent.running
        agent.stop()  # idempotent
        assert not agent.running

    def test_generate_chart(self):
        agent = MediaAgent()
        config = ChartConfig(
            chart_type=ChartType.BAR,
            labels=["A", "B"], datasets=[{"label": "S1", "values": [10, 20]}],
        )
        asset = agent.generate_chart(config)
        assert asset.type == AssetType.CHART

    def test_generate_text_overlay(self):
        agent = MediaAgent()
        config = TextOverlayConfig(text="Hello")
        asset = agent.generate_text_overlay(config)
        assert asset.type == AssetType.TEXT_OVERLAY

    def test_list_assets(self):
        agent = MediaAgent()
        config = ChartConfig(chart_type=ChartType.BAR, labels=["A"], datasets=[{"label": "S1", "values": [10]}])
        agent.generate_chart(config)
        assert len(agent.list_assets()) >= 1

    def test_delete_asset(self):
        agent = MediaAgent()
        config = ChartConfig(chart_type=ChartType.BAR, labels=["A", "B"], datasets=[{"label": "S1", "values": [10, 20]}])
        asset = agent.generate_chart(config)
        assert agent.delete_asset(asset.id) is True
        assert agent.get_asset(asset.id) is None

    def test_assign_to_segment(self):
        agent = MediaAgent()
        config = ChartConfig(chart_type=ChartType.BAR, labels=["A", "B"], datasets=[{"label": "S1", "values": [10, 20]}])
        asset = agent.generate_chart(config)
        assert agent.assign_to_segment(asset.id, "seg_1") is True
