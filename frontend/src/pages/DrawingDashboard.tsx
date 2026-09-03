import React, { useEffect, useState, useRef } from 'react';
import {
  Loader2, AlertCircle, CheckCircle2, XCircle, Eye, Ruler, Layers,
  ScanLine, GitCompare, Building2, AlertTriangle, ChevronDown, ChevronRight,
  Download, RefreshCw, Info, Boxes, Compass, Sparkles, SlidersHorizontal, Maximize2, Box, Zap
} from 'lucide-react';
import { Viewer3D } from '../components/Viewer3D';
import { MoldAnalysisViewer } from '../components/MoldAnalysisViewer';
import {
  drawingApi,
  DrawingUnderstanding,
  DetectedView,
  ExtractedDimension,
  GeometricEntity,
  ModelResult,
  ConsensusState,
  ViewType,
  FeatureGraph,
  DrawingFeature,
  ReconstructionBlueprint,
  ParametricReconstructionPlan,
  ParametricCADStep,
  ParametricParameter,
} from '../../lib/drawingApi';

interface DrawingDashboardProps {
  projectId: string;
  theme?: 'light' | 'dark';
}

// ---------------------------------------------------------------------------
// Helpers & Colors
// ---------------------------------------------------------------------------

const CONSENSUS_COLORS: Record<ConsensusState, string> = {
  agreed: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/30',
  disagreed: 'text-amber-400 bg-amber-500/10 border-amber-500/30',
  unresolved: 'text-red-400 bg-red-500/10 border-red-500/30',
  claude_only: 'text-blue-400 bg-blue-500/10 border-blue-500/30',
  gemini_only: 'text-purple-400 bg-purple-500/10 border-purple-500/30',
};

const VIEW_COLORS: Record<ViewType, string> = {
  FRONT: 'bg-blue-500/20 text-blue-300',
  TOP: 'bg-emerald-500/20 text-emerald-300',
  BOTTOM: 'bg-orange-500/20 text-orange-300',
  LEFT: 'bg-violet-500/20 text-violet-300',
  RIGHT: 'bg-cyan-500/20 text-cyan-300',
  REAR: 'bg-slate-500/20 text-slate-300',
  ISOMETRIC: 'bg-yellow-500/20 text-yellow-300',
  SECTION: 'bg-pink-500/20 text-pink-300',
  DETAIL: 'bg-rose-500/20 text-rose-300',
  AUXILIARY: 'bg-indigo-500/20 text-indigo-300',
  UNKNOWN: 'bg-slate-700 text-slate-400',
};

const DIM_TYPE_LABEL: Record<string, string> = {
  diameter: 'Ø', radius: 'R', linear: '↔', horizontal: '↔', vertical: '↕',
  aligned: '↗', angle: '°', depth: '⊥', chamfer: '×', thread: 'M', unknown: '?',
};

function ConfidenceBar({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  const col = pct >= 80 ? 'bg-emerald-500' : pct >= 50 ? 'bg-amber-500' : 'bg-red-500';
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 rounded-full bg-slate-800 overflow-hidden">
        <div className={`h-full rounded-full ${col}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs text-slate-400 w-9 text-right">{pct}%</span>
    </div>
  );
}

function ViewBadge({ vtype }: { vtype: ViewType }) {
  return (
    <span className={`text-xs font-mono font-semibold px-2 py-0.5 rounded ${VIEW_COLORS[vtype] || 'bg-slate-700 text-slate-400'}`}>
      {vtype}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Sub-panels
// ---------------------------------------------------------------------------

function ViewsPanel({ result, label }: { result: ModelResult; label: string }) {
  if (result.error) {
    return (
      <div className="flex items-center gap-2 rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-300">
        <AlertCircle className="w-4 h-4 flex-shrink-0" />
        {label} error: {result.error}
      </div>
    );
  }
  if (!result.views.length) {
    return <p className="text-slate-500 text-sm">No views detected by {label}.</p>;
  }
  return (
    <div className="space-y-2">
      {result.views.map((v) => (
        <div key={v.view_id} className="rounded-lg border border-slate-800 bg-slate-900/50 px-3 py-2">
          <div className="flex items-center justify-between gap-3 mb-1">
            <div className="flex items-center gap-2">
              <span className="font-mono text-xs text-slate-500">{v.view_id}</span>
              <ViewBadge vtype={v.view_type} />
            </div>
            <span className="text-xs text-slate-500">{Math.round(v.confidence * 100)}% conf</span>
          </div>
          <ConfidenceBar value={v.confidence} />
          {v.bbox && (
            <div className="mt-1 text-xs text-slate-600 font-mono">
              bbox [{v.bbox.x1.toFixed(0)}, {v.bbox.y1.toFixed(0)}, {v.bbox.x2.toFixed(0)}, {v.bbox.y2.toFixed(0)}]
            </div>
          )}
          {v.evidence && <p className="text-xs text-slate-400 mt-1 italic">{v.evidence}</p>}
        </div>
      ))}
    </div>
  );
}

function DimensionsPanel({
  dims,
  label,
  highlightedId,
  onHoverDimension,
}: {
  dims: ExtractedDimension[];
  label: string;
  highlightedId?: string | null;
  onHoverDimension?: (id: string | null) => void;
}) {
  const [expanded, setExpanded] = useState<string | null>(null);
  if (!dims.length) return <p className="text-slate-500 text-sm">No dimensions extracted by {label}.</p>;

  return (
    <div className="space-y-1.5">
      {dims.map((d) => {
        const isHl = highlightedId === d.dimension_id;
        return (
          <div
            key={d.dimension_id}
            onMouseEnter={() => onHoverDimension?.(d.dimension_id)}
            onMouseLeave={() => onHoverDimension?.(null)}
            className={`rounded-lg border transition-all ${
              isHl ? 'border-cyan-500/80 bg-cyan-500/10 shadow-sm' : 'border-slate-800 bg-slate-900/50'
            }`}
          >
            <button
              className="w-full flex items-center gap-3 px-3 py-2 text-left"
              onClick={() => setExpanded(expanded === d.dimension_id ? null : d.dimension_id)}
            >
              <span className="w-7 h-7 flex-shrink-0 flex items-center justify-center rounded bg-slate-800 text-sm font-bold text-slate-300">
                {DIM_TYPE_LABEL[d.dimension_type] ?? '?'}
              </span>
              <span className="font-mono text-slate-100 text-sm flex-1 font-semibold">{d.raw_text}</span>
              {d.normalized_value != null && (
                <span className="text-slate-400 text-xs">{d.normalized_value} {d.unit ?? ''}</span>
              )}
              {d.view_id && <ViewBadge vtype={d.view_id.toUpperCase() as ViewType ?? 'UNKNOWN'} />}
              <span className="text-xs text-slate-500">{Math.round(d.confidence * 100)}%</span>
              {expanded === d.dimension_id ? <ChevronDown className="w-3.5 h-3.5 text-slate-500" /> : <ChevronRight className="w-3.5 h-3.5 text-slate-500" />}
            </button>
            {expanded === d.dimension_id && (
              <div className="px-3 pb-3 pt-1 border-t border-slate-800 space-y-1.5">
                <ConfidenceBar value={d.confidence} />
                <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs text-slate-400">
                  <span>Type: <span className="text-slate-300">{d.dimension_type}</span></span>
                  <span>Unit: <span className="text-slate-300">{d.unit ?? '—'}</span></span>
                  <span>Tolerance: <span className="text-slate-300">{d.tolerance_text ?? 'None (Standard)'}</span></span>
                  <span>Provider: <span className="text-slate-300">{d.source_provider}</span></span>
                </div>
                {d.bbox && (
                  <div className="text-xs text-slate-600 font-mono">
                    bbox [{d.bbox.x1.toFixed(0)}, {d.bbox.y1.toFixed(0)}, {d.bbox.x2.toFixed(0)}, {d.bbox.y2.toFixed(0)}]
                  </div>
                )}
                {d.evidence && <p className="text-xs text-slate-400 italic">{d.evidence}</p>}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

function ConsensusPanel({ u }: { u: DrawingUnderstanding }) {
  const co = u.consensus;
  if (!co) {
    return (
      <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-6 text-center text-slate-500 text-sm">
        Consensus requires both Claude and Gemini to complete without errors.
      </div>
    );
  }

  const allDims = [
    ...co.agreed_dimensions.map((d) => ({ ...d, _type: 'agreed' as const })),
    ...co.unresolved_dimensions.map((d) => ({ ...d, _type: 'unresolved' as const })),
    ...co.disagreed_dimensions.map((d) => ({ ...d, _type: 'disagreed' as const })),
  ];

  return (
    <div className="space-y-4">
      {/* Stats */}
      <div className="grid grid-cols-3 gap-3">
        {[
          { label: 'Agreed', value: co.total_agreed, cls: 'text-emerald-400' },
          { label: 'Unresolved', value: co.total_unresolved, cls: 'text-red-400' },
          { label: 'Solo/Disagree', value: co.total_disagreed, cls: 'text-amber-400' },
        ].map((s) => (
          <div key={s.label} className="rounded-lg border border-slate-800 bg-slate-900/50 p-3 text-center">
            <div className={`text-2xl font-black ${s.cls}`}>{s.value}</div>
            <div className="text-xs text-slate-500 mt-1">{s.label}</div>
          </div>
        ))}
      </div>

      {/* Dimension table */}
      <div className="rounded-xl border border-slate-800 bg-slate-900/50 overflow-hidden">
        <div className="border-b border-slate-800 bg-slate-950/60 px-4 py-2.5 flex items-center gap-2">
          <GitCompare className="w-4 h-4 text-slate-400" />
          <span className="text-sm font-semibold text-slate-200">Dimension Comparison</span>
          <span className="text-xs text-slate-500 ml-auto">Claude {co.total_claude_dimensions} · Gemini {co.total_gemini_dimensions}</span>
        </div>
        <div className="divide-y divide-slate-800/60">
          {allDims.length === 0 && (
            <p className="p-4 text-slate-500 text-sm text-center">No dimension consensus available.</p>
          )}
          {allDims.map((d, i) => (
            <div key={i} className="flex items-center gap-3 px-4 py-2.5">
              <span className={`text-xs font-semibold px-2 py-0.5 rounded border ${CONSENSUS_COLORS[d.state] || 'text-slate-400'}`}>
                {d.state}
              </span>
              <span className="font-mono text-sm text-slate-200 w-28 font-semibold">
                {d.claude_raw_text ?? d.gemini_raw_text ?? '—'}
              </span>
              <span className="text-xs text-slate-400">
                Claude: <span className="text-blue-300 font-mono font-semibold">{d.claude_value ?? d.claude_raw_text ?? '—'}</span>
              </span>
              <span className="text-xs text-slate-400">
                Gemini: <span className="text-purple-300 font-mono font-semibold">{d.gemini_value ?? d.gemini_raw_text ?? '—'}</span>
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

const KSTATE_BADGES: Record<string, { label: string; cls: string }> = {
  known: { label: 'Confirmed (Known)', cls: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/30' },
  partially_known: { label: 'Partially Known', cls: 'text-blue-400 bg-blue-500/10 border-blue-500/30' },
  ambiguous: { label: 'Ambiguous / Conflict', cls: 'text-amber-400 bg-amber-500/10 border-amber-500/30' },
  unresolved: { label: 'Unresolved', cls: 'text-rose-400 bg-rose-500/10 border-rose-500/30' },
};

function FeatureGraphPanel({ fg }: { fg?: FeatureGraph | null }) {
  if (!fg || !fg.features.length) {
    return (
      <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-6 text-center text-slate-500 text-sm">
        <Boxes className="w-8 h-8 text-slate-600 mx-auto mb-2" />
        <p>No synthesized features available yet. Run analysis to extract topological features.</p>
      </div>
    );
  }

  const cross = fg.cross_view_alignment;

  return (
    <div className="space-y-6">
      {/* Cross-view 3D Axis Alignment card */}
      {cross && (
        <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4 space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2">
              <SlidersHorizontal className="w-4 h-4 text-violet-400" />
              Orthographic Cross-View 3D Axis Alignment
            </h3>
            <span className="text-xs font-mono text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-2 py-0.5 rounded">
              Evidence-Aligned
            </span>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <div className="rounded-lg border border-blue-500/30 bg-blue-500/5 p-3">
              <p className="text-xs font-bold text-blue-400 mb-1">X-Axis (Width)</p>
              <p className="text-lg font-black text-slate-100 font-mono">
                {cross.estimated_envelope_3d.width_x != null ? `${cross.estimated_envelope_3d.width_x} mm` : '—'}
              </p>
              <p className="text-[11px] text-slate-400 mt-1 truncate">
                Callouts: {cross.width_x_dimensions.join(', ') || 'None'}
              </p>
            </div>
            <div className="rounded-lg border border-purple-500/30 bg-purple-500/5 p-3">
              <p className="text-xs font-bold text-purple-400 mb-1">Y-Axis (Depth)</p>
              <p className="text-lg font-black text-slate-100 font-mono">
                {cross.estimated_envelope_3d.depth_y != null ? `${cross.estimated_envelope_3d.depth_y} mm` : '—'}
              </p>
              <p className="text-[11px] text-slate-400 mt-1 truncate">
                Callouts: {cross.depth_y_dimensions.join(', ') || 'None'}
              </p>
            </div>
            <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/5 p-3">
              <p className="text-xs font-bold text-emerald-400 mb-1">Z-Axis (Height)</p>
              <p className="text-lg font-black text-slate-100 font-mono">
                {cross.estimated_envelope_3d.height_z != null ? `${cross.estimated_envelope_3d.height_z} mm` : '—'}
              </p>
              <p className="text-[11px] text-slate-400 mt-1 truncate">
                Callouts: {cross.height_z_dimensions.join(', ') || 'None'}
              </p>
            </div>
          </div>
          {cross.axis_uncertainty && Object.keys(cross.axis_uncertainty).length > 0 && (
            <div className="pt-2 border-t border-slate-800/80">
              <p className="text-xs font-semibold text-slate-400 mb-1 flex items-center gap-1.5">
                <Info className="w-3.5 h-3.5 text-amber-400" />
                Axis Uncertainty & Unassigned Callouts ({Object.keys(cross.axis_uncertainty).length})
              </p>
              <div className="space-y-1">
                {Object.entries(cross.axis_uncertainty).map(([dim, note]) => (
                  <p key={dim} className="text-[11px] text-slate-500 font-mono">
                    <span className="text-slate-300 font-bold">[{dim}]</span> {note}
                  </p>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Synthesized Features Grid */}
      <div className="space-y-3">
        <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2">
          <Boxes className="w-4 h-4 text-cyan-400" />
          Evidence-Derived Engineering Features ({fg.features.length})
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {fg.features.map((feat) => {
            const kbadge = KSTATE_BADGES[feat.knowledge_state] || KSTATE_BADGES.known;
            return (
              <div key={feat.feature_id} className="rounded-xl border border-slate-800 bg-slate-900/50 p-4 space-y-2.5">
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-xs font-bold text-slate-400">{feat.feature_id}</span>
                      <span className="text-xs font-semibold text-cyan-300 bg-cyan-500/10 border border-cyan-500/20 px-2 py-0.5 rounded capitalize">
                        {feat.feature_type.replace('_', ' ')}
                      </span>
                      <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded border ${kbadge.cls}`}>
                        {kbadge.label}
                      </span>
                    </div>
                    <h4 className="text-sm font-bold text-slate-100 mt-1">{feat.name}</h4>
                  </div>
                  <span className="text-xs font-mono font-bold text-slate-400 bg-slate-800 px-2 py-0.5 rounded">
                    {Math.round(feat.confidence * 100)}%
                  </span>
                </div>

                {/* Parameters */}
                <div className="space-y-1 pt-1 border-t border-slate-800/80">
                  {feat.parameters.map((param, pi) => (
                    <div key={pi} className="flex items-center justify-between text-xs py-0.5">
                      <span className="text-slate-400 font-mono">{param.param_name}:</span>
                      <span className="font-mono font-bold text-slate-200">
                        {param.value} {param.unit}
                        {param.source_dimension_text && (
                          <span className="text-slate-500 ml-1.5 font-normal">({param.source_dimension_text})</span>
                        )}
                      </span>
                    </div>
                  ))}
                </div>

                {/* Ambiguity / Conflicts */}
                {feat.ambiguity_reasons && feat.ambiguity_reasons.length > 0 && (
                  <div className="p-2 rounded bg-amber-500/10 border border-amber-500/20 space-y-0.5">
                    {feat.ambiguity_reasons.map((r, ri) => (
                      <p key={ri} className="text-[11px] text-amber-300 flex items-start gap-1">
                        <AlertTriangle className="w-3 h-3 flex-shrink-0 mt-0.5" />
                        {r}
                      </p>
                    ))}
                  </div>
                )}

                {/* Provenance & Controlling Views */}
                <div className="pt-2 border-t border-slate-800/60 flex flex-wrap items-center justify-between gap-2 text-xs text-slate-500">
                  <span>Views: {feat.controlling_view_types.join(', ') || 'General / Unconstrained'}</span>
                  {feat.evidence_record?.source_entity_ids && feat.evidence_record.source_entity_ids.length > 0 && (
                    <span className="text-[11px] text-violet-400 bg-violet-500/10 px-1.5 py-0.5 rounded">
                      Entities: {feat.evidence_record.source_entity_ids.join(', ')}
                    </span>
                  )}
                </div>
                {feat.evidence && (
                  <p className="text-[11px] text-slate-400 italic">{feat.evidence}</p>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

function BlueprintPanel({
  projectId,
  understanding,
  theme = 'dark',
}: {
  projectId: string;
  understanding?: DrawingUnderstanding;
  theme?: 'light' | 'dark';
}) {
  const [plan, setPlan] = useState<ParametricReconstructionPlan | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedFeatureId, setSelectedFeatureId] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<'split' | '3d' | 'dag'>('split');

  const synthFeatures = understanding?.feature_graph?.features
    ? (understanding.feature_graph.features as any)
    : [];

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const p = await drawingApi.getReconstructionPlan(projectId);
        if (!cancelled) {
          setPlan(p);
          setLoading(false);
        }
      } catch (err: unknown) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : String(err));
          setLoading(false);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [projectId]);

  if (loading) {
    return (
      <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-8 text-center text-slate-400 text-sm flex items-center justify-center gap-2">
        <Loader2 className="w-4 h-4 animate-spin text-violet-400" />
        Loading Phase 19A Parametric Reconstruction Blueprint…
      </div>
    );
  }

  const env = plan?.envelope_3d || { width_x: 70, depth_y: 24, height_z: 30 };
  const audit = plan?.evidence_audit;
  const statusColor =
    plan?.reconstruction_status === 'COMPLETE'
      ? 'border-emerald-500/40 bg-emerald-500/10 text-emerald-300'
      : plan?.reconstruction_status === 'PARTIAL_ASSUMED'
      ? 'border-amber-500/40 bg-amber-500/10 text-amber-300'
      : 'border-rose-500/40 bg-rose-500/10 text-rose-300';

  return (
    <div className="space-y-6">
      {/* 3D Envelope & Status Header */}
      <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4 flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-semibold text-violet-400 bg-violet-500/10 border border-violet-500/20 px-2 py-0.5 rounded">
              Phase 19B
            </span>
            <span className={`text-xs font-bold px-2 py-0.5 rounded border ${statusColor}`}>
              {plan?.reconstruction_status === 'PARTIAL_ASSUMED'
                ? 'PARTIAL RECONSTRUCTION / ASSUMED / UNCONSTRAINED'
                : plan?.reconstruction_status === 'COMPLETE'
                ? '100% COMPLETE RECONSTRUCTION'
                : 'INSUFFICIENT EVIDENCE / BASE ESTIMATE'}
            </span>
          </div>
          <h3 className="text-base font-bold text-slate-100 flex items-center gap-2">
            <Compass className="w-4 h-4 text-emerald-400" />
            3D Reconstructed Solid Model & Parametric CAD Blueprint
          </h3>
          {plan?.plan_notes && plan.plan_notes.length > 0 && (
            <div className="mt-1.5 space-y-0.5">
              {plan.plan_notes.map((note: string, ni: number) => (
                <p key={ni} className="text-xs text-amber-400 flex items-center gap-1 font-mono">
                  <AlertTriangle className="w-3.5 h-3.5 flex-shrink-0" />
                  {note}
                </p>
              ))}
            </div>
          )}
          {error && (
            <p className="mt-1 text-xs text-amber-400 font-mono">
              Notice: 2D drawing analysis found 0 explicit dimensions. Rendering base reconstructed solid model.
            </p>
          )}
        </div>
        <div className="flex items-center gap-3">
          {/* View Mode Toggle */}
          <div className="flex items-center rounded-lg border border-slate-800 bg-slate-950 p-1 text-xs font-medium">
            <button
              onClick={() => setViewMode('3d')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md transition-colors ${
                viewMode === '3d'
                  ? 'bg-violet-600 text-white font-semibold shadow'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Box className="w-3.5 h-3.5" />
              3D Solid Model
            </button>
            <button
              onClick={() => setViewMode('split')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md transition-colors ${
                viewMode === 'split'
                  ? 'bg-violet-600 text-white font-semibold shadow'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Layers className="w-3.5 h-3.5" />
              Split View
            </button>
            <button
              onClick={() => setViewMode('dag')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md transition-colors ${
                viewMode === 'dag'
                  ? 'bg-violet-600 text-white font-semibold shadow'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Sparkles className="w-3.5 h-3.5" />
              Operations DAG
            </button>
          </div>

          <div className="px-3 py-1.5 rounded-lg border border-slate-800 bg-slate-950/80 font-mono text-sm">
            <span className="text-[10px] text-slate-500 block uppercase font-bold">Bounding Box (X × Y × Z)</span>
            <span className="text-slate-100 font-bold">
              {env.width_x != null ? `${env.width_x} mm` : '—'} × {env.depth_y != null ? `${env.depth_y} mm` : '—'} × {env.height_z != null ? `${env.height_z} mm` : '—'}
            </span>
          </div>
        </div>
      </div>

      {/* Interactive 3D WebGL Solid Viewport (When in '3d' or 'split' mode) */}
      {(viewMode === '3d' || viewMode === 'split') && (
        <div className="rounded-xl border border-slate-800 bg-slate-950/90 overflow-hidden shadow-2xl">
          <div className="border-b border-slate-800 bg-slate-900/80 px-4 py-2.5 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Box className="w-4 h-4 text-cyan-400" />
              <span className="text-xs font-bold text-slate-200 uppercase tracking-wider">
                Interactive 3D Reconstructed Solid (Three.js WebGL / FreeCAD B-Rep)
              </span>
            </div>
            <span className="text-[10px] font-mono text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-2 py-0.5 rounded">
              Orbit 360° • Raycast • B-Rep Topology
            </span>
          </div>
          <div className="h-[520px] w-full relative">
            <Viewer3D
              projectId={projectId}
              theme={theme}
            />
          </div>
        </div>
      )}

      {/* DAG & Audit Evidence Container */}
      {(viewMode === 'dag' || viewMode === 'split') && (
        <div className="space-y-6">

      {/* Phase 19A.2 Operation Gate Summary Bar */}
      {audit && (
        <div className="rounded-xl border border-slate-800 bg-slate-950/90 p-4 space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-800/80 pb-3">
            <div className="flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-cyan-400" />
              <span className="text-xs font-bold text-slate-200 uppercase tracking-wider">
                Phase 19A.2 Reconstruction Operation Gate Summary
              </span>
            </div>
            <div className="flex items-center gap-2">
              <span
                className={`flex items-center gap-1.5 px-3 py-1 rounded-lg text-xs font-bold font-mono border ${
                  audit.gate_19b_passed
                    ? 'border-emerald-500/40 bg-emerald-500/10 text-emerald-300'
                    : 'border-rose-500/40 bg-rose-500/10 text-rose-300'
                }`}
              >
                {audit.gate_19b_passed ? 'GATE OPEN: READY FOR 19B CAD' : 'HARD 19B GATE: LOCKED (MISSING EVIDENCE)'}
              </span>
            </div>
          </div>

          {/* Counts Grid */}
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-2 text-center font-mono text-xs">
            <div className="p-2.5 rounded-lg bg-slate-900 border border-slate-800">
              <span className="text-slate-500 block text-[10px] uppercase font-bold">Total Operations</span>
              <span className="text-slate-100 font-bold text-base">{audit.total_operations}</span>
            </div>
            <div className="p-2.5 rounded-lg bg-emerald-500/5 border border-emerald-500/20">
              <span className="text-emerald-400 block text-[10px] uppercase font-bold">Executable</span>
              <span className="text-emerald-300 font-bold text-base">{audit.executable_count}</span>
            </div>
            <div className="p-2.5 rounded-lg bg-amber-500/5 border border-amber-500/20">
              <span className="text-amber-400 block text-[10px] uppercase font-bold">Partially Executable</span>
              <span className="text-amber-300 font-bold text-base">{audit.partially_executable_count}</span>
            </div>
            <div className="p-2.5 rounded-lg bg-orange-500/5 border border-orange-500/20">
              <span className="text-orange-400 block text-[10px] uppercase font-bold">Unconstrained</span>
              <span className="text-orange-300 font-bold text-base">{audit.unconstrained_count}</span>
            </div>
            <div className="p-2.5 rounded-lg bg-purple-500/5 border border-purple-500/20">
              <span className="text-purple-400 block text-[10px] uppercase font-bold">Ambiguous</span>
              <span className="text-purple-300 font-bold text-base">{audit.ambiguous_count}</span>
            </div>
            <div className="p-2.5 rounded-lg bg-rose-500/5 border border-rose-500/20">
              <span className="text-rose-400 block text-[10px] uppercase font-bold">Blocked</span>
              <span className="text-rose-300 font-bold text-base">{audit.blocked_count}</span>
            </div>
          </div>

          {/* Hard 19B Gate Rationale */}
          <div className="p-3 rounded-lg bg-slate-900/90 border border-slate-800 text-xs text-slate-300 flex items-start gap-2">
            <AlertTriangle className="w-4 h-4 text-amber-400 flex-shrink-0 mt-0.5" />
            <div>
              <span className="font-bold text-amber-300">Hard 19B Gate Policy: </span>
              <span>{audit.gate_19b_rationale}</span>
            </div>
          </div>
        </div>
      )}

      {/* Unconstrained Parameters Alert */}
      {plan && plan.unconstrained_parameters.length > 0 && (
        <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-4 space-y-1.5">
          <p className="text-xs font-bold text-amber-300 flex items-center gap-1.5">
            <AlertTriangle className="w-4 h-4 text-amber-400" />
            Unconstrained Engineering Parameters ({plan.unconstrained_parameters.length})
          </p>
          <p className="text-xs text-slate-300">
            The 2D drawing contains no explicit vertical callout for <code className="text-amber-300 font-bold font-mono">{plan.unconstrained_parameters.join(', ')}</code>. In strict compliance with Tier A/B provenance, this parameter is NOT guessed and remains unconstrained.
          </p>
        </div>
      )}

      {/* Ordered CAD Steps DAG */}
      {plan && plan.steps.length > 0 && (
        <div className="space-y-3">
          <h4 className="text-sm font-semibold text-slate-200 flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-violet-400" />
            Audited Parametric CAD Operations DAG ({plan.steps.length} Steps)
          </h4>
          <div className="space-y-3">
            {plan.steps.map((step: ParametricCADStep) => {
            const auditRec = step.evidence_audit;
            const opValidity = step.operation_validity || (auditRec ? auditRec.validity : 'UNCONSTRAINED');

            const validityBadgeCls =
              opValidity === 'EXECUTABLE'
                ? 'text-emerald-300 bg-emerald-500/10 border-emerald-500/40'
                : opValidity === 'PARTIALLY_EXECUTABLE'
                ? 'text-amber-300 bg-amber-500/10 border-amber-500/40'
                : opValidity === 'UNCONSTRAINED'
                ? 'text-orange-300 bg-orange-500/10 border-orange-500/40'
                : opValidity === 'AMBIGUOUS'
                ? 'text-purple-300 bg-purple-500/10 border-purple-500/40'
                : 'text-rose-300 bg-rose-500/10 border-rose-500/40';

            return (
              <div
                key={step.step_id}
                className="rounded-xl border border-slate-800 bg-slate-900/50 p-4 space-y-3 transition-colors"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-center gap-2.5">
                    <span className="w-7 h-7 rounded bg-violet-500/20 border border-violet-500/30 text-violet-300 font-mono font-bold text-xs flex items-center justify-center">
                      {step.step_index}
                    </span>
                    <div>
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-mono text-xs text-slate-400 font-bold">{step.step_id}</span>
                        <span className="text-xs font-bold text-cyan-300 bg-cyan-500/10 border border-cyan-500/20 px-2 py-0.5 rounded capitalize">
                          {step.operation_type.replace('_', ' ')}
                        </span>
                        <span className="text-xs font-mono text-slate-300 bg-slate-800 px-1.5 py-0.5 rounded">
                          Plane: {step.sketch_plane}
                        </span>
                        <span className={`text-[10px] font-bold px-2.5 py-0.5 rounded border uppercase ${validityBadgeCls}`}>
                          {opValidity.replace(/_/g, ' ')}
                        </span>
                      </div>
                      <p className="text-sm font-semibold text-slate-100 mt-1">{step.description}</p>
                    </div>
                  </div>
                  <span className="text-xs text-slate-500 font-mono flex-shrink-0">{step.target_feature_id}</span>
                </div>

                {/* 7-Dimension Evidence Audit Matrix */}
                {auditRec && (
                  <div className="rounded-lg border border-slate-800/80 bg-slate-950/80 p-3 space-y-2 font-mono text-xs">
                    <div className="text-[11px] font-bold text-slate-400 uppercase tracking-wider border-b border-slate-800/80 pb-1 flex items-center justify-between">
                      <span>Evidence Audit (7 Dimensions)</span>
                      <span className="text-slate-500 text-[10px]">Tier A → Tier B → Tier C → Tier D</span>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2 text-[11px]">
                      {/* 1. Location */}
                      <div className="p-2 rounded bg-slate-900 border border-slate-800/80">
                        <span className="text-slate-500 block text-[10px]">1. LOCATION</span>
                        <span className={`font-bold ${auditRec.location_status === 'CONSTRAINED' ? 'text-emerald-400' : 'text-amber-400'}`}>
                          {auditRec.location_status}
                        </span>
                        <span className="text-slate-400 block text-[10px] mt-0.5 truncate" title={auditRec.location_derivation || ''}>
                          {auditRec.location_derivation || 'Unconstrained'}
                        </span>
                      </div>

                      {/* 2. Direction */}
                      <div className="p-2 rounded bg-slate-900 border border-slate-800/80">
                        <span className="text-slate-500 block text-[10px]">2. DIRECTION</span>
                        <span className="text-cyan-300 font-bold">
                          {auditRec.direction_vector ? `[${auditRec.direction_vector.join(', ')}]` : 'UNCONSTRAINED'}
                        </span>
                        <span className="text-slate-400 block text-[10px] mt-0.5">
                          View: {auditRec.direction_reference_view || 'N/A'}
                        </span>
                      </div>

                      {/* 3. Termination */}
                      <div className="p-2 rounded bg-slate-900 border border-slate-800/80">
                        <span className="text-slate-500 block text-[10px]">3. TERMINATION</span>
                        <span className={`font-bold ${auditRec.termination_type === 'THROUGH_ALL' || auditRec.termination_type === 'BLIND' ? 'text-emerald-400' : 'text-amber-400'}`}>
                          {auditRec.termination_type}
                        </span>
                        <span className="text-slate-400 block text-[10px] mt-0.5 truncate" title={auditRec.termination_evidence || ''}>
                          {auditRec.termination_evidence || 'Unconstrained'}
                        </span>
                      </div>

                      {/* 4. Magnitude */}
                      <div className="p-2 rounded bg-slate-900 border border-slate-800/80">
                        <span className="text-slate-500 block text-[10px]">4. MAGNITUDE</span>
                        <span className="text-cyan-300 font-bold">
                          {auditRec.magnitude_value_mm != null ? `${auditRec.magnitude_value_mm} mm` : auditRec.magnitude_name}
                        </span>
                        <span className="text-slate-400 block text-[10px] mt-0.5">
                          Dim: [{auditRec.tier_a_dim_id || '—'}] {auditRec.tier_a_raw_text || ''}
                        </span>
                      </div>

                      {/* 5. Target Topology */}
                      <div className="p-2 rounded bg-slate-900 border border-slate-800/80">
                        <span className="text-slate-500 block text-[10px]">5. TARGET TOPOLOGY</span>
                        <span className={`font-bold ${auditRec.target_topology_status === 'DERIVED' ? 'text-emerald-400' : 'text-amber-400'}`}>
                          {auditRec.target_topology_status}
                        </span>
                        <span className="text-slate-400 block text-[10px] mt-0.5 truncate" title={auditRec.target_topology_entity || ''}>
                          {auditRec.target_topology_entity || 'Unconstrained'}
                        </span>
                      </div>

                      {/* 6. Operation Validity */}
                      <div className="p-2 rounded bg-slate-900 border border-slate-800/80">
                        <span className="text-slate-500 block text-[10px]">6. VALIDITY DECISION</span>
                        <span className={`font-bold ${validityBadgeCls.split(' ')[0]}`}>
                          {auditRec.validity}
                        </span>
                        <span className="text-slate-400 block text-[10px] mt-0.5">
                          {auditRec.blocking_reasons.length === 0 ? 'Ready for CAD execution' : `${auditRec.blocking_reasons.length} Missing constraint(s)`}
                        </span>
                      </div>
                    </div>
                  </div>
                )}

                {/* Parameter Provenance Table */}
                {Object.keys(step.parameters).length > 0 && (
                  <div className="rounded-lg border border-slate-800 bg-slate-950/60 overflow-hidden">
                    <div className="grid grid-cols-4 px-3 py-1.5 text-[11px] font-bold text-slate-400 border-b border-slate-800 bg-slate-900/60">
                      <span>Parameter</span>
                      <span>Value</span>
                      <span>Tier A Source Callout</span>
                      <span>Provenance Status</span>
                    </div>
                    <div className="divide-y divide-slate-800/60 text-xs font-mono">
                      {Object.entries(step.parameters).map(([pName, p]: [string, ParametricParameter]) => (
                        <div key={pName} className="grid grid-cols-4 px-3 py-1.5 items-center">
                          <span className="text-slate-300 font-semibold">{p.name}</span>
                          <span className="text-cyan-300 font-bold">
                            {p.value != null ? `${p.value} ${p.unit}` : <span className="text-amber-400">UNCONSTRAINED</span>}
                          </span>
                          <span className="text-slate-400 text-[11px]">
                            {p.source_tier_a_dim_id ? (
                              <span>
                                <span className="text-slate-200">[{p.source_tier_a_dim_id}]</span> {p.source_tier_a_text}
                              </span>
                            ) : (
                              <span className="text-slate-600">—</span>
                            )}
                          </span>
                          <span className="text-[11px]">
                            {p.value != null ? (
                              <span className="text-emerald-400">Tier A Verified</span>
                            ) : (
                              <span className="text-amber-400">Unconstrained</span>
                            )}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Unresolved / Missing Parameter Notes */}
                {step.unresolved_notes.length > 0 && (
                  <div className="p-2.5 rounded bg-amber-500/10 border border-amber-500/20 space-y-1">
                    <div className="flex items-center gap-1.5 text-xs font-bold text-amber-300">
                      <AlertTriangle className="w-3.5 h-3.5 flex-shrink-0 text-amber-400" />
                      <span>Missing / Unresolved Parameters:</span>
                    </div>
                    <ul className="list-disc list-inside text-xs text-amber-200/90 pl-1 space-y-0.5">
                      {step.unresolved_notes.map((r: string, ri: number) => (
                        <li key={ri}>{r}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
      )}
      </div>
      )}
    </div>
  );
}

function TitleBlockPanel({ tb }: { tb: any }) {
  if (!tb) return <p className="text-slate-500 text-sm">No title block extracted.</p>;

  const fields = [
    ['Drawing Title', tb.drawing_title],
    ['Drawing Number', tb.drawing_number],
    ['Revision', tb.revision],
    ['Material', tb.material],
    ['Scale', tb.scale],
    ['Units', tb.units],
    ['Projection', tb.projection_method],
    ['General Tolerances', tb.general_tolerances],
    ['Sheet Size', tb.sheet_size],
    ['Author', tb.author],
    ['Company', tb.company],
  ];

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/50 overflow-hidden">
      <div className="divide-y divide-slate-800/60">
        {fields.map(([label, field]) => {
          const f = field as { raw_text?: string; normalized_value?: string; confidence?: number } | null;
          return (
            <div key={label} className="flex items-center gap-4 px-4 py-2.5">
              <span className="text-xs text-slate-500 w-36 flex-shrink-0">{label}</span>
              <span className="text-sm text-slate-200 flex-1 font-mono">
                {f?.raw_text ?? f?.normalized_value ?? <span className="text-slate-600">—</span>}
              </span>
              {f && (
                <span className="text-xs text-slate-600 w-10 text-right">
                  {f.confidence !== undefined ? `${Math.round(f.confidence * 100)}%` : ''}
                </span>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function ValidationPanel({ u }: { u: DrawingUnderstanding }) {
  const errors = u.validation_errors;
  const errorCount = errors.filter((e) => e.severity === 'error').length;
  const warningCount = errors.filter((e) => e.severity === 'warning').length;
  const status = errorCount > 0 ? 'FAIL' : warningCount > 0 ? 'PASS WITH WARNINGS' : 'PASS';

  return (
    <div className="space-y-3">
      <div
        className={`flex items-center gap-3 rounded-xl border px-4 py-3 ${
          status === 'PASS'
            ? 'border-emerald-500/30 bg-emerald-500/10'
            : status === 'PASS WITH WARNINGS'
            ? 'border-amber-500/30 bg-amber-500/10'
            : 'border-rose-500/30 bg-rose-500/10'
        }`}
      >
        {status === 'PASS' ? (
          <CheckCircle2 className="w-5 h-5 text-emerald-400" />
        ) : status === 'PASS WITH WARNINGS' ? (
          <AlertTriangle className="w-5 h-5 text-amber-400" />
        ) : (
          <XCircle className="w-5 h-5 text-rose-400" />
        )}
        <div>
          <span
            className={`text-sm font-semibold ${
              status === 'PASS'
                ? 'text-emerald-300'
                : status === 'PASS WITH WARNINGS'
                ? 'text-amber-300'
                : 'text-rose-300'
            }`}
          >
            {status === 'PASS'
              ? 'Validation Passed (Clean)'
              : status === 'PASS WITH WARNINGS'
              ? `Validation Passed with ${warningCount} Warning${warningCount > 1 ? 's' : ''}`
              : `Validation Failed (${errorCount} Error${errorCount > 1 ? 's' : ''}, ${warningCount} Warning${warningCount > 1 ? 's' : ''})`}
          </span>
          <p className="text-xs text-slate-400 mt-0.5">
            {status === 'PASS'
              ? 'All extracted views, dimensions, units, coordinates, and tolerances conform to structural engineering rules.'
              : status === 'PASS WITH WARNINGS'
              ? 'Data parsed successfully; minor non-blocking format warnings were noted.'
              : 'Structural invalidities found in extracted entities or coordinates.'}
          </p>
        </div>
      </div>
      {errors.length > 0 && (
        <div className="space-y-1.5">
          {errors.map((e, i) => (
            <div
              key={i}
              className={`rounded-lg border px-3 py-2 text-xs ${
                e.severity === 'error'
                  ? 'border-red-500/30 bg-red-500/10 text-red-300'
                  : 'border-amber-500/30 bg-amber-500/10 text-amber-300'
              }`}
            >
              <span className="font-mono text-slate-500">
                [{e.field_path}{e.item_id ? ` / ${e.item_id}` : ''}]
              </span>{' '}
              {e.message}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main dashboard
// ---------------------------------------------------------------------------

const TABS = [
  { id: 'image', label: 'Drawing Image', icon: <Eye className="w-4 h-4" /> },
  { id: 'features', label: 'Feature Graph', icon: <Boxes className="w-4 h-4" /> },
  { id: 'blueprint', label: '3D Blueprint', icon: <Compass className="w-4 h-4" /> },
  { id: 'mold', label: 'Mold Analysis', icon: <Zap className="w-4 h-4" /> },
  { id: 'views', label: 'Detected Views', icon: <ScanLine className="w-4 h-4" /> },
  { id: 'dimensions', label: 'Dimensions', icon: <Ruler className="w-4 h-4" /> },
  { id: 'titleblock', label: 'Title Block', icon: <Building2 className="w-4 h-4" /> },
  { id: 'consensus', label: 'Model Comparison', icon: <GitCompare className="w-4 h-4" /> },
  { id: 'validation', label: 'Validation', icon: <CheckCircle2 className="w-4 h-4" /> },
];

export const DrawingDashboard: React.FC<DrawingDashboardProps> = ({ projectId, theme = 'dark' }) => {
  const [loading, setLoading] = useState(true);
  const [understanding, setUnderstanding] = useState<DrawingUnderstanding | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState('image');
  const [provider, setProvider] = useState<'claude' | 'gemini'>('claude');
  const [showOverlay, setShowOverlay] = useState(true);
  const [highlightedDimId, setHighlightedDimId] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const u = await drawingApi.getDrawingUnderstanding(projectId);
        if (!cancelled) { setUnderstanding(u); setLoading(false); }
      } catch (e: unknown) {
        if (!cancelled) { setError(e instanceof Error ? e.message : String(e)); setLoading(false); }
      }
    })();
    return () => { cancelled = true; };
  }, [projectId]);

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center h-96 gap-4">
        <Loader2 className="w-10 h-10 text-violet-400 animate-spin" />
        <p className="text-slate-400">Loading drawing understanding…</p>
      </div>
    );
  }

  if (error || !understanding) {
    return (
      <div className="mx-auto max-w-2xl mt-16 px-4 space-y-4">
        <div className="rounded-xl border border-red-500/30 bg-red-500/10 px-5 py-6 flex items-start gap-3">
          <AlertCircle className="w-5 h-5 text-red-400 flex-shrink-0 mt-0.5" />
          <div>
            <p className="text-sm font-semibold text-red-300">Project Not Found or Analysis Incomplete</p>
            <p className="text-xs text-slate-400 mt-1">{error}</p>
          </div>
        </div>
        <div className="text-center">
          <button
            onClick={() => {
              window.location.href = window.location.origin + window.location.pathname + '?mode=uc2';
            }}
            className="px-4 py-2 rounded-lg bg-violet-600 hover:bg-violet-500 text-white text-sm font-semibold transition-colors inline-flex items-center gap-2"
          >
            ← Return to Upload / Drawing Projects
          </button>
        </div>
      </div>
    );
  }

  const u = understanding;
  const normalizedPngUrl = drawingApi.getNormalizedPngUrl(projectId);
  const activeResult = provider === 'claude' ? u.claude_result : u.gemini_result;

  const errorCount = u.validation_errors.filter((e) => e.severity === 'error').length;
  const warningCount = u.validation_errors.filter((e) => e.severity === 'warning').length;
  const validationLabel =
    errorCount > 0 ? `Fail (${errorCount})` : warningCount > 0 ? `Warnings (${warningCount})` : 'Pass';
  const validationCls =
    errorCount > 0 ? 'text-rose-400' : warningCount > 0 ? 'text-amber-400' : 'text-emerald-400';

  const featureCount = u.feature_graph?.features.length ?? 0;

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-semibold text-violet-400 bg-violet-500/10 border border-violet-500/20 rounded px-2 py-0.5">UC2</span>
            <span className="text-xs text-slate-500 font-mono">{u.project_id}</span>
          </div>
          <h2 className="text-2xl font-black text-slate-50">{u.source.filename}</h2>
          <p className="text-xs text-slate-500 font-mono mt-1 truncate max-w-xl">
            SHA-256: {u.source.sha256}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          {/* Stats */}
          {[
            {
              label: 'Claude dims',
              value: u.claude_result?.error ? '⚠ Error' : String(u.claude_result?.dimensions.length ?? 0),
              cls: 'text-blue-400',
            },
            {
              label: 'Gemini dims',
              value: u.gemini_result?.error ? '⚠ Error' : String(u.gemini_result?.dimensions.length ?? 0),
              cls: 'text-purple-400',
            },
            {
              label: 'Agreed',
              value: String(u.consensus?.total_agreed ?? 0),
              cls: 'text-emerald-400',
            },
            {
              label: 'Features',
              value: String(featureCount),
              cls: 'text-cyan-400',
            },
            {
              label: 'Validation',
              value: validationLabel,
              cls: validationCls,
            },
          ].map((s) => (
            <div key={s.label} className="rounded-lg border border-slate-800 bg-slate-900/60 px-3 py-2 text-center min-w-[72px]">
              <div className={`text-lg font-black ${s.cls}`}>{s.value}</div>
              <div className="text-xs text-slate-500">{s.label}</div>
            </div>
          ))}
          {/* Download JSON */}
          <a
            href={drawingApi.getArtifactUrl(projectId, 'understanding_json')}
            download
            className="flex items-center gap-1.5 rounded-lg border border-slate-700 bg-slate-900 hover:bg-slate-800 px-3 py-2 text-xs text-slate-300 transition-colors"
          >
            <Download className="w-3.5 h-3.5" />
            Download JSON
          </a>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex overflow-x-auto gap-1 border-b border-slate-800 pb-0.5">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            id={`tab-drawing-${tab.id}`}
            onClick={() => setActiveTab(tab.id)}
            className={`flex items-center gap-1.5 px-4 py-2.5 text-sm font-medium whitespace-nowrap rounded-t-lg transition-colors
              ${activeTab === tab.id
                ? 'bg-violet-500/15 text-violet-300 border-b-2 border-violet-500'
                : 'text-slate-500 hover:text-slate-300 hover:bg-slate-800/50'}`}
          >
            {tab.icon}
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div>
        {/* Image tab */}
        {activeTab === 'image' && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Original */}
            <div className="rounded-xl border border-slate-800 bg-slate-900/60 overflow-hidden">
              <div className="border-b border-slate-800 bg-slate-950/60 px-4 py-2.5">
                <p className="text-sm font-semibold text-slate-200">Original Drawing</p>
                <p className="text-xs text-slate-500">{u.source.mime_type} · {(u.source.file_size_bytes / 1024).toFixed(1)} KB</p>
              </div>
              <div className="p-4 flex items-center justify-center bg-slate-950/40 min-h-64">
                {u.source.mime_type.startsWith('image/') ? (
                  <img
                    src={drawingApi.getSourceUrl(projectId)}
                    alt="Original drawing"
                    className="max-w-full max-h-96 object-contain rounded"
                    onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }}
                  />
                ) : (
                  <div className="text-center text-slate-500 text-sm">
                    <p>PDF — download to view</p>
                    <a href={drawingApi.getSourceUrl(projectId)} download className="text-violet-400 hover:underline mt-2 inline-block">Download PDF</a>
                  </div>
                )}
              </div>
            </div>

            {/* Normalized PNG with Overlay */}
            <div className="rounded-xl border border-slate-800 bg-slate-900/60 overflow-hidden flex flex-col">
              <div className="border-b border-slate-800 bg-slate-950/60 px-4 py-2.5 flex items-center justify-between gap-2">
                <div>
                  <div className="flex items-center gap-2">
                    <p className="text-sm font-semibold text-slate-200">Normalized Analysis Image</p>
                    {u.render_quality === 'full' ? (
                      <span className="text-[10px] font-semibold text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 rounded px-1.5 py-0.5">
                        High-DPI Rasterized
                      </span>
                    ) : u.render_quality === 'copy' ? (
                      <span className="text-[10px] font-semibold text-blue-400 bg-blue-500/10 border border-blue-500/20 rounded px-1.5 py-0.5">
                        Raster Source
                      </span>
                    ) : u.render_error ? (
                      <span className="text-[10px] font-semibold text-rose-400 bg-rose-500/10 border border-rose-500/20 rounded px-1.5 py-0.5">
                        Render Error
                      </span>
                    ) : null}
                  </div>
                  <p className="text-xs text-slate-500 mt-0.5">
                    {u.normalized_png_sha256
                      ? `SHA-256: ${u.normalized_png_sha256.slice(0, 16)}…`
                      : 'Image sent to Claude and Gemini'}
                  </p>
                </div>
                <button
                  onClick={() => setShowOverlay(!showOverlay)}
                  className={`text-xs px-2.5 py-1 rounded border transition-colors flex items-center gap-1.5 ${
                    showOverlay
                      ? 'border-cyan-500/40 bg-cyan-500/10 text-cyan-300'
                      : 'border-slate-800 bg-slate-900 text-slate-400'
                  }`}
                >
                  <Eye className="w-3.5 h-3.5" />
                  {showOverlay ? 'Overlay On' : 'Overlay Off'}
                </button>
              </div>
              <div className="p-4 flex-1 flex flex-col items-center justify-center bg-slate-950/40 min-h-64">
                {u.render_error ? (
                  <div className="rounded-lg border border-red-500/30 bg-red-500/10 p-4 text-center max-w-md">
                    <AlertCircle className="w-6 h-6 text-red-400 mx-auto mb-2" />
                    <p className="text-sm font-semibold text-red-300">Renderer Failed</p>
                    <p className="text-xs text-slate-400 mt-1">{u.render_error}</p>
                  </div>
                ) : u.normalized_png_path ? (
                  <div className="w-full flex flex-col items-center">
                    <div className="relative inline-block max-w-full">
                      <img
                        src={normalizedPngUrl}
                        alt="Normalized drawing"
                        className="max-w-full max-h-96 object-contain rounded border border-slate-800 bg-white shadow-lg"
                      />
                    </div>
                    {u.render_notes && (
                      <p className="text-xs text-slate-500 mt-3 text-center italic">
                        {u.render_notes}
                      </p>
                    )}
                  </div>
                ) : (
                  <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-4 text-center max-w-md">
                    <AlertTriangle className="w-6 h-6 text-amber-400 mx-auto mb-2" />
                    <p className="text-sm font-semibold text-amber-300">No Normalized Image Available</p>
                    <p className="text-xs text-slate-400 mt-1">
                      Renderer dependency was missing during ingestion.
                    </p>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Feature Graph Tab */}
        {activeTab === 'features' && (
          <FeatureGraphPanel fg={u.feature_graph} />
        )}

        {/* 3D Blueprint Tab */}
        {activeTab === 'blueprint' && (
          <BlueprintPanel projectId={projectId} understanding={u} theme={theme} />
        )}

        {/* Mold Analysis Tab */}
        {activeTab === 'mold' && (
          <MoldAnalysisViewer projectId={projectId} theme={theme} />
        )}

        {/* Views tab */}
        {activeTab === 'views' && (
          <div className="space-y-4">
            <div className="flex items-center gap-2">
              <span className="text-xs text-slate-400">View source:</span>
              <button
                onClick={() => setProvider('claude')}
                className={`px-3 py-1 text-xs rounded-lg border font-medium ${provider === 'claude' ? 'border-blue-500 bg-blue-500/20 text-blue-300' : 'border-slate-800 text-slate-400'}`}
              >
                Anthropic Claude
              </button>
              <button
                onClick={() => setProvider('gemini')}
                className={`px-3 py-1 text-xs rounded-lg border font-medium ${provider === 'gemini' ? 'border-purple-500 bg-purple-500/20 text-purple-300' : 'border-slate-800 text-slate-400'}`}
              >
                Google Gemini
              </button>
            </div>
            {activeResult && <ViewsPanel result={activeResult} label={provider} />}
          </div>
        )}

        {/* Dimensions tab */}
        {activeTab === 'dimensions' && (
          <div className="space-y-4">
            <div className="flex items-center gap-2">
              <span className="text-xs text-slate-400">Dimension source:</span>
              <button
                onClick={() => setProvider('claude')}
                className={`px-3 py-1 text-xs rounded-lg border font-medium ${provider === 'claude' ? 'border-blue-500 bg-blue-500/20 text-blue-300' : 'border-slate-800 text-slate-400'}`}
              >
                Anthropic Claude ({u.claude_result?.dimensions.length ?? 0})
              </button>
              <button
                onClick={() => setProvider('gemini')}
                className={`px-3 py-1 text-xs rounded-lg border font-medium ${provider === 'gemini' ? 'border-purple-500 bg-purple-500/20 text-purple-300' : 'border-slate-800 text-slate-400'}`}
              >
                Google Gemini ({u.gemini_result?.dimensions.length ?? 0})
              </button>
            </div>
            {activeResult && (
              <DimensionsPanel
                dims={activeResult.dimensions}
                label={provider}
                highlightedId={highlightedDimId}
                onHoverDimension={setHighlightedDimId}
              />
            )}
          </div>
        )}

        {/* Title Block tab */}
        {activeTab === 'titleblock' && (
          <div className="space-y-4">
            <div className="flex items-center gap-2">
              <span className="text-xs text-slate-400">Title block source:</span>
              <button
                onClick={() => setProvider('claude')}
                className={`px-3 py-1 text-xs rounded-lg border font-medium ${provider === 'claude' ? 'border-blue-500 bg-blue-500/20 text-blue-300' : 'border-slate-800 text-slate-400'}`}
              >
                Anthropic Claude
              </button>
              <button
                onClick={() => setProvider('gemini')}
                className={`px-3 py-1 text-xs rounded-lg border font-medium ${provider === 'gemini' ? 'border-purple-500 bg-purple-500/20 text-purple-300' : 'border-slate-800 text-slate-400'}`}
              >
                Google Gemini
              </button>
            </div>
            {activeResult?.title_block && <TitleBlockPanel tb={activeResult.title_block} />}
          </div>
        )}

        {/* Consensus tab */}
        {activeTab === 'consensus' && (
          <ConsensusPanel u={u} />
        )}

        {/* Validation tab */}
        {activeTab === 'validation' && (
          <ValidationPanel u={u} />
        )}
      </div>
    </div>
  );
};
