import { useState, useEffect, useCallback } from "react";
import {
  createChart,
  createTextOverlay,
  listAssets,
  deleteAsset,
} from "../lib/api";
import type { ChartConfig, MediaAsset, ChartType } from "../lib/api";

type Tab = "chart" | "text" | "gallery";

export function MediaPanel() {
  const [activeTab, setActiveTab] = useState<Tab>("chart");
  const [assets, setAssets] = useState<MediaAsset[]>([]);
  const [previewSvg, setPreviewSvg] = useState<string | null>(null);
  const [assetsLoading, setAssetsLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // ── Chart form state ──
  const [chartType, setChartType] = useState<ChartType>("bar");
  const [chartTitle, setChartTitle] = useState("");
  const [labels, setLabels] = useState("A, B, C");
  const [seriesLabel, setSeriesLabel] = useState("Series 1");
  const [seriesValues, setSeriesValues] = useState("10, 20, 30");

  // ── Text overlay form state ──
  const [textContent, setTextContent] = useState("");
  const [fontSize, setFontSize] = useState(48);
  const [textColor, setTextColor] = useState("#FFFFFF");
  const [bgColor, setBgColor] = useState("transparent");

  const fetchAssets = useCallback(async () => {
    try {
      const data = await listAssets();
      setAssets(data);
      setError(null);
    } catch {
      setError("Failed to load assets");
    }
    setAssetsLoading(false);
  }, []);

  useEffect(() => {
    fetchAssets();
  }, [fetchAssets]);

  // ── Chart preview ──
  const updateChartPreview = useCallback(() => {
    const labelList = labels
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
    const valueList = seriesValues
      .split(",")
      .map((s) => Number(s.trim()))
      .filter((n) => !isNaN(n));
    if (labelList.length === 0 || valueList.length === 0) {
      setPreviewSvg(null);
      return;
    }
    const darkColors = ["#6366f1", "#22c55e", "#f97316", "#3b82f6", "#eab308", "#ef4444", "#a855f7"];
    const maxVal = Math.max(...valueList, 1);
    const width = 400;
    const height = 250;
    const barWidth = Math.max(8, Math.min(40, (width - 80) / valueList.length));

    let svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${width} ${height}" width="${width}" height="${height}">`;
    svg += `<rect width="${width}" height="${height}" fill="#0d111d" rx="8"/>`;

    if (chartType === "bar") {
      const lm = 50,
        bm = 40;
      valueList.forEach((val, i) => {
        const barH = (val / maxVal) * (height - bm - 30);
        const x = lm + i * (barWidth + 4);
        const y = height - bm - barH;
        svg += `<rect x="${x}" y="${y}" width="${barWidth}" height="${barH}" fill="${darkColors[i % darkColors.length]}" rx="3"/>`;
        svg += `<text x="${x + barWidth / 2}" y="${height - bm + 14}" text-anchor="middle" font-size="9" fill="#94a3b8" font-family="monospace">${labelList[i] || ""}</text>`;
      });
    } else if (chartType === "line") {
      const step = (width - 100) / Math.max(valueList.length - 1, 1);
      const pts = valueList.map((val, i) => {
        const x = 60 + i * step;
        const y = height - 40 - (val / maxVal) * (height - 80);
        svg += `<circle cx="${x}" cy="${y}" r="4" fill="${darkColors[0]}" stroke="#151b2b" stroke-width="2"/>`;
        return `${x},${y}`;
      });
      svg += `<polyline points="${pts.join(" ")}" fill="none" stroke="${darkColors[0]}" stroke-width="2.5" stroke-linejoin="round"/>`;
    } else if (chartType === "pie") {
      const cx = width / 2,
        cy = height / 2 - 10;
      const r = Math.min(width, height) / 2 - 40;
      const total = valueList.reduce((a, b) => a + b, 0) || 1;
      let angle = -90;
      valueList.forEach((val, i) => {
        if (val <= 0) return;
        const frac = val / total;
        const a = frac * 360;
        const sr = (angle * Math.PI) / 180;
        const er = ((angle + a) * Math.PI) / 180;
        const x1 = cx + r * Math.cos(sr),
          y1 = cy + r * Math.sin(sr);
        const x2 = cx + r * Math.cos(er),
          y2 = cy + r * Math.sin(er);
        const la = a > 180 ? 1 : 0;
        svg += `<path d="M ${cx} ${cy} L ${x1.toFixed(1)} ${y1.toFixed(1)} A ${r} ${r} 0 ${la} 1 ${x2.toFixed(1)} ${y2.toFixed(1)} Z" fill="${darkColors[i % darkColors.length]}" stroke="#0d111d" stroke-width="2"/>`;
        angle += a;
      });
    }
    svg += "</svg>";
    setPreviewSvg(svg);
  }, [chartType, labels, seriesValues]);

  useEffect(() => {
    updateChartPreview();
  }, [updateChartPreview]);

  // ── Actions ──
  const handleCreateChart = async () => {
    const labelList = labels
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
    const valueList = seriesValues
      .split(",")
      .map((s) => Number(s.trim()))
      .filter((n) => !isNaN(n));
    if (labelList.length === 0 || valueList.length === 0) return;

    const config: ChartConfig = {
      chart_type: chartType,
      title: chartTitle,
      labels: labelList,
      datasets: [{ label: seriesLabel || "Series 1", values: valueList }],
    };

    setCreating(true);
    setError(null);
    try {
      await createChart(config);
      setActiveTab("gallery");
      await fetchAssets();
    } catch {
      setError("Failed to create chart");
    }
    setCreating(false);
  };

  const handleCreateText = async () => {
    if (!textContent.trim()) return;
    setCreating(true);
    setError(null);
    try {
      await createTextOverlay({
        text: textContent.trim(),
        font_size: fontSize,
        color: textColor,
        background_color: bgColor,
      });
      setActiveTab("gallery");
      await fetchAssets();
    } catch {
      setError("Failed to create text overlay");
    }
    setCreating(false);
  };

  const handleDelete = async (id: string) => {
    setError(null);
    try {
      await deleteAsset(id);
      await fetchAssets();
    } catch {
      setError("Failed to delete asset");
    }
  };

  const tabs: Tab[] = ["chart", "text", "gallery"];

  return (
    <div className="bg-surface border border-border rounded-lg p-6">
      <h2 className="text-sm font-semibold text-text uppercase tracking-[0.08em] mb-4">Media Assets</h2>

      {/* Error banner */}
      {error && (
        <div className="bg-danger-bg border border-danger/30 rounded-lg px-4 py-3 mb-4" role="alert">
          <p className="text-sm text-danger">{error}</p>
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-1 mb-5 border-b border-border">
        {tabs.map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`px-4 py-2.5 text-sm font-medium capitalize transition-all relative ${
              activeTab === tab
                ? "text-brand"
                : "text-text-muted hover:text-text-secondary"
            } focus:outline-none focus:ring-2 focus:ring-brand/50 rounded-t-lg`}
          >
            {tab === "gallery"
              ? `Gallery (${assets.length})`
              : `Create ${tab === "text" ? "Text" : "Chart"}`}
            {activeTab === tab && (
              <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-brand rounded-full" />
            )}
          </button>
        ))}
      </div>

      {/* Loading skeleton for gallery tab */}
      {assetsLoading && activeTab === "gallery" && (
        <div className="animate-pulse" aria-hidden="true">
          <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
            {[...Array(3)].map((_, i) => (
              <div key={i} className="h-44 bg-elevated rounded-lg" />
            ))}
          </div>
        </div>
      )}

      {/* Chart tab */}
      {activeTab === "chart" && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label htmlFor="chart-type" className="block text-xs font-medium text-text-muted uppercase tracking-wider mb-1.5">
                Chart Type
              </label>
              <select
                id="chart-type"
                value={chartType}
                onChange={(e) => setChartType(e.target.value as ChartType)}
                className="w-full px-3.5 py-2.5 bg-base border border-border rounded-lg text-sm text-text focus:outline-none focus:ring-2 focus:ring-brand/50 focus:border-brand/50 transition-all"
              >
                <option value="bar">Bar</option>
                <option value="line">Line</option>
                <option value="pie">Pie</option>
              </select>
            </div>
            <div>
              <label htmlFor="chart-title" className="block text-xs font-medium text-text-muted uppercase tracking-wider mb-1.5">
                Title
              </label>
              <input
                id="chart-title"
                type="text"
                value={chartTitle}
                onChange={(e) => setChartTitle(e.target.value)}
                className="w-full px-3.5 py-2.5 bg-base border border-border rounded-lg text-sm text-text placeholder-text-muted focus:outline-none focus:ring-2 focus:ring-brand/50 focus:border-brand/50 transition-all"
                placeholder="Chart title (optional)"
              />
            </div>
            <div>
              <label htmlFor="chart-labels" className="block text-xs font-medium text-text-muted uppercase tracking-wider mb-1.5">
                Labels (comma-separated)
              </label>
              <input
                id="chart-labels"
                type="text"
                value={labels}
                onChange={(e) => setLabels(e.target.value)}
                className="w-full px-3.5 py-2.5 bg-base border border-border rounded-lg text-sm text-text placeholder-text-muted focus:outline-none focus:ring-2 focus:ring-brand/50 focus:border-brand/50 transition-all"
              />
            </div>
            <div>
              <label htmlFor="chart-series-label" className="block text-xs font-medium text-text-muted uppercase tracking-wider mb-1.5">
                Series Label
              </label>
              <input
                id="chart-series-label"
                type="text"
                value={seriesLabel}
                onChange={(e) => setSeriesLabel(e.target.value)}
                className="w-full px-3.5 py-2.5 bg-base border border-border rounded-lg text-sm text-text placeholder-text-muted focus:outline-none focus:ring-2 focus:ring-brand/50 focus:border-brand/50 transition-all"
              />
            </div>
            <div className="col-span-2">
              <label htmlFor="chart-values" className="block text-xs font-medium text-text-muted uppercase tracking-wider mb-1.5">
                Values (comma-separated)
              </label>
              <input
                id="chart-values"
                type="text"
                value={seriesValues}
                onChange={(e) => setSeriesValues(e.target.value)}
                className="w-full px-3.5 py-2.5 bg-base border border-border rounded-lg text-sm text-text placeholder-text-muted focus:outline-none focus:ring-2 focus:ring-brand/50 focus:border-brand/50 transition-all"
              />
            </div>
          </div>

          {/* Preview */}
          {previewSvg && (
            <div className="bg-elevated border border-border rounded-lg p-4">
              <p className="text-xs font-medium text-text-muted uppercase tracking-wider mb-3">
                Preview
              </p>
              <div
                className="flex justify-center bg-base rounded-lg p-4"
                dangerouslySetInnerHTML={{ __html: previewSvg }}
              />
            </div>
          )}

          <button
            onClick={handleCreateChart}
            disabled={!labels.trim() || !seriesValues.trim() || creating}
            className="w-full px-4 py-2.5 bg-brand hover:bg-brand-hover text-white rounded-lg text-sm font-medium focus:outline-none focus:ring-2 focus:ring-brand/50 disabled:opacity-40 disabled:cursor-not-allowed transition-all"
          >
            {creating ? (
              <span className="flex items-center justify-center gap-2">
                <span className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                Creating...
              </span>
            ) : (
              "Create Chart"
            )}
          </button>
        </div>
      )}

      {/* Text tab */}
      {activeTab === "text" && (
        <div className="space-y-4">
          <div>
            <label htmlFor="text-content" className="block text-xs font-medium text-text-muted uppercase tracking-wider mb-1.5">
              Text
            </label>
            <input
              id="text-content"
              type="text"
              value={textContent}
              onChange={(e) => setTextContent(e.target.value)}
              className="w-full px-3.5 py-2.5 bg-base border border-border rounded-lg text-sm text-text placeholder-text-muted focus:outline-none focus:ring-2 focus:ring-brand/50 focus:border-brand/50 transition-all"
              placeholder="Enter text for overlay..."
            />
          </div>
          <div className="grid grid-cols-3 gap-4">
            <div>
              <label htmlFor="text-font-size" className="block text-xs font-medium text-text-muted uppercase tracking-wider mb-1.5">
                Font Size
              </label>
              <input
                id="text-font-size"
                type="number"
                value={fontSize}
                onChange={(e) => setFontSize(Number(e.target.value))}
                className="w-full px-3.5 py-2.5 bg-base border border-border rounded-lg text-sm text-text focus:outline-none focus:ring-2 focus:ring-brand/50 focus:border-brand/50 transition-all"
                min={12}
                max={200}
              />
            </div>
            <div>
              <label htmlFor="text-color" className="block text-xs font-medium text-text-muted uppercase tracking-wider mb-1.5">
                Text Color
              </label>
              <div className="flex gap-2 items-center">
                <label htmlFor="text-color-picker" className="sr-only">Text color picker</label>
                <input
                  id="text-color-picker"
                  type="color"
                  value={textColor}
                  onChange={(e) => setTextColor(e.target.value)}
                  className="w-9 h-9 rounded-lg border border-border bg-base cursor-pointer p-0.5"
                />
                <input
                  id="text-color"
                  type="text"
                  value={textColor}
                  onChange={(e) => setTextColor(e.target.value)}
                  className="flex-1 px-3.5 py-2.5 bg-base border border-border rounded-lg text-sm text-text font-mono focus:outline-none focus:ring-2 focus:ring-brand/50 focus:border-brand/50 transition-all"
                />
              </div>
            </div>
            <div>
              <label htmlFor="bg-color" className="block text-xs font-medium text-text-muted uppercase tracking-wider mb-1.5">
                Background
              </label>
              <div className="flex gap-2 items-center">
                <label htmlFor="bg-color-picker" className="sr-only">Background color picker</label>
                <input
                  id="bg-color-picker"
                  type="color"
                  value={bgColor === "transparent" ? "#000000" : bgColor}
                  onChange={(e) => setBgColor(e.target.value)}
                  className="w-9 h-9 rounded-lg border border-border bg-base cursor-pointer p-0.5"
                />
                <input
                  id="bg-color"
                  type="text"
                  value={bgColor}
                  onChange={(e) => setBgColor(e.target.value)}
                  className="flex-1 px-3.5 py-2.5 bg-base border border-border rounded-lg text-sm text-text font-mono focus:outline-none focus:ring-2 focus:ring-brand/50 focus:border-brand/50 transition-all"
                  placeholder="transparent or hex"
                />
              </div>
            </div>
          </div>

          {/* Text preview */}
          <div className="bg-elevated border border-border rounded-lg p-5">
            <p className="text-xs font-medium text-text-muted uppercase tracking-wider mb-3">
              Preview
            </p>
            <div
              className="rounded-lg p-6 flex items-center justify-center min-h-[120px] bg-base border border-border/50"
              style={{ backgroundColor: bgColor !== "transparent" ? bgColor : undefined }}
            >
              <span
                style={{ fontSize: `${fontSize}px`, color: textColor }}
                className="font-sans leading-tight"
              >
                {textContent || "Preview"}
              </span>
            </div>
          </div>

          <button
            onClick={handleCreateText}
            disabled={!textContent.trim() || creating}
            className="w-full px-4 py-2.5 bg-brand hover:bg-brand-hover text-white rounded-lg text-sm font-medium focus:outline-none focus:ring-2 focus:ring-brand/50 disabled:opacity-40 disabled:cursor-not-allowed transition-all"
          >
            {creating ? (
              <span className="flex items-center justify-center gap-2">
                <span className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                Creating...
              </span>
            ) : (
              "Create Text Overlay"
            )}
          </button>
        </div>
      )}

      {/* Gallery tab */}
      {activeTab === "gallery" && !assetsLoading && (
        <div aria-live="polite">
          {assets.length === 0 ? (
            <div className="border border-dashed border-border rounded-lg p-10 text-center">
              <p className="text-sm text-text-muted">No assets yet</p>
              <p className="text-xs text-text-muted/60 mt-1">Create a chart or text overlay above</p>
            </div>
          ) : (
            <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
              {assets.map((asset) => (
                <div
                  key={asset.id}
                  className="bg-elevated border border-border rounded-lg overflow-hidden hover:border-brand/30 transition-all group"
                >
                  <div className="flex justify-center items-center bg-base p-3 min-h-[100px]">
                    <div
                      className="w-full h-32 overflow-hidden flex items-center justify-center"
                      dangerouslySetInnerHTML={{
                        __html: asset.svg_content,
                      }}
                    />
                  </div>
                  <div className="p-3 border-t border-border/50">
                    <div className="flex items-center justify-between">
                      <span className="text-xs text-text-muted font-mono capitalize">
                        {asset.type.replace("_", " ")}
                      </span>
                      <button
                        onClick={() => handleDelete(asset.id)}
                        className="text-xs font-medium text-danger hover:text-danger/80 opacity-0 group-hover:opacity-100 transition-all focus:opacity-100 focus:outline-none focus:ring-2 focus:ring-danger/50 rounded px-1.5 py-0.5"
                      >
                        Delete
                      </button>
                    </div>
                    {asset.segment_id && (
                      <p className="text-xs text-text-muted/60 mt-0.5 font-mono">
                        Segment: {asset.segment_id}
                      </p>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
