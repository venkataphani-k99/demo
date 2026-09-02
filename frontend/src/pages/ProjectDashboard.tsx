import React, { useEffect, useState, useRef } from 'react';
import {
  Box,
  FileText,
  Cpu,
  Ruler,
  Bot,
  ShieldCheck,
  CheckCircle2,
  AlertTriangle,
  Layers,
  Sparkles,
  RefreshCw,
  Download,
  Info,
  Fingerprint,
  HardDrive,
  Clock,
  FileCode,
  Copy,
  Check,
  Compass,
} from 'lucide-react';
import {
  ProjectResponse,
  CADAnalysisResponse,
  RecognizedFeature,
  DimensionCandidate,
  DimensionListResponse,
  DrawingResponse,
  EngineeringIssue,
  EngineeringRecommendation,
  ReviewSummaryResponse,
  AIReviewResponse,
  CADMeshResponse,
  EngineeringIntelligenceResponse,
  api,
} from '../../lib/api';
import { Viewer3D } from '../components/Viewer3D';
import { DrawingViewer } from '../components/DrawingViewer';
import { FeaturesTable } from '../components/FeaturesTable';
import { DimensionsTable } from '../components/DimensionsTable';
import { AIReviewPanel } from '../components/AIReviewPanel';
import { EngineeringIssuesPanel } from '../components/EngineeringIssuesPanel';
import { EngineeringIntelligencePanel } from '../components/EngineeringIntelligencePanel';
import { EngineeringDesignReviewCockpit } from '../components/EngineeringDesignReviewCockpit';
import { MoldAnalysisViewer } from '../components/MoldAnalysisViewer';

interface ProjectDashboardProps {
  projectId: string;
  theme?: 'light' | 'dark';
  onToggleTheme?: () => void;
}

export const ProjectDashboard: React.FC<ProjectDashboardProps> = ({ projectId, theme = 'light', onToggleTheme }) => {
  const [project, setProject] = useState<ProjectResponse | null>(null);
  const [analysis, setAnalysis] = useState<CADAnalysisResponse | null>(null);
  const [features, setFeatures] = useState<RecognizedFeature[]>([]);
  const [dimensions, setDimensions] = useState<DimensionCandidate[]>([]);
  const [dimensionSummary, setDimensionSummary] = useState<DimensionListResponse | null>(null);
  const [drawing, setDrawing] = useState<DrawingResponse | null>(null);
  const [reviewSummary, setReviewSummary] = useState<ReviewSummaryResponse | null>(null);
  const [aiReview, setAiReview] = useState<AIReviewResponse | null>(null);
  const [meshData, setMeshData] = useState<CADMeshResponse | null>(null);
  const [issues, setIssues] = useState<EngineeringIssue[]>([]);
  const [recommendations, setRecommendations] = useState<EngineeringRecommendation[]>([]);

  const [selectedFeatureId, setSelectedFeatureId] = useState<string | null>(null);
  const [selectedFaceId, setSelectedFaceId] = useState<string | null>(null);
  const [selectedDimensionId, setSelectedDimensionId] = useState<string | null>(null);
  const [selectedSectionId, setSelectedSectionId] = useState<string>('SEC_AA');
  const [intelData, setIntelData] = useState<EngineeringIntelligenceResponse | null>(null);
  const [activeTab, setActiveTab] = useState<'intelligence' | 'mold' | '3d' | '2d' | 'features' | 'ai' | 'issues'>('intelligence');
  const [featuresSubTab, setFeaturesSubTab] = useState<'stacked' | 'features' | 'dimensions' | 'split'>('stacked');
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [copiedSha, setCopiedSha] = useState<boolean>(false);

  const activeSection = intelData?.section_recommendations?.candidates?.find((s) => s.section_id === selectedSectionId) || intelData?.section_recommendations?.candidates?.[0] || null;

  const loadAllData = async () => {
    setIsLoading(true);
    setError(null);
    try {
      // 1. Fetch core metadata, analysis, features, mesh, and engineering intelligence
      const [proj, ana, featList, meshRes, intelRes] = await Promise.all([
        api.getProject(projectId).catch(() => null),
        api.analyzeProject(projectId).catch(() => null),
        api.getFeatures(projectId).catch(() => [] as RecognizedFeature[]),
        api.getMesh(projectId).catch(() => null),
        api.getEngineeringIntelligence(projectId).catch(() => null),
      ]);

      if (proj) setProject(proj);
      if (ana) setAnalysis(ana);
      if (featList && featList.length > 0) setFeatures(featList);
      if (meshRes) setMeshData(meshRes);
      if (intelRes) setIntelData(intelRes);

      // Unblock UI immediately so the 3D model is visible and interactive in ~2s
      setIsLoading(false);

      // 2. Load lightweight metadata & reviews in background without spawning heavy CAD subprocesses
      Promise.all([
        api.getReviewSummary(projectId).catch(() => null),
        api.getIssues(projectId).catch(() => [] as EngineeringIssue[]),
        api.getRecommendations(projectId).catch(() => [] as EngineeringRecommendation[]),
        api.getExistingAIReview(projectId).catch(() => null),
      ]).then(([summaryRes, issList, recList, existingReview]) => {
        if (summaryRes) setReviewSummary(summaryRes);
        if (issList && issList.length > 0) setIssues(issList);
        if (recList && recList.length > 0) setRecommendations(recList);
        if (existingReview) setAiReview(existingReview);
      });
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err));
      setIsLoading(false);
    }
  };

  const handleFetchIntelData = async () => {
    setIsLoading(true);
    try {
      const res = await api.getEngineeringIntelligence(projectId);
      if (res) setIntelData(res);
    } catch (e) {
      console.error('Failed to load intel data:', e);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadAllData();
  }, [projectId]);

  useEffect(() => {
    if (activeTab === 'intelligence' && !intelData) {
      handleFetchIntelData();
    }
  }, [activeTab, intelData]);

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedSha(true);
    setTimeout(() => setCopiedSha(false), 2000);
  };

  const formatFileSize = (bytes?: number) => {
    if (!bytes || bytes === 0) return 'N/A';
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
  };

  if (isLoading) {
    return (
      <div className="flex min-h-[70vh] flex-col items-center justify-center p-8 text-center">
        <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-cyan-500/10 text-cyan-400 border border-cyan-500/20 shadow-xl shadow-cyan-500/10 animate-spin">
          <RefreshCw className="h-8 w-8" />
        </div>
        <h3 className="mt-6 text-lg font-bold text-white">Loading CAD Intelligence Workspace...</h3>
        <p className="mt-1 text-xs text-slate-400 max-w-sm">
          Extracting B-Rep topology graph, exact measurements, TechDraw orthographic projections, and multimodal review models.
        </p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="mx-auto max-w-4xl px-4 py-12">
        <div className="rounded-xl border border-rose-500/30 bg-rose-500/10 p-6 text-rose-300">
          <div className="flex items-center space-x-3">
            <AlertTriangle className="h-6 w-6 text-rose-400" />
            <h3 className="text-base font-bold text-white">Error Loading Project</h3>
          </div>
          <p className="mt-2 text-xs text-rose-300 font-mono">{error}</p>
          <button
            onClick={loadAllData}
            className="mt-4 rounded-lg bg-rose-600 px-4 py-2 text-xs font-bold text-white hover:bg-rose-500"
          >
            Retry Connection
          </button>
        </div>
      </div>
    );
  }

  const rawBbox = analysis?.bounding_box || (analysis as unknown as { summary: { bounding_box: Record<string, number> } })?.summary?.bounding_box;
  // Use mesh tessellation bounds as the primary source (they are computed from real vertex positions)
  // then fall back to the analysis bounding_box, both sanitized against 1e100 OCCT sentinels.
  const meshBounds = meshData?.bounds;

  const topology = analysis?.topology || (analysis as unknown as { summary: { faces: number; edges: number } })?.summary;

  // Sanitize bounding box: OCC sometimes returns uninitialized extreme numbers (~1e100)
  const sanitizeDim = (val: number | undefined, fallback: number | undefined) => {
    if (val !== undefined && isFinite(val) && val > 0 && val < 1e6) return val;
    if (fallback !== undefined && isFinite(fallback) && fallback > 0 && fallback < 1e6) return fallback;
    return 0.0;
  };

  // Mesh bounds (vertex-based, always real) first; analysis bbox second
  const xLen = sanitizeDim(meshBounds?.x_len, rawBbox?.x_length ?? (rawBbox as unknown as { x_len?: number })?.x_len);
  const yLen = sanitizeDim(meshBounds?.y_len, rawBbox?.y_length ?? (rawBbox as unknown as { y_len?: number })?.y_len);
  const zLen = sanitizeDim(meshBounds?.z_len, rawBbox?.z_length ?? (rawBbox as unknown as { z_len?: number })?.z_len);
  const volumeMm3 = analysis?.volume_mm3;
  const surfaceAreaMm2 = analysis?.surface_area_mm2;

  const facesCount = topology?.faces ?? meshData?.stats?.face_count ?? 0;
  const edgesCount = topology?.edges ?? meshData?.stats?.edge_segments ?? 0;
  // Authoritative placed count: from dimensionSummary (the pipeline placed_count field), then filter
  const placedDimsCount =
    dimensionSummary?.placed_count ??
    dimensions.filter((d) => d.status === 'placed' || d.placement_status === 'placed').length;
  const totalCandidatesCount =
    dimensionSummary?.engineering_candidates_count ??
    dimensionSummary?.total_candidates ??
    dimensions.length;

  const shaHash = project?.sha256_hash || analysis?.sha256_hash || 'Calculating...';
  const fileName = project?.filename || analysis?.filename || 'Unknown Model.step';
  const fileBytes = project?.file_size_bytes || analysis?.file_size_bytes;
  const sourcePath = analysis?.source_file || `workspaces/${projectId}/${fileName}`;
  const timestamp = analysis?.analysis_timestamp || project?.created_at || new Date().toISOString();

  const isLight = theme === 'light';
  const bgCard = isLight ? 'bg-white border-slate-200 shadow-sm' : 'bg-slate-900/60 border-slate-800 shadow-lg';
  const textHead = isLight ? 'text-slate-900' : 'text-white';
  const textMuted = isLight ? 'text-slate-500' : 'text-slate-400';

  return (
    <div className="w-full max-w-[1920px] mx-auto px-3 sm:px-6 lg:px-8 py-4 space-y-5">
      {/* 0. Source / Model Identity & Provenance Card */}
      <div className={`rounded-2xl border p-4 shadow-xl backdrop-blur-md transition-all ${
        isLight
          ? 'bg-gradient-to-r from-white via-cyan-50/40 to-blue-50/30 border-slate-200'
          : 'border-cyan-500/30 bg-gradient-to-r from-slate-900/90 via-slate-900/60 to-slate-950/90'
      }`}>
        <div className={`flex flex-wrap items-center justify-between gap-4 border-b pb-3 ${isLight ? 'border-slate-200' : 'border-slate-800/80'}`}>
          <div className="flex items-center space-x-3">
            <div className="rounded-xl bg-cyan-500/15 p-2 text-cyan-600 dark:text-cyan-400 border border-cyan-500/30">
              <FileCode className="h-5 w-5" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <h2 className={`text-base font-black tracking-tight ${textHead}`}>{fileName}</h2>
                <span className="rounded-full bg-emerald-500/10 px-2.5 py-0.5 text-[10px] font-mono font-bold text-emerald-600 dark:text-emerald-400 border border-emerald-500/20">
                  ISOLATED PROJECT WORKSPACE
                </span>
              </div>
              <p className={`text-xs font-mono flex items-center space-x-2 mt-0.5 ${textMuted}`}>
                <span>Project ID:</span>
                <span className="text-cyan-600 dark:text-cyan-300 font-bold">{projectId}</span>
              </p>
            </div>
          </div>

          <div className={`flex items-center space-x-3 text-xs font-mono ${textMuted}`}>
            <div className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-xl border ${isLight ? 'bg-slate-100 border-slate-200' : 'bg-slate-950/80 border-slate-800'}`}>
              <HardDrive className="h-3.5 w-3.5 text-slate-400" />
              <span className="font-bold">{formatFileSize(fileBytes)}</span>
            </div>
            <div className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-xl border ${isLight ? 'bg-slate-100 border-slate-200' : 'bg-slate-950/80 border-slate-800'}`}>
              <Clock className="h-3.5 w-3.5 text-slate-400" />
              <span className="font-bold">{new Date(timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}</span>
            </div>
          </div>
        </div>

        {/* SHA-256 Provenance & File Path */}
        <div className="mt-3 grid grid-cols-1 md:grid-cols-2 gap-3 text-[11px] font-mono">
          <div className={`flex items-center justify-between px-3 py-2 rounded-xl border ${isLight ? 'bg-slate-50 border-slate-200' : 'bg-slate-950/60 border-slate-800/80'}`}>
            <div className="flex items-center space-x-2 truncate">
              <Fingerprint className="h-3.5 w-3.5 text-cyan-500 flex-shrink-0" />
              <span className="text-slate-400 font-semibold">SHA-256:</span>
              <span className="text-cyan-700 dark:text-cyan-200 truncate font-bold" title={shaHash}>
                {shaHash.length > 24 ? `${shaHash.substring(0, 16)}...${shaHash.substring(shaHash.length - 8)}` : shaHash}
              </span>
            </div>
            <button
              onClick={() => copyToClipboard(shaHash)}
              className="ml-2 flex-shrink-0 text-slate-400 hover:text-cyan-600 dark:hover:text-cyan-300 transition-colors p-1"
              title="Copy Full SHA-256"
            >
              {copiedSha ? <Check className="h-3.5 w-3.5 text-emerald-500" /> : <Copy className="h-3.5 w-3.5" />}
            </button>
          </div>

          <div className={`flex items-center space-x-2 px-3 py-2 rounded-xl border truncate ${isLight ? 'bg-slate-50 border-slate-200' : 'bg-slate-950/60 border-slate-800/80'}`}>
            <FileText className="h-3.5 w-3.5 text-slate-400 flex-shrink-0" />
            <span className="text-slate-400 font-semibold">Source:</span>
            <span className={`truncate font-medium ${isLight ? 'text-slate-700' : 'text-slate-300'}`} title={sourcePath}>
              {sourcePath}
            </span>
          </div>
        </div>
      </div>

      {/* 1. Model & Project Stats Banner */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {/* Model Extents */}
        <div className={`rounded-2xl border p-4 backdrop-blur-md transition-all ${bgCard}`}>
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400">Bounding Box Extents</span>
            <Box className="h-4 w-4 text-cyan-500" />
          </div>
          <p className={`mt-2 text-base font-black font-mono ${textHead}`}>
            {`${Number(xLen).toFixed(1)} × ${Number(yLen).toFixed(1)} × ${Number(zLen).toFixed(1)}`}{' '}
            <span className="text-xs text-slate-400 font-normal">mm</span>
          </p>
          <div className="mt-1 flex items-center space-x-2 text-[11px] text-slate-400 font-mono">
            <span>{facesCount} Faces</span>
            <span>•</span>
            <span>{edgesCount} Edges</span>
          </div>
        </div>

        {/* Features Count */}
        <div className={`rounded-2xl border p-4 backdrop-blur-md transition-all ${bgCard}`}>
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400">Recognized Features</span>
            <Cpu className="h-4 w-4 text-cyan-500" />
          </div>
          <p className="mt-2 text-xl font-black font-mono text-cyan-600 dark:text-cyan-300">
            {features.length} <span className="text-xs text-slate-400 font-normal">Features</span>
          </p>
          <span className="mt-1 inline-flex items-center text-[10px] text-emerald-600 dark:text-emerald-400 font-bold">
            <CheckCircle2 className="h-3 w-3 mr-1" />
            100% Deterministic B-Rep
          </span>
        </div>

        {/* Dimensioned TechDraw Status */}
        <div className={`rounded-2xl border p-4 backdrop-blur-md transition-all ${bgCard}`}>
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400">TechDraw Placements</span>
            <Ruler className="h-4 w-4 text-cyan-500" />
          </div>
          <p className="mt-2 text-xl font-black font-mono text-emerald-600 dark:text-emerald-400">
            {placedDimsCount} / {dimensions.length}
          </p>
          <span className="mt-1 text-[10px] text-slate-400 font-mono">
            5 Views (Third-Angle Layout)
          </span>
        </div>

        {/* Human Review Status */}
        <div className={`rounded-2xl border p-4 backdrop-blur-md transition-all ${bgCard}`}>
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400">Human Approval Gate</span>
            <ShieldCheck className="h-4 w-4 text-amber-500" />
          </div>
          <p className="mt-2 text-sm font-black font-mono text-amber-600 dark:text-amber-300">
            {issues.length > 0 ? 'AWAITING APPROVAL' : 'VERIFIED CLEAN'}
          </p>
          <span className="mt-1 text-[10px] text-slate-400 font-mono">
            {issues.length} Issues • Zero Auto-Mutation
          </span>
        </div>
      </div>

      {/* 2. Navigation Tabs */}
      <div className={`flex flex-wrap items-center gap-1.5 p-1.5 rounded-2xl border transition-all ${
        isLight ? 'bg-slate-100 border-slate-200' : 'bg-slate-950/80 border-slate-800'
      }`}>
        <button
          onClick={() => setActiveTab('intelligence')}
          className={`flex items-center space-x-2 rounded-xl px-4 py-2 text-xs font-black transition-all ${
            activeTab === 'intelligence'
              ? 'bg-cyan-500 text-white shadow-md shadow-cyan-500/25'
              : isLight
              ? 'text-slate-600 hover:text-slate-900 hover:bg-slate-200/60'
              : 'text-slate-400 hover:text-white hover:bg-slate-900'
          }`}
        >
          <Cpu className="h-4 w-4" />
          <span>Engineering Design Review Cockpit</span>
          <span className={`rounded-full px-2 py-0.5 text-[10px] font-mono font-bold ${
            activeTab === 'intelligence' ? 'bg-white/20 text-white' : 'bg-cyan-500/10 text-cyan-600 dark:text-cyan-400'
          }`}>
            Phase 24
          </span>
        </button>

        <button
          onClick={() => setActiveTab('mold')}
          className={`flex items-center space-x-2 rounded-xl px-4 py-2 text-xs font-black transition-all ${
            activeTab === 'mold'
              ? 'bg-gradient-to-r from-cyan-500 to-blue-600 text-white shadow-md shadow-cyan-500/25'
              : isLight
              ? 'text-slate-600 hover:text-slate-900 hover:bg-slate-200/60'
              : 'text-slate-400 hover:text-white hover:bg-slate-900'
          }`}
        >
          <Compass className="h-4 w-4 text-cyan-300" />
          <span>Mold &amp; Undercut DFM</span>
          <span className={`rounded-full px-2 py-0.5 text-[10px] font-mono font-bold ${
            activeTab === 'mold' ? 'bg-white/20 text-white' : 'bg-cyan-500/10 text-cyan-400'
          }`}>
            Phase 26
          </span>
        </button>

        <button
          onClick={() => setActiveTab('3d')}
          className={`flex items-center space-x-2 rounded-xl px-4 py-2 text-xs font-bold transition-all ${
            activeTab === '3d'
              ? 'bg-cyan-500 text-white shadow-md'
              : isLight
              ? 'text-slate-600 hover:text-slate-900 hover:bg-slate-200/60'
              : 'text-slate-400 hover:text-white hover:bg-slate-900'
          }`}
        >
          <Box className="h-4 w-4" />
          <span>3D B-Rep Viewport</span>
        </button>

        <button
          onClick={() => setActiveTab('2d')}
          className={`flex items-center space-x-2 rounded-xl px-4 py-2 text-xs font-bold transition-all ${
            activeTab === '2d'
              ? 'bg-cyan-500 text-white shadow-md'
              : isLight
              ? 'text-slate-600 hover:text-slate-900 hover:bg-slate-200/60'
              : 'text-slate-400 hover:text-white hover:bg-slate-900'
          }`}
        >
          <FileText className="h-4 w-4" />
          <span>2D TechDraw Sheet</span>
        </button>

        <button
          onClick={() => setActiveTab('features')}
          className={`flex items-center space-x-2 rounded-xl px-4 py-2 text-xs font-bold transition-all ${
            activeTab === 'features'
              ? 'bg-cyan-500 text-white shadow-md'
              : isLight
              ? 'text-slate-600 hover:text-slate-900 hover:bg-slate-200/60'
              : 'text-slate-400 hover:text-white hover:bg-slate-900'
          }`}
        >
          <Layers className="h-4 w-4" />
          <span>Features &amp; Dimensions</span>
        </button>

        <button
          onClick={() => setActiveTab('ai')}
          className={`flex items-center space-x-2 rounded-xl px-4 py-2 text-xs font-bold transition-all ${
            activeTab === 'ai'
              ? 'bg-cyan-500 text-white shadow-md'
              : isLight
              ? 'text-slate-600 hover:text-slate-900 hover:bg-slate-200/60'
              : 'text-slate-400 hover:text-white hover:bg-slate-900'
          }`}
        >
          <Bot className="h-4 w-4" />
          <span>Multimodal AI Review</span>
        </button>

        <button
          onClick={() => setActiveTab('issues')}
          className={`flex items-center space-x-2 rounded-xl px-4 py-2 text-xs font-bold transition-all ${
            activeTab === 'issues'
              ? 'bg-amber-500 text-white shadow-md'
              : isLight
              ? 'text-slate-600 hover:text-slate-900 hover:bg-slate-200/60'
              : 'text-slate-400 hover:text-white hover:bg-slate-900'
          }`}
        >
          <ShieldCheck className="h-4 w-4 text-amber-400" />
          <span>Issues &amp; Approval</span>
          <span className="rounded-full bg-amber-500/20 px-1.5 py-0.2 text-[10px] font-mono text-amber-300">
            {issues.length}
          </span>
        </button>
      </div>

      {/* 3. Tab Contents */}
      <div className="space-y-6">
        {activeTab === 'intelligence' && (
          <EngineeringDesignReviewCockpit
            projectId={projectId}
            data={intelData}
            meshData={meshData}
            summary={analysis || undefined}
            features={features}
            isLoading={isLoading && !intelData}
            onReload={handleFetchIntelData}
            theme={theme}
            onToggleTheme={onToggleTheme}
          />
        )}
        {activeTab === 'mold' && (
          <MoldAnalysisViewer
            projectId={projectId}
            meshData={meshData}
            theme={theme}
          />
        )}
        {activeTab === '3d' && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-2 min-h-[600px] h-[600px] rounded-2xl overflow-hidden border border-slate-200 dark:border-slate-800">
              <Viewer3D
                projectId={projectId}
                meshData={meshData}
                summary={analysis || undefined}
                features={features}
                selectedFeatureId={selectedFeatureId}
                onSelectFeature={setSelectedFeatureId}
                selectedFaceId={selectedFaceId}
                onSelectFace={setSelectedFaceId}
                activeSection={activeSection}
                showSectionPlane={true}
                theme={theme}
              />
            </div>
            <div>
              <FeaturesTable
                features={features}
                selectedFeatureId={selectedFeatureId}
                onSelectFeature={setSelectedFeatureId}
              />
            </div>
          </div>
        )}

        {activeTab === '2d' && (
          <div className="space-y-6">
            <DrawingViewer
              projectId={projectId}
              artifacts={drawing?.artifacts || analysis?.artifacts || []}
              views={drawing?.views_generated || ['Front', 'Top', 'Left', 'Right', 'Bottom']}
              dimensions={dimensions}
              theme={theme}
            />
          </div>
        )}

        {activeTab === 'features' && (
          <div className="space-y-4">
            {/* Sub-Layout Selector */}
            <div className={`flex flex-wrap items-center justify-between gap-3 p-2.5 rounded-xl border backdrop-blur-md transition-colors ${
              theme === 'light'
                ? 'bg-white/95 border-slate-200/90 shadow-sm text-slate-800'
                : 'bg-slate-900/80 border-slate-800 text-slate-300'
            }`}>
              <div className="flex items-center space-x-2 text-xs font-medium">
                <span className={theme === 'light' ? 'text-slate-500 font-semibold' : 'text-slate-400'}>View Mode:</span>
                <div className={`flex items-center space-x-1 p-1 rounded-lg border font-mono ${
                  theme === 'light' ? 'bg-slate-100 border-slate-200' : 'bg-slate-950 border-slate-800'
                }`}>
                  <button
                    onClick={() => setFeaturesSubTab('stacked')}
                    className={`rounded px-2.5 py-1 text-xs font-bold transition-all ${
                      featuresSubTab === 'stacked'
                        ? 'bg-cyan-500 text-white shadow-sm shadow-cyan-500/25'
                        : theme === 'light' ? 'text-slate-600 hover:text-slate-950' : 'text-slate-400 hover:text-white'
                    }`}
                  >
                    Stacked (Full Details)
                  </button>
                  <button
                    onClick={() => setFeaturesSubTab('features')}
                    className={`rounded px-2.5 py-1 text-xs font-bold transition-all ${
                      featuresSubTab === 'features'
                        ? 'bg-cyan-500 text-white shadow-sm shadow-cyan-500/25'
                        : theme === 'light' ? 'text-slate-600 hover:text-slate-950' : 'text-slate-400 hover:text-white'
                    }`}
                  >
                    Features Only ({features.length})
                  </button>
                  <button
                    onClick={() => setFeaturesSubTab('dimensions')}
                    className={`rounded px-2.5 py-1 text-xs font-bold transition-all ${
                      featuresSubTab === 'dimensions'
                        ? 'bg-cyan-500 text-white shadow-sm shadow-cyan-500/25'
                        : theme === 'light' ? 'text-slate-600 hover:text-slate-950' : 'text-slate-400 hover:text-white'
                    }`}
                  >
                    Dimensions Only ({dimensions.length})
                  </button>
                  <button
                    onClick={() => setFeaturesSubTab('split')}
                    className={`rounded px-2.5 py-1 text-xs font-bold transition-all ${
                      featuresSubTab === 'split'
                        ? 'bg-cyan-500 text-white shadow-sm shadow-cyan-500/25'
                        : theme === 'light' ? 'text-slate-600 hover:text-slate-950' : 'text-slate-400 hover:text-white'
                    }`}
                  >
                    Side-by-Side
                  </button>
                </div>
              </div>

              <div className="flex items-center space-x-3 text-xs font-mono">
                <span className="text-cyan-600 dark:text-cyan-300 font-bold">{features.length} Features</span>
                <span className={theme === 'light' ? 'text-slate-300' : 'text-slate-600'}>•</span>
                <span className="text-emerald-600 dark:text-emerald-300 font-bold">{placedDimsCount} Placed Dimensions</span>
                <span className={theme === 'light' ? 'text-slate-300' : 'text-slate-600'}>•</span>
                <span className={theme === 'light' ? 'text-slate-500' : 'text-slate-400'}>100% Deterministic OCCT</span>
              </div>
            </div>

            {/* Layout Rendering */}
            {featuresSubTab === 'stacked' && (
              <div className="space-y-6">
                <FeaturesTable
                  features={features}
                  selectedFeatureId={selectedFeatureId}
                  onSelectFeature={setSelectedFeatureId}
                  theme={theme}
                />
                <DimensionsTable dimensions={dimensions} theme={theme} />
              </div>
            )}

            {featuresSubTab === 'features' && (
              <div className="space-y-6">
                <FeaturesTable
                  features={features}
                  selectedFeatureId={selectedFeatureId}
                  onSelectFeature={setSelectedFeatureId}
                  theme={theme}
                />
              </div>
            )}

            {featuresSubTab === 'dimensions' && (
              <div className="space-y-6">
                <DimensionsTable dimensions={dimensions} theme={theme} />
              </div>
            )}

            {featuresSubTab === 'split' && (
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <FeaturesTable
                  features={features}
                  selectedFeatureId={selectedFeatureId}
                  onSelectFeature={setSelectedFeatureId}
                  theme={theme}
                />
                <DimensionsTable dimensions={dimensions} theme={theme} />
              </div>
            )}
          </div>
        )}

        {activeTab === 'ai' && (
          <div className="space-y-6">
            <AIReviewPanel
              projectId={projectId}
              projectName={fileName}
              dimensions={dimensions}
              placedCount={placedDimsCount}
              totalCandidatesCount={totalCandidatesCount}
              features={features}
              boundingBox={xLen > 0 ? { x_length: xLen, y_length: yLen, z_length: zLen } : undefined}
              consensus={reviewSummary?.consensus}
              claudeReview={aiReview?.provider === 'claude' ? aiReview : null}
              geminiReview={aiReview?.provider === 'gemini' ? aiReview : null}
              issues={issues}
              recommendations={recommendations}
              onRefreshReview={loadAllData}
              onSelectFeature={(featureId) => {
                if (featureId) setSelectedFeatureId(featureId);
              }}
              theme={theme}
            />
          </div>
        )}

        {activeTab === 'issues' && (
          <div className="space-y-6">
            <EngineeringIssuesPanel
              projectId={projectId}
              issues={issues}
              recommendations={recommendations}
              onRefreshIssues={loadAllData}
              theme={theme}
            />
          </div>
        )}
      </div>
    </div>
  );
};
