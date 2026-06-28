import { useState, useEffect, useCallback } from "react";
import {
  createChart,
  createTextOverlay,
  listAssets,
  deleteAsset,
  assignAsset,
  ChartConfig as ChartConfigType,
  MediaAsset,
  ChartType,
  AssetType,
} from "../lib/api";

type Tab = "chart" | "text" | "gallery";

export function MediaPanel() {
  const [activeTab, setActiveTab] = useState<Tab>("chart");
  const [assets, setAssets] = useState<MediaAsset[]>([]);
  const [previewSvg, setPreviewSvg] = useState<string | null>(null);

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
    } catch {
      // silently fail
    }
  }, []);

  useEffect(() => {
    fetchAssets();
  }, [fetchAssets]);

  // ── Chart preview ──
  const updateChartPreview = useCallback(() => {
    const labelList = labels.split(",").map((s) => s.trim()).filter(Boolean);
    const valueList = seriesValues.split(",").map((s) => Number(s.trim())).filter((n) => !isNaN(n));
    if (labelList.length === 0 || valueList.length === 0) {
      setPreviewSvg(null);
      return;
    }
    // Build a temporary config and render preview via a GET-like approach
    // We'll generate inline SVG for preview using a simple approach
    const colors = ["#3B82F6", "#10B981", "#F59E0B", "#EF4444", "#8B5CF6"];
    const maxVal = Math.max(...valueList, 1);
    const width = 400;
    const height = 250;
    const barWidth = Math.max(8, Math.min(40, (width - 80) / valueList.length));

    let svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${width} ${height}" width="${width}" height="${height}">`;

    if (chartType === "bar") {
      const lm = 50, bm = 40;
      valueList.forEach((val, i) => {
        const barH = (val / maxVal) * (height - bm - 30);
        const x = lm + i * (barWidth + 4);
        const y = height - bm - barH;
        svg += `<rect x="${x}" y="${y}" width="${barWidth}" height="${barH}" fill="${colors[i % colors.length]}" rx="2"/>`;
        svg += `<text x="${x + barWidth / 2}" y="${height - bm + 14}" text-anchor="middle" font-size="9" fill="#666">${labelList[i] || ""}</text>`;
      });
    } else if (chartType === "line") {
      const step = (width - 100) / Math.max(valueList.length - 1, 1);
      const pts = valueList.map((val, i) => {
        const x = 60 + i * step;
        const y = height - 40 - ((val / maxVal) * (height - 80));
        svg += `<circle cx="${x}" cy="${y}" r="3" fill="${colors[0]}" stroke="#fff" stroke-width="1.5"/>`;
        return `${x},${y}`;
      });
      svg += `<polyline points="${pts.join(" ")}" fill="none" stroke="${colors[0]}" stroke-width="2" stroke-linejoin="round"/>`;
    } else if (chartType === "pie") {
      const cx = width / 2, cy = height / 2 - 10;
      const r = Math.min(width, height) / 2 - 40;
      const total = valueList.reduce((a, b) => a + b, 0) || 1;
      let angle = -90;
      valueList.forEach((val, i) => {
        if (val <= 0) return;
        const frac = val / total;
        const a = frac * 360;
        const sr = (angle * Math.PI) / 180;
        const er = ((angle + a) * Math.PI) / 180;
        const x1 = cx + r * Math.cos(sr), y1 = cy + r * Math.sin(sr);
        const x2 = cx + r * Math.cos(er), y2 = cy + r * Math.sin(er);
        const la = a > 180 ? 1 : 0;
        svg += `<path d="M ${cx} ${cy} L ${x1.toFixed(1)} ${y1.toFixed(1)} A ${r} ${r} 0 ${la} 1 ${x2.toFixed(1)} ${y2.toFixed(1)} Z" fill="${colors[i % colors.length]}" stroke="#fff" stroke-width="1.5"/>`;
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
    const labelList = labels.split(",").map((s) => s.trim()).filter(Boolean);
    const valueList = seriesValues.split(",").map((s) => Number(s.trim())).filter((n) => !isNaN(n));
    if (labelList.length === 0 || valueList.length === 0) return;

    const config: ChartConfigType = {
      chart_type: chartType,
      title: chartTitle,
      labels: labelList,
      datasets: [{ label: seriesLabel || "Series 1", values: valueList }],
    };

    try {
      await createChart(config);
      setActiveTab("gallery");
      await fetchAssets();
    } catch (err) {
      console.error("Failed to create chart:", err);
    }
  };

  const handleCreateText = async () => {
    if (!textContent.trim()) return;
    try {
      await createTextOverlay({
        text: textContent.trim(),
        font_size: fontSize,
        color: textColor,
        background_color: bgColor,
      });
      setActiveTab("gallery");
      await fetchAssets();
    } catch (err) {
      console.error("Failed to create text overlay:", err);
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await deleteAsset(id);
      await fetchAssets();
    } catch {
      // silently fail
    }
  };

  return (
    <div>
      <h2 className="text-lg font-semibold mb-4">Media Assets</h2>

      {/* Tabs */}
      <div className="flex gap-1 mb-4 border-b">
        {(["chart", "text", "gallery"] as Tab[]).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`px-4 py-2 text-sm font-medium capitalize transition-colors ${
              activeTab === tab
                ? "border-b-2 border-blue-600 text-blue-600"
                : "text-gray-500 hover:text-gray-700"
            }`}
          >
            {tab === "gallery" ? `Gallery (${assets.length})` : `Create ${tab === "text" ? "Text" : "Chart"}`}
          </button>
        ))}
      </div>

      {/* Chart tab */}
      {activeTab === "chart" && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">Chart Type</label>
              <select
                value={chartType}
                onChange={(e) => setChartType(e.target.value as ChartType)}
                className="w-full border rounded px-3 py-2 text-sm"
              >
                <option value="bar">Bar</option>
                <option value="line">Line</option>
                <option value="pie">Pie</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">Title</label>
              <input
                type="text"
                value={chartTitle}
                onChange={(e) => setChartTitle(e.target.value)}
                className="w-full border rounded px-3 py-2 text-sm"
                placeholder="Chart title (optional)"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">Labels (comma-separated)</label>
              <input
                type="text"
                value={labels}
                onChange={(e) => setLabels(e.target.value)}
                className="w-full border rounded px-3 py-2 text-sm"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">Series Label</label>
              <input
                type="text"
                value={seriesLabel}
                onChange={(e) => setSeriesLabel(e.target.value)}
                className="w-full border rounded px-3 py-2 text-sm"
              />
            </div>
            <div className="col-span-2">
              <label className="block text-xs font-medium text-gray-500 mb-1">Values (comma-separated)</label>
              <input
                type="text"
                value={seriesValues}
                onChange={(e) => setSeriesValues(e.target.value)}
                className="w-full border rounded px-3 py-2 text-sm"
              />
            </div>
          </div>

          {/* Preview */}
          {previewSvg && (
            <div className="border rounded p-4 bg-gray-50">
              <p className="text-xs font-medium text-gray-500 mb-2">Preview</p>
              <div className="flex justify-center" dangerouslySetInnerHTML={{ __html: previewSvg }} />
            </div>
          )}

          <button
            onClick={handleCreateChart}
            disabled={!labels.trim() || !seriesValues.trim()}
            className="bg-blue-600 text-white px-4 py-2 rounded text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
          >
            Create Chart
          </button>
        </div>
      )}

      {/* Text tab */}
      {activeTab === "text" && (
        <div className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">Text</label>
            <input
              type="text"
              value={textContent}
              onChange={(e) => setTextContent(e.target.value)}
              className="w-full border rounded px-3 py-2 text-sm"
              placeholder="Enter text for overlay..."
            />
          </div>
          <div className="grid grid-cols-3 gap-4">
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">Font Size</label>
              <input
                type="number"
                value={fontSize}
                onChange={(e) => setFontSize(Number(e.target.value))}
                className="w-full border rounded px-3 py-2 text-sm"
                min={12}
                max={200}
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">Text Color</label>
              <input
                type="text"
                value={textColor}
                onChange={(e) => setTextColor(e.target.value)}
                className="w-full border rounded px-3 py-2 text-sm"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">Background</label>
              <input
                type="text"
                value={bgColor}
                onChange={(e) => setBgColor(e.target.value)}
                className="w-full border rounded px-3 py-2 text-sm"
                placeholder="transparent or hex"
              />
            </div>
          </div>

          {/* Text preview */}
          <div
            className="border rounded p-4 flex items-center justify-center min-h-[100px]"
            style={{ backgroundColor: bgColor !== "transparent" ? bgColor : undefined }}
          >
            <span style={{ fontSize: fontSize, color: textColor }} className="font-sans">
              {textContent || "Preview"}
            </span>
          </div>

          <button
            onClick={handleCreateText}
            disabled={!textContent.trim()}
            className="bg-blue-600 text-white px-4 py-2 rounded text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
          >
            Create Text Overlay
          </button>
        </div>
      )}

      {/* Gallery tab */}
      {activeTab === "gallery" && (
        <div>
          {assets.length === 0 ? (
            <p className="text-sm text-gray-400 italic">No assets yet. Create one above!</p>
          ) : (
            <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
              {assets.map((asset) => (
                <div key={asset.id} className="border rounded p-3 bg-white">
                  <div className="flex justify-center mb-2 bg-gray-50 rounded p-2 min-h-[80px] items-center">
                    <div
                      className="w-full"
                      dangerouslySetInnerHTML={{
                        __html: asset.svg_content.slice(0, 1000) + (asset.svg_content.length > 1000 ? "..." : ""),
                      }}
                    />
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-gray-500 capitalize">{asset.type.replace("_", " ")}</span>
                    <div className="flex gap-1">
                      <button
                        onClick={() => handleDelete(asset.id)}
                        className="text-xs text-red-600 hover:text-red-800"
                      >
                        Delete
                      </button>
                    </div>
                  </div>
                  {asset.segment_id && (
                    <p className="text-xs text-gray-400 mt-1">Segment: {asset.segment_id}</p>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
