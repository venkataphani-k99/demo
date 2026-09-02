import React, { useState, useEffect, useMemo } from 'react';
import {
  Loader2,
  AlertCircle,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Compass,
  Layers,
  Box,
  Split,
  MoveRight,
  ShieldAlert,
  ArrowUpRight,
  Sparkles,
  RefreshCw,
  SlidersHorizontal,
  FileText,
  ChevronDown,
  ChevronRight,
  Eye,
  Check,
  Zap,
} from 'lucide-react';
import { Viewer3D, DirectionalArrowProp } from './Viewer3D';
import {
  drawingApi,
  MoldAnalysisResult,
  MoldParameters,
  CandidateDirection,
  FaceDraftInfo,
  UndercutFeature,
  SliderCandidate,
  LifterCandidate,
  PartingCandidate,
} from '../../lib/drawingApi';

interface MoldAnalysisPanelProps {
  projectId: string;
  isStepProject?: boolean;
}

type SubAnalysisMode =
  | '3d'
  | 'draft'
  | 'undercuts'
  | 'parting'
  | 'sliders'
  | 'lifters'
  | 'core_cavity'
  | 'ejection'
  | 'report';

export const MoldAnalysisPanel: React.FC<MoldAnalysisPanelProps> = ({
  projectId,
  isStepProject = false,
}) => {
  const [loading, setLoading] = useState<boolean>(true);
  const [reanalyzing, setReanalyzing] = useState<boolean>(false);
  const [analysis, setAnalysis] = useState<MoldAnalysisResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [activeMode, setActiveMode] = useState<SubAnalysisMode>('3d');

  // Interactive parameters
  const [selectedDirection, setSelectedDirection] = useState<string>('+Z');
  const [minDraftAngle, setMinDraftAngle] = useState<number>(1.0);
  const [selectedUndercutId, setSelectedUndercutId] = useState<string | null>(null);
  const [selectedFaceId, setSelectedFaceId] = useState<string | null>(null);
  const [visibilityFilter, setVisibilityFilter] = useState<'all' | 'cavity' | 'core' | 'parting' | 'sliders'>('all');

  const fetchAnalysis = async (dir?: string, draft?: number) => {
    try {
      if (analysis) setReanalyzing(true);
      else setLoading(true);
      setError(null);

      const targetDir = dir ?? selectedDirection;
      const targetDraft = draft ?? minDraftAngle;

      const res = await drawingApi.getMoldAnalysis(projectId, targetDir, targetDraft);
      setAnalysis(res);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
      setReanalyzing(false);
    }
  };

  useEffect(() => {
    fetchAnalysis();
  }, [projectId]);

  const handleApplyDirection = (dirLabel: string) => {
    setSelectedDirection(dirLabel);
    fetchAnalysis(dirLabel, minDraftAngle);
  };

  const handleApplyMinDraft = (val: number) => {
    setMinDraftAngle(val);
    fetchAnalysis(selectedDirection, val);
  };

  // ---------------------------------------------------------------------------
  // Build Dynamic Three.js Overlays Based on Active Mode
  // ---------------------------------------------------------------------------

  const faceColorMap = useMemo<Record<string, string>>(() => {
    if (!analysis || !analysis.is_valid_brep) return {};
    const map: Record<string, string> = {};

    if (activeMode === 'draft' && analysis.draft_analysis?.faces) {
      for (const f of analysis.draft_analysis.faces) {
        if (f.classification === 'POSITIVE_DRAFT') map[f.face_id] = '#10b981'; // Emerald
        else if (f.classification === 'INSUFFICIENT_DRAFT' || f.classification === 'ZERO_DRAFT') map[f.face_id] = '#f59e0b'; // Amber
        else if (f.classification === 'NEGATIVE_DRAFT') map[f.face_id] = '#ef4444'; // Rose
        else map[f.face_id] = '#64748b';
      }
    } else if (activeMode === 'undercuts' && analysis.undercut_analysis) {
      const uMap = analysis.undercut_analysis.face_classifications || {};
      for (const [fId, cls] of Object.entries(uMap)) {
        if (cls === 'UNDERCUT') map[fId] = '#ef4444'; // Bright Red for undercuts
        else if (cls === 'DIRECTLY_EJECTABLE') map[fId] = '#06b6d4'; // Cyan for directly ejectable
        else map[fId] = '#64748b';
      }
      if (selectedUndercutId) {
        const u = analysis.undercut_analysis.undercuts.find((item) => item.undercut_id === selectedUndercutId);
        if (u) {
          for (const fId of u.face_ids) map[fId] = '#ec4899'; // Vibrant magenta for selected undercut
        }
      }
    } else if (activeMode === 'core_cavity' && analysis.core_cavity_analysis) {
      const cc = analysis.core_cavity_analysis;
      for (const fId of cc.cavity_faces) {
        if (visibilityFilter === 'all' || visibilityFilter === 'cavity') map[fId] = '#3b82f6'; // Blue for Cavity
      }
      for (const fId of cc.core_faces) {
        if (visibilityFilter === 'all' || visibilityFilter === 'core') map[fId] = '#f59e0b'; // Amber for Core
      }
      for (const fId of cc.parting_faces) {
        if (visibilityFilter === 'all' || visibilityFilter === 'parting') map[fId] = '#d946ef'; // Magenta for Parting
      }
      for (const fId of cc.side_action_faces) {
        if (visibilityFilter === 'all' || visibilityFilter === 'sliders') map[fId] = '#8b5cf6'; // Purple for Sliders
      }
    } else if (activeMode === 'sliders' && analysis.slider_analysis?.candidates) {
      for (const s of analysis.slider_analysis.candidates) {
        for (const fId of s.affected_faces) map[fId] = '#8b5cf6'; // Purple
      }
    } else if (activeMode === 'lifters' && analysis.lifter_analysis?.candidates) {
      for (const l of analysis.lifter_analysis.candidates) {
        for (const fId of l.affected_faces) map[fId] = '#ec4899'; // Pink
      }
    } else if (selectedFaceId) {
      map[selectedFaceId] = '#ec4899';
    }

    return map;
  }, [analysis, activeMode, selectedUndercutId, selectedFaceId, visibilityFilter]);

  const directionalArrows = useMemo<DirectionalArrowProp[]>(() => {
    if (!analysis || !analysis.is_valid_brep) return [];
    const arrows: DirectionalArrowProp[] = [];

    // Mold opening arrow
    if (analysis.active_mold_opening_direction) {
      arrows.push({
        direction: analysis.active_mold_opening_direction,
        color: '#10b981',
        label: `Mold Pull ${selectedDirection}`,
      });
    }

    // Slider arrows
    if ((activeMode === 'sliders' || activeMode === 'undercuts') && analysis.slider_analysis?.candidates) {
      for (const s of analysis.slider_analysis.candidates) {
        arrows.push({
          direction: s.withdrawal_direction,
          color: '#8b5cf6',
          label: `${s.slider_id} Pull (${s.required_travel}mm)`,
        });
      }
    }

    // Lifter arrows
    if ((activeMode === 'lifters' || activeMode === 'undercuts') && analysis.lifter_analysis?.candidates) {
      for (const l of analysis.lifter_analysis.candidates) {
        arrows.push({
          origin: l.undercut_geometry_center,
          direction: l.lifter_axis,
          color: '#ec4899',
          label: `${l.lifter_id} Axis (${l.lifter_angle_deg}°)`,
        });
      }
    }

    // Ejection arrow
    if (activeMode === 'ejection' && analysis.ejection_analysis?.ejection_direction) {
      arrows.push({
        direction: analysis.ejection_analysis.ejection_direction,
        color: '#06b6d4',
        label: 'Ejection Vector',
      });
    }

    return arrows;
  }, [analysis, activeMode, selectedDirection]);

  const highlightEdges = useMemo<number[][]>(() => {
    if (!analysis || !analysis.is_valid_brep) return [];
    if (activeMode === 'parting' && analysis.parting_line_analysis?.candidates) {
      const rec = analysis.parting_line_analysis.candidates.find((c) => c.is_recommended) || analysis.parting_line_analysis.candidates[0];
      return rec?.parting_segments || [];
    }
    return [];
  }, [analysis, activeMode]);

  // ---------------------------------------------------------------------------
  // Loading & Error States
  // ---------------------------------------------------------------------------

  if (loading) {
    return (
      <div className="flex min-h-[500px] flex-col items-center justify-center rounded-2xl border border-slate-800 bg-slate-950/80 p-12 text-center shadow-2xl">
        <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-violet-500/10 text-violet-400 border border-violet-500/20 animate-spin mb-4">
          <RefreshCw className="h-8 w-8" />
        </div>
        <h3 className="text-lg font-bold text-white">Analyzing 3D B-Rep Moldability...</h3>
        <p className="mt-1 text-xs text-slate-400 max-w-md font-mono">
          Evaluating geometric face normals, directional reachability, parting silhouette transitions, and side actions.
        </p>
      </div>
    );
  }

  // ---------------------------------------------------------------------------
  // Unavailable State (No Validated B-Rep Exists)
  // ---------------------------------------------------------------------------

  if (error || !analysis || !analysis.is_valid_brep || analysis.status === 'VALIDATION_FAILED') {
    return (
      <div className="rounded-2xl border border-rose-500/40 bg-rose-950/20 p-8 text-center max-w-3xl mx-auto shadow-2xl space-y-4">
        <div className="flex h-16 w-16 items-center justify-center rounded-full bg-rose-500/20 text-rose-400 border border-rose-500/40 mx-auto">
          <ShieldAlert className="h-8 w-8" />
        </div>
        <div className="space-y-1">
          <span className="text-xs font-mono font-bold uppercase tracking-widest text-rose-400">
            Downstream Gate Locked
          </span>
          <h2 className="text-xl font-black text-white">MOLD ANALYSIS UNAVAILABLE</h2>
        </div>
        <p className="text-sm text-rose-200/90 max-w-lg mx-auto leading-relaxed">
          {analysis?.errors?.[0] || error || 'A validated 3D B-Rep model is required before mold analysis.'}
        </p>
        <div className="rounded-xl border border-slate-800 bg-slate-900/80 p-4 text-xs text-slate-400 text-left max-w-md mx-auto font-mono space-y-1">
          <p className="text-slate-300 font-semibold">Architectural Pre-Condition:</p>
          <p>1. Universal 2D→3D reconstruction must complete.</p>
          <p>2. OpenCASCADE solid body must be valid (Volume &gt; 0).</p>
          <p>3. Geometry must match 3D Blueprint artifact hash.</p>
        </div>
        <div className="pt-2">
          <button
            onClick={() => fetchAnalysis()}
            className="px-4 py-2 rounded-lg bg-violet-600 hover:bg-violet-500 text-white text-xs font-bold transition-all shadow-lg inline-flex items-center gap-2"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            Retry Mold Analysis Check
          </button>
        </div>
      </div>
    );
  }

  // ---------------------------------------------------------------------------
  // Status Colors & Badges
  // ---------------------------------------------------------------------------

  const overallStatusColor =
    analysis.overall_moldability === 'MOLDABLE'
      ? 'border-emerald-500/40 bg-emerald-500/10 text-emerald-300'
      : analysis.overall_moldability === 'MOLDABLE WITH SIDE ACTIONS'
      ? 'border-cyan-500/40 bg-cyan-500/10 text-cyan-300'
      : analysis.overall_moldability === 'MOLDABILITY WARNING'
      ? 'border-amber-500/40 bg-amber-500/10 text-amber-300'
      : 'border-rose-500/40 bg-rose-500/10 text-rose-300';

  const meshUrl = isStepProject
    ? `http://127.0.0.1:8000/api/v1/projects/${projectId}/mesh`
    : drawingApi.getMeshUrl(projectId);

  return (
    <div className="space-y-6">
      {/* 1. Header Toolbar & Sub-Mode Navigation */}
      <div className="rounded-2xl border border-slate-800 bg-slate-900/80 p-4 shadow-xl backdrop-blur-md flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-bold text-violet-400 bg-violet-500/10 border border-violet-500/20 px-2 py-0.5 rounded font-mono">
              Phase 21
            </span>
            <span className={`text-xs font-black px-2.5 py-0.5 rounded-md border ${overallStatusColor}`}>
              {analysis.overall_moldability}
            </span>
            {reanalyzing && (
              <span className="text-[11px] text-violet-400 flex items-center gap-1 font-mono animate-pulse">
                <Loader2 className="w-3 h-3 animate-spin" />
                Re-evaluating...
              </span>
            )}
          </div>
          <h2 className="text-lg font-black text-slate-100 flex items-center gap-2">
            <Compass className="w-5 h-5 text-emerald-400" />
            Interactive 3D Moldability Analysis Workspace
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            B-Rep Volume: <span className="font-mono text-slate-200">{analysis.provenance.volume_mm3.toLocaleString()} mm³</span> • Total Faces: <span className="font-mono text-slate-200">{analysis.provenance.total_face_count}</span> • Mold Pull: <span className="font-mono text-emerald-400 font-bold">{selectedDirection}</span>
          </p>
        </div>

        {/* Sub-Mode Buttons */}
        <div className="flex flex-wrap items-center gap-1 bg-slate-950 p-1.5 rounded-xl border border-slate-800 text-xs font-semibold">
          {[
            { id: '3d', label: '3D MODEL' },
            { id: 'draft', label: 'DRAFT' },
            { id: 'undercuts', label: 'UNDERCUTS' },
            { id: 'parting', label: 'PARTING' },
            { id: 'sliders', label: 'SLIDERS' },
            { id: 'lifters', label: 'LIFTERS' },
            { id: 'core_cavity', label: 'CORE/CAVITY' },
            { id: 'ejection', label: 'EJECTION' },
            { id: 'report', label: 'REPORT' },
          ].map((mode) => (
            <button
              key={mode.id}
              onClick={() => setActiveMode(mode.id as SubAnalysisMode)}
              className={`px-3 py-1.5 rounded-lg transition-all ${
                activeMode === mode.id
                  ? 'bg-violet-600 text-white font-bold shadow-lg shadow-violet-600/30'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900'
              }`}
            >
              {mode.label}
            </button>
          ))}
        </div>
      </div>

      {/* 2. Main Workspace (3D Viewport on Left, Analysis Panel on Right) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left: 3D Viewport with Overlays */}
        <div className="lg:col-span-8 flex flex-col space-y-4">
          <div className="rounded-2xl border border-slate-800 bg-slate-950 overflow-hidden shadow-2xl relative h-[560px]">
            <div className="absolute top-3 left-3 z-10 flex items-center gap-2 bg-slate-900/90 border border-slate-800/80 px-3 py-1.5 rounded-lg backdrop-blur-md text-xs font-mono text-slate-300">
              <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse" />
              <span>Mode: <strong className="text-white uppercase">{activeMode}</strong></span>
              <span>•</span>
              <span>Pull: <strong className="text-emerald-400">{selectedDirection}</strong></span>
            </div>

            {/* Sub-mode Color Legend Overlay */}
            <div className="absolute bottom-3 left-3 z-10 bg-slate-900/95 border border-slate-800/90 p-2.5 rounded-xl backdrop-blur-md text-[11px] font-mono space-y-1.5 shadow-xl">
              <span className="text-[10px] text-slate-500 uppercase font-bold tracking-wider block">Legend</span>
              {activeMode === 'draft' && (
                <div className="space-y-1">
                  <div className="flex items-center gap-2"><span className="w-3 h-3 rounded bg-emerald-500" /><span>Positive Draft ({analysis.draft_analysis.pass_percentage}%)</span></div>
                  <div className="flex items-center gap-2"><span className="w-3 h-3 rounded bg-amber-500" /><span>Zero / Insufficient ({analysis.draft_analysis.warning_percentage}%)</span></div>
                  <div className="flex items-center gap-2"><span className="w-3 h-3 rounded bg-rose-500" /><span>Negative / Undercut ({analysis.draft_analysis.fail_percentage}%)</span></div>
                </div>
              )}
              {activeMode === 'undercuts' && (
                <div className="space-y-1">
                  <div className="flex items-center gap-2"><span className="w-3 h-3 rounded bg-rose-500" /><span>Undercut Face (Blocked)</span></div>
                  <div className="flex items-center gap-2"><span className="w-3 h-3 rounded bg-cyan-500" /><span>Directly Ejectable</span></div>
                  <div className="flex items-center gap-2"><span className="w-3 h-3 rounded bg-violet-500" /><span>Side Action Pull Vector</span></div>
                </div>
              )}
              {activeMode === 'parting' && (
                <div className="space-y-1">
                  <div className="flex items-center gap-2"><span className="w-3 h-3 rounded bg-fuchsia-500" /><span>Candidate Parting Line</span></div>
                  <div className="flex items-center gap-2"><span className="w-3 h-3 rounded bg-blue-500" /><span>Cavity Half Faces</span></div>
                  <div className="flex items-center gap-2"><span className="w-3 h-3 rounded bg-amber-500" /><span>Core Half Faces</span></div>
                </div>
              )}
              {activeMode === 'core_cavity' && (
                <div className="space-y-1">
                  <div className="flex items-center gap-2"><span className="w-3 h-3 rounded bg-blue-500" /><span>Cavity Side ({analysis.core_cavity_analysis.cavity_faces.length} faces)</span></div>
                  <div className="flex items-center gap-2"><span className="w-3 h-3 rounded bg-amber-500" /><span>Core Side ({analysis.core_cavity_analysis.core_faces.length} faces)</span></div>
                  <div className="flex items-center gap-2"><span className="w-3 h-3 rounded bg-fuchsia-500" /><span>Parting Region</span></div>
                  <div className="flex items-center gap-2"><span className="w-3 h-3 rounded bg-purple-500" /><span>Side Action Region</span></div>
                </div>
              )}
              {(activeMode === 'sliders' || activeMode === 'lifters' || activeMode === '3d' || activeMode === 'ejection' || activeMode === 'report') && (
                <div className="space-y-1">
                  <div className="flex items-center gap-2"><span className="w-3 h-3 rounded bg-emerald-500" /><span>Mold Opening Direction</span></div>
                  <div className="flex items-center gap-2"><span className="w-3 h-3 rounded bg-purple-500" /><span>Slider Side Actions</span></div>
                  <div className="flex items-center gap-2"><span className="w-3 h-3 rounded bg-pink-500" /><span>Internal Lifter Axes</span></div>
                </div>
              )}
            </div>

            <Viewer3D
              projectId={projectId}
              meshUrl={meshUrl}
              faceColorMap={faceColorMap}
              directionalArrows={directionalArrows}
              highlightEdges={highlightEdges}
              onSelectFace={setSelectedFaceId}
            />
          </div>

          {/* Visibility Controls for Core/Cavity Mode */}
          {activeMode === 'core_cavity' && (
            <div className="flex items-center gap-2 bg-slate-900/80 p-2 rounded-xl border border-slate-800 text-xs">
              <span className="text-slate-500 font-mono px-2">Filter Surfaces:</span>
              {(['all', 'cavity', 'core', 'parting', 'sliders'] as const).map((filter) => (
                <button
                  key={filter}
                  onClick={() => setVisibilityFilter(filter)}
                  className={`px-3 py-1 rounded-lg uppercase font-bold transition-all ${
                    visibilityFilter === filter
                      ? 'bg-violet-600 text-white'
                      : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800'
                  }`}
                >
                  {filter}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Right: Inspection & Analysis Panel */}
        <div className="lg:col-span-4 space-y-4">
          {/* Section A: Mold Opening Direction */}
          <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-4 space-y-3">
            <div className="flex items-center justify-between border-b border-slate-800/80 pb-2">
              <div className="flex items-center gap-2">
                <Compass className="w-4 h-4 text-emerald-400" />
                <span className="text-xs font-bold text-slate-200 uppercase tracking-wider">
                  Mold Opening Direction
                </span>
              </div>
              <span className="text-xs font-mono font-bold text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-2 py-0.5 rounded">
                {selectedDirection}
              </span>
            </div>

            <div className="grid grid-cols-3 gap-1.5">
              {['+Z', '-Z', '+Y', '-Y', '+X', '-X'].map((dir) => (
                <button
                  key={dir}
                  onClick={() => handleApplyDirection(dir)}
                  className={`py-1.5 px-2 rounded-lg text-xs font-mono font-bold border transition-all ${
                    selectedDirection === dir
                      ? 'bg-emerald-600 text-white border-emerald-500 shadow-md'
                      : 'bg-slate-950 border-slate-800 text-slate-400 hover:text-slate-200 hover:bg-slate-900'
                  }`}
                >
                  {dir}
                </button>
              ))}
            </div>

            {/* Candidate Direction Rankings */}
            <div className="space-y-1.5 pt-1">
              <span className="text-[10px] uppercase font-bold text-slate-500 tracking-wider block">
                Ranked Geometric Candidates
              </span>
              <div className="space-y-1 max-h-36 overflow-y-auto pr-1">
                {analysis.candidate_directions.map((cand, idx) => (
                  <div
                    key={cand.direction_id}
                    onClick={() => handleApplyDirection(cand.label)}
                    className={`flex items-center justify-between p-2 rounded-lg border text-xs cursor-pointer transition-all ${
                      selectedDirection === cand.label
                        ? 'border-emerald-500/50 bg-emerald-500/10 text-emerald-300'
                        : 'border-slate-800/60 bg-slate-950/60 text-slate-400 hover:border-slate-700'
                    }`}
                  >
                    <div className="flex items-center gap-2">
                      <span className="font-mono font-bold text-slate-200">{cand.label}</span>
                      <span className="text-[10px] text-slate-500">
                        {cand.undercut_face_count} undercuts
                      </span>
                    </div>
                    <span className="font-mono text-emerald-400 font-bold">
                      {(cand.score * 100).toFixed(0)}% Opt
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Section B: Draft Angle Analysis */}
          <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-4 space-y-3">
            <div className="flex items-center justify-between border-b border-slate-800/80 pb-2">
              <div className="flex items-center gap-2">
                <SlidersHorizontal className="w-4 h-4 text-cyan-400" />
                <span className="text-xs font-bold text-slate-200 uppercase tracking-wider">
                  Draft Angle Requirements
                </span>
              </div>
              <span className="text-xs font-mono text-slate-300">
                Min: <strong className="text-cyan-400">{minDraftAngle}°</strong>
              </span>
            </div>

            {/* Interactive Draft Slider */}
            <div className="space-y-1">
              <div className="flex items-center justify-between text-[11px] text-slate-400">
                <span>Configure Minimum Draft:</span>
                <span className="font-mono font-bold text-cyan-400">{minDraftAngle}°</span>
              </div>
              <input
                type="range"
                min="0.5"
                max="5.0"
                step="0.5"
                value={minDraftAngle}
                onChange={(e) => handleApplyMinDraft(parseFloat(e.target.value))}
                className="w-full accent-cyan-500 cursor-pointer"
              />
            </div>

            {/* Draft Distribution Bar */}
            <div className="space-y-1.5">
              <div className="flex h-2 w-full rounded-full overflow-hidden bg-slate-950">
                <div style={{ width: `${analysis.draft_analysis.pass_percentage}%` }} className="bg-emerald-500" />
                <div style={{ width: `${analysis.draft_analysis.warning_percentage}%` }} className="bg-amber-500" />
                <div style={{ width: `${analysis.draft_analysis.fail_percentage}%` }} className="bg-rose-500" />
              </div>
              <div className="flex items-center justify-between text-[10px] font-mono text-slate-400">
                <span className="text-emerald-400">Pass {analysis.draft_analysis.pass_percentage}%</span>
                <span className="text-amber-400">Warn {analysis.draft_analysis.warning_percentage}%</span>
                <span className="text-rose-400">Fail {analysis.draft_analysis.fail_percentage}%</span>
              </div>
            </div>
          </div>

          {/* Section C: Undercuts & Side Actions Summary */}
          <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-4 space-y-3">
            <div className="flex items-center justify-between border-b border-slate-800/80 pb-2">
              <div className="flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 text-rose-400" />
                <span className="text-xs font-bold text-slate-200 uppercase tracking-wider">
                  Undercuts & Side Actions
                </span>
              </div>
              <span
                className={`text-xs font-mono font-bold px-2 py-0.5 rounded ${
                  analysis.undercut_analysis.total_undercuts > 0
                    ? 'bg-rose-500/10 text-rose-400 border border-rose-500/20'
                    : 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                }`}
              >
                {analysis.undercut_analysis.total_undercuts} Detected
              </span>
            </div>

            <div className="grid grid-cols-2 gap-2 text-center text-xs">
              <div className="rounded-xl border border-slate-800 bg-slate-950 p-2">
                <span className="text-[10px] text-slate-500 block uppercase font-bold">Sliders Required</span>
                <span className="text-base font-black text-purple-400 font-mono">
                  {analysis.slider_analysis.slider_count}
                </span>
              </div>
              <div className="rounded-xl border border-slate-800 bg-slate-950 p-2">
                <span className="text-[10px] text-slate-500 block uppercase font-bold">Lifters Required</span>
                <span className="text-base font-black text-pink-400 font-mono">
                  {analysis.lifter_analysis.lifter_count}
                </span>
              </div>
            </div>

            {/* List of Undercut Features */}
            {analysis.undercut_analysis.undercuts.length > 0 && (
              <div className="space-y-1.5">
                <span className="text-[10px] uppercase font-bold text-slate-500 tracking-wider block">
                  Detected Undercut Regions
                </span>
                <div className="space-y-1 max-h-40 overflow-y-auto pr-1">
                  {analysis.undercut_analysis.undercuts.map((u) => (
                    <div
                      key={u.undercut_id}
                      onClick={() => setSelectedUndercutId(selectedUndercutId === u.undercut_id ? null : u.undercut_id)}
                      className={`p-2.5 rounded-xl border text-xs cursor-pointer transition-all ${
                        selectedUndercutId === u.undercut_id
                          ? 'border-pink-500 bg-pink-500/10 text-pink-200'
                          : 'border-slate-800 bg-slate-950/70 text-slate-300 hover:border-slate-700'
                      }`}
                    >
                      <div className="flex items-center justify-between font-bold mb-1">
                        <span className="font-mono">{u.undercut_id}</span>
                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-purple-500/20 text-purple-300 font-mono">
                          {u.possible_resolution}
                        </span>
                      </div>
                      <p className="text-[11px] text-slate-400 line-clamp-2">{u.evidence}</p>
                      <div className="mt-1 flex items-center justify-between text-[10px] text-slate-500 font-mono">
                        <span>Faces: {u.face_ids.join(', ')}</span>
                        <span>Area: {u.surface_area} mm²</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Section D: Demolding & Ejection Summary */}
          <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-4 space-y-2">
            <div className="flex items-center justify-between border-b border-slate-800/80 pb-2">
              <div className="flex items-center gap-2">
                <Zap className="w-4 h-4 text-cyan-400" />
                <span className="text-xs font-bold text-slate-200 uppercase tracking-wider">
                  Demolding Feasibility
                </span>
              </div>
              <span className="text-xs font-mono font-bold text-cyan-400">
                {analysis.ejection_analysis.status}
              </span>
            </div>
            <p className="text-xs text-slate-300 leading-relaxed font-mono">
              {analysis.ejection_analysis.summary}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};
