import React, { useEffect, useState, useRef } from 'react';
import * as THREE from 'three';
import {
  Loader2, AlertCircle, CheckCircle2, XCircle, Eye, Ruler, Layers,
  ScanLine, GitCompare, Building2, AlertTriangle, ChevronDown, ChevronRight,
  Download, RefreshCw, Info, Boxes, Compass, Sparkles, SlidersHorizontal, Maximize2,
  Box, FileDown, RotateCcw, Play, Zap, Check, Send
} from 'lucide-react';
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

function ReconstructedSolidViewer({
  meshData,
  metrics,
  projectId,
}: {
  meshData: any;
  metrics?: any;
  projectId: string;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [wireframe, setWireframe] = useState(false);
  const [viewMode, setViewMode] = useState<'brep_interactive' | 'ai_concept_render'>('brep_interactive');

  useEffect(() => {
    if (!containerRef.current || !meshData || viewMode !== 'brep_interactive') return;
    const container = containerRef.current;
    const width = container.clientWidth;
    const height = 400;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x070b19);

    const camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 3000);
    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));

    container.innerHTML = '';
    container.appendChild(renderer.domElement);

    // Lights
    scene.add(new THREE.AmbientLight(0xffffff, 1.1));
    const dir1 = new THREE.DirectionalLight(0x38bdf8, 1.5);
    dir1.position.set(150, 250, 200);
    scene.add(dir1);
    const dir2 = new THREE.DirectionalLight(0xa855f7, 1.0);
    dir2.position.set(-150, -100, -150);
    scene.add(dir2);
    const dir3 = new THREE.DirectionalLight(0xffffff, 0.8);
    dir3.position.set(0, -200, 100);
    scene.add(dir3);

    // Pivot group for smooth rotation around object center
    const pivotGroup = new THREE.Group();
    scene.add(pivotGroup);

    // Geometry
    const geom = new THREE.BufferGeometry();
    const pos = new Float32Array(meshData.vertices);
    geom.setAttribute('position', new THREE.BufferAttribute(pos, 3));

    if (meshData.indices && meshData.indices.length > 0) {
      geom.setIndex(meshData.indices);
    }
    geom.computeVertexNormals();
    geom.center();

    const mat = new THREE.MeshPhysicalMaterial({
      color: 0x0284c7,
      metalness: 0.25,
      roughness: 0.3,
      clearcoat: 0.5,
      wireframe: wireframe,
      side: THREE.DoubleSide,
      transparent: true,
      opacity: 0.94,
    });

    const mesh = new THREE.Mesh(geom, mat);
    pivotGroup.add(mesh);

    // Render sharp CAD boundary edges if available
    if (meshData.edges && meshData.edges.length > 0) {
      const edgePositions: number[] = [];
      meshData.edges.forEach((seg: number[]) => {
        if (seg.length >= 6) {
          edgePositions.push(seg[0], seg[1], seg[2], seg[3], seg[4], seg[5]);
        }
      });
      if (edgePositions.length > 0) {
        const edgeGeom = new THREE.BufferGeometry();
        edgeGeom.setAttribute('position', new THREE.Float32BufferAttribute(edgePositions, 3));
        edgeGeom.center();
        const edgeMat = new THREE.LineBasicMaterial({ color: 0x38bdf8, linewidth: 1.5, transparent: true, opacity: 0.85 });
        const edgeLines = new THREE.LineSegments(edgeGeom, edgeMat);
        pivotGroup.add(edgeLines);
      }
    }

    // Grid Floor below part
    geom.computeBoundingSphere();
    const sphere = geom.boundingSphere || { radius: 40 };
    const radius = Math.max(sphere.radius, 15);

    const grid = new THREE.GridHelper(radius * 5, 30, 0x334155, 0x0f172a);
    grid.position.y = -radius * 0.9;
    scene.add(grid);

    // Camera initial framing
    camera.position.set(radius * 1.3, radius * 1.1, radius * 1.5);
    camera.lookAt(0, 0, 0);

    // Simple Orbit Controls via mouse drag
    let isDragging = false;
    let prevX = 0;
    let prevY = 0;
    let rotX = 0.35;
    let rotY = 0.75;
    let zoom = 1.0;

    const onMouseDown = (e: MouseEvent) => {
      isDragging = true;
      prevX = e.clientX;
      prevY = e.clientY;
    };
    const onMouseMove = (e: MouseEvent) => {
      if (!isDragging) return;
      const dx = e.clientX - prevX;
      const dy = e.clientY - prevY;
      rotY += dx * 0.01;
      rotX += dy * 0.01;
      prevX = e.clientX;
      prevY = e.clientY;
    };
    const onMouseUp = () => {
      isDragging = false;
    };
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      zoom *= e.deltaY > 0 ? 1.08 : 0.92;
      zoom = Math.max(0.3, Math.min(zoom, 4.0));
    };

    const dom = container;
    dom.addEventListener('mousedown', onMouseDown);
    window.addEventListener('mousemove', onMouseMove);
    window.addEventListener('mouseup', onMouseUp);
    dom.addEventListener('wheel', onWheel, { passive: false });

    let reqId: number;
    const animate = () => {
      reqId = requestAnimationFrame(animate);
      pivotGroup.rotation.y = rotY;
      pivotGroup.rotation.x = rotX;
      camera.position.set(radius * 1.3 * zoom, radius * 1.1 * zoom, radius * 1.5 * zoom);
      camera.lookAt(0, 0, 0);
      renderer.render(scene, camera);
    };
    animate();

    return () => {
      cancelAnimationFrame(reqId);
      dom.removeEventListener('mousedown', onMouseDown);
      window.removeEventListener('mousemove', onMouseMove);
      window.removeEventListener('mouseup', onMouseUp);
      dom.removeEventListener('wheel', onWheel);
      renderer.dispose();
    };
  }, [meshData, wireframe, viewMode]);

  return (
    <div className="rounded-xl border border-emerald-500/40 bg-slate-950/95 overflow-hidden shadow-2xl space-y-3 p-4 animate-in fade-in zoom-in-95 duration-300">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between border-b border-slate-800/80 pb-3 gap-3">
        <div className="flex items-center gap-2">
          <Box className="w-5 h-5 text-emerald-400" />
          <div>
            <h4 className="text-sm font-bold text-slate-100 flex items-center gap-2">
              Reconstructed 3D Solid Model
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/40">
                {viewMode === 'brep_interactive' ? 'Deterministic OpenCASCADE B-Rep' : 'AI Multimodal Studio Shading'}
              </span>
            </h4>
            <p className="text-xs text-slate-400">
              {viewMode === 'brep_interactive'
                ? 'Interactive 3D geometry synthesized from 2D drawing blueprint.'
                : 'Photorealistic multi-view CAD workbench rendering with feature decomposition.'}
            </p>
          </div>
        </div>

        {/* Dual Mode Switcher & Download Buttons */}
        <div className="flex items-center gap-2 font-mono text-xs">
          <div className="flex items-center gap-1 bg-slate-900 border border-slate-800 p-0.5 rounded-lg">
            <button
              onClick={() => setViewMode('brep_interactive')}
              className={`px-3 py-1 rounded-md text-xs font-bold transition-all ${
                viewMode === 'brep_interactive'
                  ? 'bg-emerald-600 text-white shadow-md'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              ⚙️ Interactive 3D B-Rep
            </button>
            <button
              onClick={() => setViewMode('ai_concept_render')}
              className={`px-3 py-1 rounded-md text-xs font-bold transition-all ${
                viewMode === 'ai_concept_render'
                  ? 'bg-gradient-to-r from-purple-600 to-indigo-600 text-white shadow-md'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              🎨 AI Studio Render
            </button>
          </div>

          {viewMode === 'brep_interactive' && (
            <button
              onClick={() => setWireframe((w) => !w)}
              className={`px-2.5 py-1.5 rounded-lg border text-xs font-bold transition-colors ${
                wireframe ? 'bg-cyan-500/20 text-cyan-300 border-cyan-500/40' : 'bg-slate-900 text-slate-400 border-slate-800 hover:text-slate-200'
              }`}
            >
              <Layers className="w-3.5 h-3.5 inline mr-1" />
              Wireframe
            </button>
          )}

          <a
            href={drawingApi.getArtifactUrl(projectId, 'reconstructed_step')}
            download
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 font-bold hover:bg-emerald-500/30 transition-colors shadow-sm"
          >
            <Download className="w-3.5 h-3.5" />
            <span>STEP (.step)</span>
          </a>
          <a
            href={drawingApi.getArtifactUrl(projectId, 'reconstructed_fcstd')}
            download
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 font-bold hover:bg-cyan-500/30 transition-colors shadow-sm"
          >
            <FileDown className="w-3.5 h-3.5" />
            <span>FreeCAD (.FCStd)</span>
          </a>
          <a
            href={drawingApi.getArtifactUrl(projectId, 'reconstructed_build123d')}
            download
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-amber-500/20 text-amber-300 border border-amber-500/40 font-bold hover:bg-amber-500/30 transition-colors shadow-sm"
            title="Download executable build123d Python CAD Script"
          >
            <FileDown className="w-3.5 h-3.5" />
            <span>Python (build123d)</span>
          </a>
        </div>
      </div>

      {/* Main 3D Canvas / AI Concept Studio Display */}
      {viewMode === 'brep_interactive' ? (
        <div
          ref={containerRef}
          className="w-full h-[400px] rounded-lg overflow-hidden border border-slate-800 bg-slate-950 cursor-grab active:cursor-grabbing select-none"
        />
      ) : (
        <div className="w-full h-[400px] rounded-lg overflow-hidden border border-purple-500/30 bg-slate-950 flex flex-col items-center justify-center relative group">
          <img
            src={drawingApi.getArtifactUrl(projectId, 'visual_concept_render')}
            alt="AI Studio Concept Shaded Workbench"
            className="w-full h-full object-contain"
            onError={(e) => {
              (e.target as HTMLImageElement).src = drawingApi.getArtifactUrl(projectId, 'normalized_png');
            }}
          />
          <div className="absolute bottom-3 left-3 right-3 bg-slate-950/85 backdrop-blur border border-purple-500/40 rounded-lg px-3 py-2 flex items-center justify-between text-xs font-mono text-purple-300 shadow-xl">
            <span className="flex items-center gap-1.5 font-bold">
              <span>✨</span> Gemini Multimodal CAD Studio Concept Render
            </span>
            <span className="text-slate-400 text-[11px]">Feature Decomposition &amp; Shaded Isometric</span>
          </div>
        </div>
      )}

      {/* Metrics Bar */}
      {metrics && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-1 font-mono text-xs">
          <div className="p-2 rounded bg-slate-900 border border-slate-800">
            <span className="text-slate-500 block text-[10px]">Solid Volume</span>
            <span className="text-cyan-300 font-bold">{metrics.volume_mm3?.toLocaleString()} mm³</span>
          </div>
          <div className="p-2 rounded bg-slate-900 border border-slate-800">
            <span className="text-slate-500 block text-[10px]">B-Rep Faces</span>
            <span className="text-pink-300 font-bold">{metrics.face_count} Faces</span>
          </div>
          <div className="p-2 rounded bg-slate-900 border border-slate-800">
            <span className="text-slate-500 block text-[10px]">B-Rep Edges</span>
            <span className="text-yellow-300 font-bold">{metrics.edge_count} Edges</span>
          </div>
          <div className="p-2 rounded bg-slate-900 border border-slate-800">
            <span className="text-slate-500 block text-[10px]">Bounding Box (X×Y×Z)</span>
            <span className="text-slate-200 font-bold">
              {metrics.bounding_box?.extents?.map((e: number) => e.toFixed(1)).join(' × ')} mm
            </span>
          </div>
        </div>
      )}
    </div>
  );
}

function BlueprintPanel({ projectId }: { projectId: string }) {
  const [plan, setPlan] = useState<ParametricReconstructionPlan | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Human Parameter Overrides State
  const [heightZInput, setHeightZInput] = useState<string>('30.0');
  const [holeDepthInput, setHoleDepthInput] = useState<string>('34.0');
  const [bossHeightInput, setBossHeightInput] = useState<string>('15.0');
  const [isReconstructing, setIsReconstructing] = useState<boolean>(false);
  const [reconstructResult, setReconstructResult] = useState<any | null>(null);
  const [reconstructedMesh, setReconstructedMesh] = useState<any | null>(null);
  const [reconstructError, setReconstructError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const p = await drawingApi.getReconstructionPlan(projectId);
        if (!cancelled) {
          setPlan(p);
          setLoading(false);
        }

        // Try preloading any existing reconstructed mesh
        try {
          const mesh = await drawingApi.getReconstructedMesh(projectId);
          if (!cancelled && mesh) {
            setReconstructedMesh(mesh);
          }
        } catch (_) {
          // Not reconstructed yet
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

  const handleExecuteReconstruction = async () => {
    setIsReconstructing(true);
    setReconstructError(null);
    try {
      const overrides: Record<string, number> = {
        height_z: parseFloat(heightZInput) || 30.0,
        hole_depth: parseFloat(holeDepthInput) || 34.0,
        boss_height: parseFloat(bossHeightInput) || 15.0,
      };
      const res = await drawingApi.reconstruct3DSolid(projectId, overrides);
      setReconstructResult(res);

      const mesh = await drawingApi.getReconstructedMesh(projectId);
      setReconstructedMesh(mesh);
    } catch (err: unknown) {
      setReconstructError(err instanceof Error ? err.message : String(err));
    } finally {
      setIsReconstructing(false);
    }
  };

  if (loading) {
    return (
      <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-8 text-center text-slate-400 text-sm flex items-center justify-center gap-2">
        <Loader2 className="w-4 h-4 animate-spin text-violet-400" />
        Loading Phase 19A Parametric Reconstruction Blueprint…
      </div>
    );
  }

  if (error || !plan) {
    return (
      <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-6 text-center text-red-300 text-sm">
        <AlertCircle className="w-6 h-6 mx-auto mb-2 text-red-400" />
        Failed to load reconstruction plan: {error}
      </div>
    );
  }

  const env = plan.envelope_3d;
  const audit = plan.evidence_audit;
  const statusColor =
    plan.reconstruction_status === 'COMPLETE'
      ? 'border-emerald-500/40 bg-emerald-500/10 text-emerald-300'
      : plan.reconstruction_status === 'PARTIAL_ASSUMED'
      ? 'border-amber-500/40 bg-amber-500/10 text-amber-300'
      : 'border-rose-500/40 bg-rose-500/10 text-rose-300';

  return (
    <div className="space-y-6">
      {/* 3D Envelope & Status Header */}
      <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4 flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-semibold text-violet-400 bg-violet-500/10 border border-violet-500/20 px-2 py-0.5 rounded">
              Phase 19A.2
            </span>
            <span className={`text-xs font-bold px-2 py-0.5 rounded border ${statusColor}`}>
              {plan.reconstruction_status === 'PARTIAL_ASSUMED'
                ? 'PARTIAL RECONSTRUCTION / ASSUMED / UNCONSTRAINED'
                : plan.reconstruction_status === 'COMPLETE'
                ? '100% COMPLETE RECONSTRUCTION'
                : 'INSUFFICIENT EVIDENCE'}
            </span>
          </div>
          <h3 className="text-base font-bold text-slate-100 flex items-center gap-2">
            <Compass className="w-4 h-4 text-emerald-400" />
            Parametric 3D CAD Reconstruction Blueprint & Operation Evidence Gate
          </h3>
          {plan.plan_notes.length > 0 && (
            <div className="mt-1.5 space-y-0.5">
              {plan.plan_notes.map((note: string, ni: number) => (
                <p key={ni} className="text-xs text-amber-400 flex items-center gap-1 font-mono">
                  <AlertTriangle className="w-3.5 h-3.5 flex-shrink-0" />
                  {note}
                </p>
              ))}
            </div>
          )}
        </div>
        <div className="flex items-center gap-2 font-mono text-sm">
          <div className="px-3 py-1.5 rounded-lg border border-slate-800 bg-slate-950/80">
            <span className="text-xs text-slate-500 block">Bounding Box (X × Y × Z)</span>
            <span className="text-slate-100 font-bold">
              {env.width_x != null ? `${env.width_x} mm` : '—'} × {env.depth_y != null ? `${env.depth_y} mm` : '—'} × {env.height_z != null ? `${env.height_z} mm` : '—'}
            </span>
          </div>
        </div>
      </div>

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

      {/* Parameter Resolution & 3D CAD Reconstruction Trigger Panel */}
      <div className="rounded-xl border border-cyan-500/30 bg-gradient-to-r from-slate-900/90 via-cyan-950/20 to-slate-900/90 p-5 space-y-4 shadow-xl">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-800 pb-3">
          <div className="flex items-center gap-2.5">
            <Zap className="w-5 h-5 text-cyan-400" />
            <div>
              <h4 className="text-sm font-bold text-slate-100 flex items-center gap-2">
                Phase 19B & 19D — 3D CAD Solid Reconstruction
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-cyan-500/20 text-cyan-300 border border-cyan-500/40">
                  OpenCASCADE Kernel
                </span>
              </h4>
              <p className="text-xs text-slate-400">
                Supply or confirm missing parameters to unlock the gate and synthesize a real 3D solid model (.STEP & .FCStd).
              </p>
            </div>
          </div>

          {/* Reconstruction Trigger Button */}
          <button
            onClick={handleExecuteReconstruction}
            disabled={isReconstructing}
            className={`flex items-center gap-2 px-5 py-2.5 rounded-xl text-xs font-bold font-mono transition-all shadow-lg ${
              isReconstructing
                ? 'bg-cyan-500/40 text-slate-300 cursor-not-allowed'
                : 'bg-gradient-to-r from-cyan-500 to-emerald-500 text-slate-950 hover:brightness-110 active:scale-95 shadow-cyan-500/25'
            }`}
          >
            {isReconstructing ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin text-slate-950" />
                <span>Executing OpenCASCADE CSG Kernel...</span>
              </>
            ) : (
              <>
                <Play className="w-4 h-4 fill-slate-950" />
                <span>Generate 3D Solid CAD (STEP & FCStd)</span>
              </>
            )}
          </button>
        </div>

        {/* Human Parameter Resolution Inputs */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 font-mono text-xs">
          <div className="p-3 rounded-lg bg-slate-950/80 border border-slate-800 space-y-1.5">
            <label className="text-slate-400 block text-[11px] font-bold flex items-center justify-between">
              <span>Base Height (Z Extrusion)</span>
              <span className="text-amber-400 text-[10px]">Unconstrained</span>
            </label>
            <div className="flex items-center gap-2">
              <input
                type="number"
                step="0.5"
                value={heightZInput}
                onChange={(e) => setHeightZInput(e.target.value)}
                className="w-full bg-slate-900 border border-slate-700 rounded px-2.5 py-1.5 text-xs text-cyan-300 font-bold focus:outline-none focus:border-cyan-400"
              />
              <span className="text-slate-500 text-xs">mm</span>
            </div>
            <p className="text-[10px] text-slate-500">2D profile is 70.04 × 50 mm.</p>
          </div>

          <div className="p-3 rounded-lg bg-slate-950/80 border border-slate-800 space-y-1.5">
            <label className="text-slate-400 block text-[11px] font-bold flex items-center justify-between">
              <span>Through-Hole Cut Depth</span>
              <span className="text-amber-400 text-[10px]">Unconstrained</span>
            </label>
            <div className="flex items-center gap-2">
              <input
                type="number"
                step="0.5"
                value={holeDepthInput}
                onChange={(e) => setHoleDepthInput(e.target.value)}
                className="w-full bg-slate-900 border border-slate-700 rounded px-2.5 py-1.5 text-xs text-cyan-300 font-bold focus:outline-none focus:border-cyan-400"
              />
              <span className="text-slate-500 text-xs">mm</span>
            </div>
            <p className="text-[10px] text-slate-500">Applies clean through cut (Ø11 & Ø5.5).</p>
          </div>

          <div className="p-3 rounded-lg bg-slate-950/80 border border-slate-800 space-y-1.5">
            <label className="text-slate-400 block text-[11px] font-bold flex items-center justify-between">
              <span>Boss Extrusion Length</span>
              <span className="text-amber-400 text-[10px]">Unconstrained</span>
            </label>
            <div className="flex items-center gap-2">
              <input
                type="number"
                step="0.5"
                value={bossHeightInput}
                onChange={(e) => setBossHeightInput(e.target.value)}
                className="w-full bg-slate-900 border border-slate-700 rounded px-2.5 py-1.5 text-xs text-cyan-300 font-bold focus:outline-none focus:border-cyan-400"
              />
              <span className="text-slate-500 text-xs">mm</span>
            </div>
            <p className="text-[10px] text-slate-500">Applies to Ø30 & Ø16 side bosses.</p>
          </div>
        </div>

        {reconstructError && (
          <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/30 text-xs text-red-300 flex items-center gap-2 font-mono">
            <AlertCircle className="w-4 h-4 text-red-400 flex-shrink-0" />
            <span>{reconstructError}</span>
          </div>
        )}
      </div>

      {/* Rendered 3D Solid Viewer if reconstructed */}
      {reconstructedMesh && (
        <ReconstructedSolidViewer
          meshData={reconstructedMesh}
          metrics={reconstructResult?.metrics}
          projectId={projectId}
        />
      )}

      {/* Unconstrained Parameters Alert */}
      {plan.unconstrained_parameters.length > 0 && (
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
  { id: 'views', label: 'Detected Views', icon: <ScanLine className="w-4 h-4" /> },
  { id: 'dimensions', label: 'Dimensions', icon: <Ruler className="w-4 h-4" /> },
  { id: 'titleblock', label: 'Title Block', icon: <Building2 className="w-4 h-4" /> },
  { id: 'consensus', label: 'Model Comparison', icon: <GitCompare className="w-4 h-4" /> },
  { id: 'validation', label: 'Validation', icon: <CheckCircle2 className="w-4 h-4" /> },
];

interface DrawingDashboardProps {
  projectId: string;
  theme?: 'light' | 'dark';
}

export const DrawingDashboard: React.FC<DrawingDashboardProps> = ({ projectId, theme = 'light' }) => {
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
      <div className="mx-auto max-w-2xl mt-16 px-4">
        <div className="rounded-xl border border-red-500/30 bg-red-500/10 px-5 py-6 flex items-start gap-3">
          <AlertCircle className="w-5 h-5 text-red-400 flex-shrink-0 mt-0.5" />
          <div>
            <p className="text-sm font-semibold text-red-300">Failed to load drawing understanding</p>
            <p className="text-xs text-slate-400 mt-1">{error}</p>
          </div>
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
          <BlueprintPanel projectId={projectId} />
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
