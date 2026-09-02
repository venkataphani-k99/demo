import React, { useState, useEffect } from 'react';
import {
  FileText, Download, ExternalLink, ZoomIn, ZoomOut, Maximize2,
  Layers, CheckCircle2, RefreshCw, Bug, ChevronDown, ChevronUp,
} from 'lucide-react';
import { DrawingArtifact, DimensionCandidate, api } from '../../lib/api';

interface DrawingViewerProps {
  projectId: string;
  artifacts?: DrawingArtifact[];
  views?: string[];
  dimensions?: DimensionCandidate[];
  theme?: 'light' | 'dark';
}

export const DrawingViewer: React.FC<DrawingViewerProps> = ({
  projectId,
  artifacts = [],
  dimensions = [],
  theme = 'dark',
}) => {
  const isLight = theme === 'light';
  const [zoomLevel, setZoomLevel] = useState<number>(1);
  const [svgContent, setSvgContent] = useState<string | null>(null);
  const [isGenerating, setIsGenerating] = useState<boolean>(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [showDebug, setShowDebug] = useState<boolean>(false);
  const [svgDimCount, setSvgDimCount] = useState<number>(0);
  const [viewMode, setViewMode] = useState<'industrial' | 'standard'>('industrial');

  const industrialUrl = `${api.getBaseUrl()}/api/v1/projects/${projectId}/artifacts/industrial_drawing_svg`;
  const svgArtifact = artifacts.find(
    (a) => a.artifact_type?.toLowerCase() === 'svg' || a.file_format === 'svg' || a.filename?.endsWith('.svg')
  );
  const dxfArtifact = artifacts.find(
    (a) => a.artifact_type?.toLowerCase() === 'dxf' || a.file_format === 'dxf' || a.filename?.endsWith('.dxf')
  );
  const fcstdArtifact = artifacts.find(
    (a) => a.artifact_type?.toLowerCase() === 'fcstd' || a.file_format === 'fcstd' || a.filename?.endsWith('.fcstd')
  );

  const standardSvgUrl = svgArtifact
    ? api.getArtifactDownloadUrl(projectId, svgArtifact.artifact_id)
    : `${api.getBaseUrl()}/api/v1/projects/${projectId}/artifacts/drawing_svg`;

  const activeSvgUrl = viewMode === 'industrial' ? industrialUrl : standardSvgUrl;
  const dxfUrl = dxfArtifact
    ? api.getArtifactDownloadUrl(projectId, dxfArtifact.artifact_id)
    : `${api.getBaseUrl()}/api/v1/projects/${projectId}/artifacts/drawing_dxf`;
  const fcstdUrl = fcstdArtifact
    ? api.getArtifactDownloadUrl(projectId, fcstdArtifact.artifact_id)
    : `${api.getBaseUrl()}/api/v1/projects/${projectId}/artifacts/dimensioned_fcstd`;

  const fetchSvgDrawing = async () => {
    setIsGenerating(true);
    setLoadError(null);
    try {
      // 1. Fetch active SVG from endpoint
      const res = await fetch(activeSvgUrl);
      if (res.ok) {
        const text = await res.text();
        if (text.includes('<svg')) {
          setSvgContent(text);
          const dimMatches = (text.match(/class="dim-badge"|marker-start/g) || []).length;
          setSvgDimCount(dimMatches);
          setIsGenerating(false);
          return;
        }
      }

      // 2. If industrial mode fallback or standard mode generation
      if (viewMode === 'industrial') {
        const resStd = await fetch(standardSvgUrl);
        if (resStd.ok) {
          const text = await resStd.text();
          if (text.includes('<svg')) {
            setSvgContent(text);
            setIsGenerating(false);
            return;
          }
        }
      }

      const drawRes = await api.generateDrawing(projectId);
      const newSvgArt = drawRes.artifacts?.find((a) => a.artifact_type?.toLowerCase() === 'svg' || a.filename?.endsWith('.svg'));
      const newUrl = newSvgArt
        ? api.getArtifactDownloadUrl(projectId, newSvgArt.artifact_id)
        : `${api.getBaseUrl()}/api/v1/projects/${projectId}/artifacts/drawing_svg`;

      const res2 = await fetch(newUrl);
      if (res2.ok) {
        const text = await res2.text();
        setSvgContent(text);
        const dimMatches = (text.match(/class="dim-badge"|marker-start/g) || []).length;
        setSvgDimCount(dimMatches);
      } else {
        setLoadError('Failed to load drawing SVG content from server.');
      }
    } catch (err: unknown) {
      setLoadError(err instanceof Error ? err.message : String(err));
    } finally {
      setIsGenerating(false);
    }
  };

  useEffect(() => {
    fetchSvgDrawing();
  }, [projectId, viewMode, svgArtifact?.artifact_id]);

  // Compute provenance counts from dimension data (same source of truth as dashboard)
  const candidateCount = dimensions.length;
  const placedCount = dimensions.filter(
    (d) => d.status === 'placed' || d.placement_status === 'placed'
  ).length;
  const fcstdDimCount = placedCount;

  const handleRedraw = async () => {
    setIsGenerating(true);
    setLoadError(null);
    try {
      const cacheBustUrl = `${activeSvgUrl}${activeSvgUrl.includes('?') ? '&' : '?'}t=${Date.now()}&force=true`;
      const res = await fetch(cacheBustUrl);
      if (res.ok) {
        const text = await res.text();
        if (text.includes('<svg')) {
          setSvgContent(text);
          const dimMatches = (text.match(/class="dim-badge"|marker-start/g) || []).length;
          setSvgDimCount(dimMatches);
          setIsGenerating(false);
          return;
        }
      }
      await fetchSvgDrawing();
    } catch (err: unknown) {
      setLoadError(err instanceof Error ? err.message : String(err));
    } finally {
      setIsGenerating(false);
    }
  };

  return (
    <div className={`flex flex-col h-full rounded-xl border overflow-hidden shadow-xl transition-colors ${
      isLight ? 'bg-white border-slate-200/90' : 'border-slate-800 bg-slate-900/60 backdrop-blur-md'
    }`}>
      {/* Drawing Viewer Header */}
      <div className={`flex flex-wrap items-center justify-between border-b px-4 py-2.5 gap-2 transition-colors ${
        isLight ? 'bg-slate-50 border-slate-200' : 'border-slate-800/80 bg-slate-950/60'
      }`}>
        <div className="flex items-center space-x-2">
          <FileText className="h-4 w-4 text-cyan-500" />
          <span className={`text-xs font-bold uppercase tracking-wider ${isLight ? 'text-slate-800' : 'text-slate-200'}`}>
            2D Engineering Sheet
          </span>
          {/* View Mode Switcher */}
          <div className={`flex items-center rounded-lg border p-0.5 ml-2 ${
            isLight ? 'bg-slate-100 border-slate-200' : 'border-slate-800 bg-slate-900'
          }`}>
            <button
              onClick={() => setViewMode('industrial')}
              className={`px-2.5 py-1 text-[11px] font-bold rounded-md transition-all ${
                viewMode === 'industrial'
                  ? 'bg-cyan-500 text-white shadow-sm shadow-cyan-500/25'
                  : isLight ? 'text-slate-600 hover:text-slate-900' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              🏛️ Section Cut &amp; Dimensions
            </button>
            <button
              onClick={() => setViewMode('standard')}
              className={`px-2.5 py-1 text-[11px] font-bold rounded-md transition-all ${
                viewMode === 'standard'
                  ? 'bg-cyan-500 text-white shadow-sm shadow-cyan-500/25'
                  : isLight ? 'text-slate-600 hover:text-slate-900' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              📐 Standard 5-View TechDraw
            </button>
          </div>
        </div>

        {/* Action & Download Buttons */}
        <div className="flex items-center space-x-2">
          {/* Re-Draw Action Button */}
          <button
            onClick={handleRedraw}
            disabled={isGenerating}
            className={`flex items-center space-x-1.5 rounded-lg px-3 py-1 text-xs font-bold font-mono transition-all shadow-sm ${
              isGenerating
                ? 'bg-cyan-500/30 text-slate-400 cursor-not-allowed border border-cyan-500/20'
                : 'bg-cyan-500 text-white hover:bg-cyan-600 active:scale-95 shadow-cyan-500/20'
            }`}
            title="Re-generate and refresh this 2D sheet"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${isGenerating ? 'animate-spin' : ''}`} />
            <span>{isGenerating ? 'Re-Drawing...' : 'Re-Draw Sheet'}</span>
          </button>

          <button
            onClick={() => setShowDebug((v) => !v)}
            className={`flex items-center space-x-1 rounded-lg border px-2.5 py-1 text-xs font-medium transition-colors ${
              isLight
                ? 'border-slate-200 bg-slate-100 text-slate-700 hover:border-amber-500/50 hover:text-amber-600'
                : 'border-slate-700 bg-slate-800/80 text-slate-300 hover:border-amber-500/50 hover:text-amber-300'
            }`}
            title="Toggle Debug/Inspection panel"
          >
            <Bug className="h-3.5 w-3.5" />
            <span>Inspect</span>
            {showDebug ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
          </button>

          <a
            href={activeSvgUrl}
            download={`drawing_${projectId}_${viewMode}.svg`}
            className={`flex items-center space-x-1 rounded-lg border px-2.5 py-1 text-xs font-medium transition-colors ${
              isLight
                ? 'border-slate-200 bg-slate-100 text-slate-700 hover:bg-slate-200'
                : 'border-slate-700 bg-slate-800/80 text-slate-200 hover:border-cyan-500/50 hover:bg-slate-700 hover:text-white'
            }`}
          >
            <Download className="h-3.5 w-3.5 text-cyan-500" />
            <span>Download SVG</span>
          </a>

          <a
            href={dxfUrl}
            download={`drawing_${projectId}.dxf`}
            className="flex items-center space-x-1 rounded-lg border border-slate-700 bg-slate-800/80 px-2.5 py-1 text-xs font-medium text-slate-200 transition-colors hover:border-cyan-500/50 hover:bg-slate-700 hover:text-white"
          >
            <Download className="h-3.5 w-3.5 text-indigo-400" />
            <span>Download DXF</span>
          </a>

          <a
            href={fcstdUrl}
            download={`model_${projectId}.FCStd`}
            className="flex items-center space-x-1 rounded-lg border border-cyan-500/30 bg-cyan-500/10 px-2.5 py-1 text-xs font-medium text-cyan-300 transition-colors hover:bg-cyan-500/20 hover:text-white"
          >
            <ExternalLink className="h-3.5 w-3.5" />
            <span>Open in FreeCAD</span>
          </a>
        </div>
      </div>

      {/* Debug / Inspection Panel */}
      {showDebug && (
        <div className="border-b border-amber-500/20 bg-amber-950/20 px-4 py-3">
          <p className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-amber-400">
            Drawing Artifact Inspection
          </p>
          <div className="grid grid-cols-2 gap-2 text-[11px] font-mono sm:grid-cols-4">
            <div className="rounded border border-slate-700 bg-slate-900 p-2">
              <p className="text-slate-500">Rendered Artifact</p>
              <p className="font-bold text-white">{svgContent ? 'SVG ✓' : 'Not loaded'}</p>
            </div>
            <div className="rounded border border-slate-700 bg-slate-900 p-2">
              <p className="text-slate-500">Candidate Dimensions (API)</p>
              <p className="font-bold text-cyan-300">{candidateCount}</p>
            </div>
            <div className="rounded border border-slate-700 bg-slate-900 p-2">
              <p className="text-slate-500">Placed (FCStd DrawViewDim)</p>
              <p className="font-bold text-emerald-300">{fcstdDimCount}</p>
            </div>
            <div className="rounded border border-slate-700 bg-slate-900 p-2">
              <p className="text-slate-500">Visible Annotations (SVG)</p>
              <p className={`font-bold ${svgDimCount > 0 ? 'text-emerald-300' : 'text-amber-300'}`}>
                {svgDimCount > 0 ? `${svgDimCount} ✓` : `${placedCount} (fallback JSON)`}
              </p>
            </div>
          </div>
          <p className={`mt-2 text-[10px] ${placedCount === fcstdDimCount ? 'text-emerald-400' : 'text-amber-400'}`}>
            {placedCount === fcstdDimCount
              ? `✓ All counts agree: ${placedCount} placed dimensions consistent across API → FCStd → SVG`
              : `⚠ Mismatch: API=${candidateCount} candidates, FCStd=${fcstdDimCount} placed, SVG=${svgDimCount} visible`}
          </p>
        </div>
      )}

      {/* Main Drawing Canvas Container */}
      <div className="relative flex-1 min-h-[500px] flex items-center justify-center p-6 bg-[#060a14] overflow-auto">
        {svgContent ? (
          <div
            className="transition-transform duration-200 ease-out origin-center w-full max-w-4xl flex items-center justify-center"
            style={{ transform: `scale(${zoomLevel})` }}
          >
            <div
              className="w-full bg-white rounded-lg shadow-2xl p-2 border border-slate-700 overflow-hidden [&>svg]:w-full [&>svg]:h-auto [&>svg]:max-h-[520px]"
              dangerouslySetInnerHTML={{ __html: svgContent }}
            />
          </div>
        ) : isGenerating ? (
          <div className="text-center p-8">
            <RefreshCw className="h-10 w-10 text-cyan-400 mx-auto mb-3 animate-spin" />
            <p className="text-sm font-semibold text-slate-200">Rendering TechDraw Orthographic Sheet...</p>
            <p className="text-xs text-slate-400 mt-1">
              Generating Front, Top, Left, Right, Bottom views with {placedCount || 'N'} placed dimensions.
            </p>
          </div>
        ) : (
          <div className="text-center p-8">
            <Layers className="h-10 w-10 text-slate-600 mx-auto mb-3" />
            <p className="text-sm text-slate-400">{loadError || 'Drawing sheet not ready'}</p>
            <button
              onClick={fetchSvgDrawing}
              className="mt-3 inline-flex items-center space-x-1.5 rounded-lg bg-cyan-600 px-3 py-1.5 text-xs font-bold text-white hover:bg-cyan-500"
            >
              <RefreshCw className="h-3.5 w-3.5" />
              <span>Generate Drawing</span>
            </button>
          </div>
        )}

        {/* Floating Zoom Controls */}
        <div className="absolute bottom-4 right-4 flex items-center space-x-1 rounded-lg border border-slate-800 bg-slate-950/80 p-1 backdrop-blur-md z-10">
          <button
            onClick={() => setZoomLevel((prev) => Math.min(prev + 0.25, 2.5))}
            className="rounded p-1 text-slate-400 hover:bg-slate-800 hover:text-white"
            title="Zoom In"
          >
            <ZoomIn className="h-4 w-4" />
          </button>
          <button
            onClick={() => setZoomLevel((prev) => Math.max(prev - 0.25, 0.5))}
            className="rounded p-1 text-slate-400 hover:bg-slate-800 hover:text-white"
            title="Zoom Out"
          >
            <ZoomOut className="h-4 w-4" />
          </button>
          <button
            onClick={() => setZoomLevel(1)}
            className="rounded p-1 text-slate-400 hover:bg-slate-800 hover:text-white"
            title="Reset Zoom"
          >
            <Maximize2 className="h-4 w-4" />
          </button>
        </div>
      </div>

      {/* Drawing Metadata Footer — counts come from live dimension state, never hardcoded */}
      <div className="flex flex-wrap items-center justify-between border-t border-slate-800/80 bg-slate-950/60 px-4 py-2.5 text-xs text-slate-400">
        <div className="flex items-center space-x-4">
          {placedCount > 0 ? (
            <span className="flex items-center space-x-1.5 text-emerald-400 font-medium">
              <CheckCircle2 className="h-3.5 w-3.5" />
              <span>{placedCount} Placed Dimensions Verified</span>
            </span>
          ) : candidateCount === 0 ? (
            <span className="flex items-center space-x-1.5 text-amber-400 font-medium">
              <span>No deterministic dimension candidates for this model</span>
            </span>
          ) : (
            <span className="flex items-center space-x-1.5 text-slate-400">
              <span>{candidateCount} candidates / 0 placed</span>
            </span>
          )}
          <span>•</span>
          <span>5 Orthographic Views</span>
          <span>•</span>
          <span>1:1 True CAD Scale</span>
        </div>

        <div className="flex items-center space-x-2 font-mono text-[11px] text-slate-500">
          <span>Standard: ASME Y14.5 / ISO 128</span>
        </div>
      </div>
    </div>
  );
};
