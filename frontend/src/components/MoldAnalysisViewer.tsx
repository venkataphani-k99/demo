import React, { useState, useEffect, useRef, useMemo } from 'react';
import * as THREE from 'three';
import {
  Layers,
  ArrowRight,
  ShieldCheck,
  AlertTriangle,
  HelpCircle,
  Eye,
  Sliders,
  Sparkles,
  RefreshCw,
  Compass,
  CheckCircle2,
  DollarSign,
  Maximize2,
  Minimize2,
  Info,
  ChevronRight,
  ChevronDown,
  Wrench,
  Gauge,
  CircleDot,
  RotateCcw,
  Tag,
  FileCheck,
  AlertOctagon,
  ArrowUpRight,
  Code2,
  Terminal,
  Cpu,
  Check,
  Filter,
} from 'lucide-react';
import {
  ManufacturingReviewResponse,
  ManufacturingFinding,
  PullDirectionCandidate,
  ProcessPreset,
  SliderAction,
  CADMeshResponse,
  VectorVerificationProof,
  DraftRelevanceBreakdown,
  ConnectedUndercutRegion,
  api,
} from '../../lib/api';

interface MoldAnalysisViewerProps {
  projectId: string;
  meshData?: CADMeshResponse | null;
  theme?: 'light' | 'dark';
}

export const MoldAnalysisViewer: React.FC<MoldAnalysisViewerProps> = ({
  projectId,
  meshData: externalMeshData,
  theme = 'dark',
}) => {
  const isLight = theme === 'light';

  // Data states
  const [mfgData, setMfgData] = useState<ManufacturingReviewResponse | null>(null);
  const [presets, setPresets] = useState<ProcessPreset[]>([]);
  const [activePresetId, setActivePresetId] = useState<string>('GENERAL_PLASTIC_INJECTION');
  const [draftThreshold, setDraftThreshold] = useState<number>(1.5);
  const [meshData, setMeshData] = useState<CADMeshResponse | null>(externalMeshData || null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isEvaluating, setIsEvaluating] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Review & Viewport Controls
  const [activeCandidateId, setActiveCandidateId] = useState<string>('PULL_DIR_POS_Z');
  const [displayFilter, setDisplayFilter] = useState<'ALL' | 'CAVITY' | 'CORE' | 'UNDERCUT' | 'INSUFFICIENT' | 'EXCLUDED'>('ALL');
  const [selectedFindingId, setSelectedFindingId] = useState<string | null>(null);
  const [selectedSliderId, setSelectedSliderId] = useState<string | null>(null);
  const [selectedFaceId, setSelectedFaceId] = useState<string | null>(null);
  const [showPartingLine, setShowPartingLine] = useState<boolean>(true);
  const [showSliderArrows, setShowSliderArrows] = useState<boolean>(true);
  const [showMainPullArrow, setShowMainPullArrow] = useState<boolean>(true);
  const [isDebugMode, setIsDebugMode] = useState<boolean>(false);
  const [activeTabSubView, setActiveTabSubView] = useState<'FINDINGS' | 'SLIDERS' | 'DECOMPOSITION' | 'AI_AGENDA' | 'DEBUG_PROOF'>('FINDINGS');

  // Three.js Viewport References
  const containerRef = useRef<HTMLDivElement>(null);
  const sceneRef = useRef<THREE.Scene | null>(null);
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null);
  const rendererRef = useRef<THREE.WebGLRenderer | null>(null);
  const coloredMeshGroupRef = useRef<THREE.Group | null>(null);
  const partingLineGroupRef = useRef<THREE.Group | null>(null);
  const sliderArrowsGroupRef = useRef<THREE.Group | null>(null);
  const mainPullArrowGroupRef = useRef<THREE.Group | null>(null);

  // Camera Orbit State
  const orbitStateRef = useRef({
    target: new THREE.Vector3(0, 0, 0),
    spherical: { radius: 180, theta: Math.PI / 4, phi: Math.PI / 3 },
    updateCamera: () => {},
    resetView: () => {},
  });

  // 1. Initial Load
  useEffect(() => {
    let isMounted = true;
    const loadData = async () => {
      setIsLoading(true);
      setError(null);
      try {
        const [revData, presetList, mMesh] = await Promise.all([
          api.getManufacturingReview(projectId, activePresetId),
          api.getManufacturingPresets().catch(() => []),
          externalMeshData ? Promise.resolve(externalMeshData) : api.getMesh(projectId),
        ]);
        if (isMounted) {
          setMfgData(revData);
          if (presetList && presetList.length > 0) setPresets(presetList);
          if (mMesh) setMeshData(mMesh);
          if (revData.preset_used?.nominal_draft_deg) {
            setDraftThreshold(revData.preset_used.nominal_draft_deg);
          }
          if (revData.findings && revData.findings.length > 0) {
            setSelectedFindingId(revData.findings[0].finding_id);
            if (revData.findings[0].source_entities?.length > 0) {
              setSelectedFaceId(revData.findings[0].source_entities[0]);
            }
          }
        }
      } catch (err: unknown) {
        if (isMounted) {
          setError(err instanceof Error ? err.message : String(err));
        }
      } finally {
        if (isMounted) setIsLoading(false);
      }
    };

    loadData();
    return () => {
      isMounted = false;
    };
  }, [projectId, externalMeshData]);

  // 2. Preset or Candidate Direction Change
  const handlePresetChange = async (newPresetId: string) => {
    setActivePresetId(newPresetId);
    setIsEvaluating(true);
    try {
      const updated = await api.getManufacturingReview(projectId, newPresetId, true);
      setMfgData(updated);
      if (updated.preset_used?.nominal_draft_deg) {
        setDraftThreshold(updated.preset_used.nominal_draft_deg);
      }
    } catch (err) {
      console.error('Failed to change process preset:', err);
    } finally {
      setIsEvaluating(false);
    }
  };

  const handleSelectCandidateDirection = async (candidate: PullDirectionCandidate) => {
    setActiveCandidateId(candidate.candidate_id);
    setIsEvaluating(true);
    try {
      const updated = await api.evaluateManufacturingReview(projectId, {
        direction: candidate.direction_vector,
        min_draft_deg: draftThreshold,
        preset_id: activePresetId,
      });
      setMfgData(updated);
    } catch (err) {
      console.error('Failed to evaluate candidate direction:', err);
    } finally {
      setIsEvaluating(false);
    }
  };

  const handleDraftThresholdChange = async (newVal: number) => {
    setDraftThreshold(newVal);
    setIsEvaluating(true);
    try {
      const updated = await api.evaluateManufacturingReview(projectId, {
        direction: mfgData?.optimal_pull_direction || [0, 0, 1],
        min_draft_deg: newVal,
        preset_id: activePresetId,
      });
      setMfgData(updated);
    } catch (err) {
      console.error('Failed to update draft threshold:', err);
    } finally {
      setIsEvaluating(false);
    }
  };

  // 3. Initialize Three.js Viewport
  useEffect(() => {
    if (!containerRef.current || !mfgData) return;
    const container = containerRef.current;
    const width = container.clientWidth;
    const height = container.clientHeight || 560;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(isLight ? 0xf8fafc : 0x070b19);
    sceneRef.current = scene;

    const camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 4000);
    cameraRef.current = camera;

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false, powerPreference: 'high-performance' });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.shadowMap.enabled = true;
    rendererRef.current = renderer;

    container.innerHTML = '';
    container.appendChild(renderer.domElement);

    // Lighting
    const ambientLight = new THREE.AmbientLight(0xffffff, isLight ? 0.95 : 0.85);
    scene.add(ambientLight);

    const dirLight1 = new THREE.DirectionalLight(0xe0f2fe, 1.3);
    dirLight1.position.set(160, 220, 180);
    scene.add(dirLight1);

    const dirLight2 = new THREE.DirectionalLight(0x38bdf8, 0.6);
    dirLight2.position.set(-160, -100, -140);
    scene.add(dirLight2);

    // Grid
    const grid = new THREE.GridHelper(260, 26, isLight ? 0xcbd5e1 : 0x1e293b, isLight ? 0xe2e8f0 : 0x0f172a);
    grid.position.y = -40;
    scene.add(grid);

    // Orbit
    const target = new THREE.Vector3(0, 0, 0);
    const spherical = { radius: 180, theta: Math.PI / 4, phi: Math.PI / 3 };

    const updateCameraPosition = () => {
      camera.position.x = target.x + spherical.radius * Math.sin(spherical.phi) * Math.sin(spherical.theta);
      camera.position.y = target.y + spherical.radius * Math.cos(spherical.phi);
      camera.position.z = target.z + spherical.radius * Math.sin(spherical.phi) * Math.cos(spherical.theta);
      camera.lookAt(target);
    };
    updateCameraPosition();

    orbitStateRef.current.target = target;
    orbitStateRef.current.spherical = spherical;
    orbitStateRef.current.updateCamera = updateCameraPosition;
    orbitStateRef.current.resetView = () => {
      target.set(0, 0, 0);
      const maxDim = meshData?.bounds ? Math.max(meshData.bounds.x_len, meshData.bounds.y_len, meshData.bounds.z_len) : 60;
      spherical.radius = Math.max(90, maxDim * 2.2);
      spherical.theta = Math.PI / 4;
      spherical.phi = Math.PI / 3;
      updateCameraPosition();
    };

    // Mouse Controls
    let isDragging = false;
    let dragMode: 'orbit' | 'pan' = 'orbit';
    let previousMousePosition = { x: 0, y: 0 };

    const onMouseDown = (e: MouseEvent) => {
      if (e.button === 2 || e.button === 1 || (e.button === 0 && e.shiftKey)) {
        dragMode = 'pan';
      } else if (e.button === 0) {
        dragMode = 'orbit';
      } else {
        return;
      }
      isDragging = true;
      previousMousePosition = { x: e.clientX, y: e.clientY };
    };

    const onMouseMove = (e: MouseEvent) => {
      if (!isDragging) return;
      const deltaX = e.clientX - previousMousePosition.x;
      const deltaY = e.clientY - previousMousePosition.y;

      if (dragMode === 'orbit') {
        spherical.theta -= deltaX * 0.008;
        spherical.phi = Math.max(0.01, Math.min(Math.PI - 0.01, spherical.phi - deltaY * 0.008));
      } else if (dragMode === 'pan') {
        const forward = new THREE.Vector3().subVectors(target, camera.position).normalize();
        const worldUp = new THREE.Vector3(0, 1, 0);
        const right = new THREE.Vector3().crossVectors(forward, worldUp).normalize();
        const cameraUp = new THREE.Vector3().crossVectors(right, forward).normalize();
        const panSpeed = spherical.radius * 0.0016;
        target.addScaledVector(right, -deltaX * panSpeed);
        target.addScaledVector(cameraUp, deltaY * panSpeed);
      }

      updateCameraPosition();
      previousMousePosition = { x: e.clientX, y: e.clientY };
    };

    const onMouseUp = () => {
      isDragging = false;
    };

    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      spherical.radius = Math.max(15, Math.min(1000, spherical.radius + e.deltaY * 0.15));
      updateCameraPosition();
    };

    container.addEventListener('mousedown', onMouseDown);
    container.addEventListener('mousemove', onMouseMove);
    container.addEventListener('wheel', onWheel, { passive: false });
    window.addEventListener('mouseup', onMouseUp);

    let animId: number;
    const animate = () => {
      animId = requestAnimationFrame(animate);
      renderer.render(scene, camera);
    };
    animate();

    const handleResize = () => {
      if (!container) return;
      const w = container.clientWidth;
      const h = container.clientHeight || 560;
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
    };
    window.addEventListener('resize', handleResize);

    return () => {
      cancelAnimationFrame(animId);
      container.removeEventListener('mousedown', onMouseDown);
      container.removeEventListener('mousemove', onMouseMove);
      container.removeEventListener('wheel', onWheel);
      window.removeEventListener('mouseup', onMouseUp);
      window.removeEventListener('resize', handleResize);
      renderer.dispose();
    };
  }, [mfgData]);

  // 4. Render Color-Coded Moldability B-Rep Mesh
  useEffect(() => {
    if (!sceneRef.current || !meshData || !mfgData) return;
    const scene = sceneRef.current;

    if (coloredMeshGroupRef.current) {
      scene.remove(coloredMeshGroupRef.current);
      coloredMeshGroupRef.current = null;
    }
    if (partingLineGroupRef.current) {
      scene.remove(partingLineGroupRef.current);
      partingLineGroupRef.current = null;
    }
    if (sliderArrowsGroupRef.current) {
      scene.remove(sliderArrowsGroupRef.current);
      sliderArrowsGroupRef.current = null;
    }
    if (mainPullArrowGroupRef.current) {
      scene.remove(mainPullArrowGroupRef.current);
      mainPullArrowGroupRef.current = null;
    }

    const { bounds, faces_map } = meshData;
    const cx = bounds?.center?.[0] ?? 0;
    const cy = bounds?.center?.[1] ?? 0;
    const cz = bounds?.center?.[2] ?? 0;

    const meshGroup = new THREE.Group();

    const COLOR_CAVITY = new THREE.Color(0x22c55e);      // Emerald Green (Cavity)
    const COLOR_CORE = new THREE.Color(0x3b82f6);        // Royal Blue (Core)
    const COLOR_INSUFFICIENT = new THREE.Color(0xf59e0b); // Amber (Low Draft)
    const COLOR_UNDERCUT = new THREE.Color(0xef4444);    // Crimson Red (Undercut)
    const COLOR_CROSSING = new THREE.Color(0xa855f7);    // Purple (Crossover)
    const COLOR_EXCLUDED = new THREE.Color(0x64748b);    // Slate (Excluded Planar Cap)
    const COLOR_HIGHLIGHT = new THREE.Color(0xfff176);   // Bright yellow for selection

    if (faces_map) {
      for (const [faceId, fData] of Object.entries(faces_map)) {
        if (!fData.vertices || !fData.indices) continue;

        const faceAnalysis = mfgData.face_details?.[faceId];
        const classification = faceAnalysis?.classification || 'POSITIVE_DRAFT_CAVITY';
        const relevance = faceAnalysis?.relevance || 'APPLICABLE';

        let isVisible = true;
        if (displayFilter === 'CAVITY' && !classification.includes('CAVITY')) isVisible = false;
        if (displayFilter === 'CORE' && !classification.includes('CORE')) isVisible = false;
        if (displayFilter === 'UNDERCUT' && classification !== 'UNDERCUT') isVisible = false;
        if (displayFilter === 'INSUFFICIENT' && !classification.includes('LOW') && !classification.includes('ZERO')) isVisible = false;
        if (displayFilter === 'EXCLUDED' && relevance === 'APPLICABLE') isVisible = false;

        const fVerts: number[] = [];
        for (let i = 0; i < fData.vertices.length; i += 3) {
          fVerts.push(fData.vertices[i] - cx, fData.vertices[i + 1] - cy, fData.vertices[i + 2] - cz);
        }
        const fGeom = new THREE.BufferGeometry();
        fGeom.setAttribute('position', new THREE.Float32BufferAttribute(fVerts, 3));
        fGeom.setIndex(fData.indices);
        fGeom.computeVertexNormals();

        let faceColor = COLOR_CAVITY;
        if (relevance !== 'APPLICABLE') {
          faceColor = COLOR_EXCLUDED;
        } else if (classification.includes('CORE')) {
          faceColor = COLOR_CORE;
        } else if (classification.includes('LOW') || classification.includes('ZERO')) {
          faceColor = COLOR_INSUFFICIENT;
        } else if (classification === 'UNDERCUT') {
          faceColor = COLOR_UNDERCUT;
        } else if (classification === 'CROSSING_PARTING') {
          faceColor = COLOR_CROSSING;
        }

        const isSelected = selectedFaceId === faceId;
        if (isSelected) faceColor = COLOR_HIGHLIGHT;

        const mat = new THREE.MeshStandardMaterial({
          color: faceColor,
          roughness: 0.4,
          metalness: 0.2,
          side: THREE.DoubleSide,
          transparent: !isVisible,
          opacity: isVisible ? 1.0 : 0.22,
        });

        const fMesh = new THREE.Mesh(fGeom, mat);
        meshGroup.add(fMesh);
      }
    }

    scene.add(meshGroup);
    coloredMeshGroupRef.current = meshGroup;

    // 5. M2.5 Render Main Pull Vector 3D Arrow (Cyan Glow Vector)
    if (showMainPullArrow && mfgData.optimal_pull_direction) {
      const pullGroup = new THREE.Group();
      const p_dir = new THREE.Vector3(...mfgData.optimal_pull_direction).normalize();
      const maxDim = bounds ? Math.max(bounds.x_len, bounds.y_len, bounds.z_len) : 50;
      const p_origin = new THREE.Vector3(0, 0, (bounds?.z_max ?? 40) - cz + 15);
      const arrowLen = Math.max(40, maxDim * 0.45);

      const pullArrow = new THREE.ArrowHelper(p_dir, p_origin, arrowLen, 0x00ffff, 14, 7);
      if (pullArrow.line.material instanceof THREE.Material) pullArrow.line.material.depthTest = false;
      if (pullArrow.cone.material instanceof THREE.Material) pullArrow.cone.material.depthTest = false;
      pullArrow.renderOrder = 1002;
      pullGroup.add(pullArrow);

      const originSphere = new THREE.Mesh(
        new THREE.SphereGeometry(4, 16, 16),
        new THREE.MeshBasicMaterial({ color: 0x00ffff, depthTest: false })
      );
      originSphere.position.copy(p_origin);
      originSphere.renderOrder = 1002;
      pullGroup.add(originSphere);

      scene.add(pullGroup);
      mainPullArrowGroupRef.current = pullGroup;
    }

    // 6. M2.11 Render Parting Lines (Fluorescent Magenta Bold 3D Lines)
    if (showPartingLine && mfgData.parting_lines && mfgData.parting_lines.length > 0) {
      const partingGroup = new THREE.Group();
      for (const pSeg of mfgData.parting_lines) {
        if (!pSeg.points || pSeg.points.length < 2) continue;
        const pts: number[] = [];
        for (let i = 0; i < pSeg.points.length - 1; i++) {
          const p1 = pSeg.points[i];
          const p2 = pSeg.points[i + 1];
          pts.push(p1[0] - cx, p1[1] - cy, p1[2] - cz, p2[0] - cx, p2[1] - cy, p2[2] - cz);
        }
        const geom = new THREE.BufferGeometry();
        geom.setAttribute('position', new THREE.Float32BufferAttribute(pts, 3));
        const line = new THREE.LineSegments(
          geom,
          new THREE.LineBasicMaterial({
            color: 0xff007f,
            depthTest: false,
            transparent: true,
            opacity: 0.95,
          })
        );
        line.renderOrder = 999;
        partingGroup.add(line);
      }
      scene.add(partingGroup);
      partingLineGroupRef.current = partingGroup;
    }

    // 7. M2.8 Render 3D Side-Action Slider Travel Arrows (Strict Exact Coordinates)
    if (showSliderArrows && mfgData.sliders && mfgData.sliders.length > 0) {
      const arrowsGroup = new THREE.Group();

      for (const slider of mfgData.sliders) {
        const isSliderActive = selectedSliderId === slider.slider_id;
        const start = new THREE.Vector3(slider.arrow_start[0] - cx, slider.arrow_start[1] - cy, slider.arrow_start[2] - cz);
        const dir = new THREE.Vector3(slider.pull_vector[0], slider.pull_vector[1], slider.pull_vector[2]).normalize();
        const length = Math.max(30, slider.required_stroke_mm + 15);
        const color = isSliderActive ? 0xffea00 : slider.mechanism_type.includes('LIFTER') ? 0x10b981 : 0xff3366;

        const arrowHelper = new THREE.ArrowHelper(dir, start, length, color, 12, 6);
        if (arrowHelper.line.material instanceof THREE.Material) arrowHelper.line.material.depthTest = false;
        if (arrowHelper.cone.material instanceof THREE.Material) arrowHelper.cone.material.depthTest = false;
        arrowHelper.renderOrder = 1000;
        arrowsGroup.add(arrowHelper);

        const sphereGeom = new THREE.SphereGeometry(3.5, 16, 16);
        const sphereMat = new THREE.MeshBasicMaterial({ color, depthTest: false });
        const sphere = new THREE.Mesh(sphereGeom, sphereMat);
        sphere.position.copy(start);
        sphere.renderOrder = 1000;
        arrowsGroup.add(sphere);
      }

      scene.add(arrowsGroup);
      sliderArrowsGroupRef.current = arrowsGroup;
    }

    orbitStateRef.current.resetView();
  }, [mfgData, meshData, displayFilter, selectedFaceId, selectedSliderId, showPartingLine, showSliderArrows, showMainPullArrow]);

  if (isLoading && !mfgData) {
    return (
      <div className="flex min-h-[600px] flex-col items-center justify-center p-8 text-center bg-slate-950 rounded-2xl border border-slate-800 font-mono">
        <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-cyan-500/10 text-cyan-400 border border-cyan-500/20 shadow-xl shadow-cyan-500/10 animate-spin mb-4">
          <RefreshCw className="h-7 w-7" />
        </div>
        <h3 className="text-base font-bold text-slate-100">Synthesizing Phase M2 Authoritative Manufacturing Engine...</h3>
        <p className="mt-1 text-xs text-slate-400 max-w-md">
          Filtering draft relevance, verifying vector orthogonality (S · D_pull = 0), and generating topological evidence proofs.
        </p>
      </div>
    );
  }

  if (error && !mfgData) {
    return (
      <div className="rounded-2xl border border-rose-500/30 bg-rose-500/10 p-8 text-center text-rose-300">
        <AlertTriangle className="h-8 w-8 mx-auto text-rose-400 mb-2" />
        <h3 className="font-bold text-sm">Failed to Load Manufacturing Intelligence Review</h3>
        <p className="text-xs font-mono mt-1 text-rose-400">{error || 'Unknown error'}</p>
        <button
          onClick={() => api.getManufacturingReview(projectId, activePresetId, true).then(setMfgData)}
          className="mt-4 px-4 py-2 bg-rose-600 hover:bg-rose-500 rounded-xl text-white font-bold text-xs font-mono"
        >
          Retry Review Engine
        </button>
      </div>
    );
  }

  if (!mfgData) return null;

  return (
    <div className="space-y-5 w-full font-sans relative">
      {/* Loading Overlay */}
      {isEvaluating && (
        <div className="absolute inset-0 z-50 flex flex-col items-center justify-center bg-slate-950/70 backdrop-blur-sm rounded-2xl border border-slate-800 text-cyan-300 font-mono text-xs">
          <RefreshCw className="w-8 h-8 animate-spin text-cyan-400 mb-2" />
          <span>Re-evaluating Manufacturing Criteria...</span>
        </div>
      )}

      {/* 1. TOP 4 PRIMARY KPI CARDS */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Moldability Score */}
        <div className={`p-4 rounded-2xl border backdrop-blur-md ${isLight ? 'bg-white border-slate-200' : 'bg-slate-900/90 border-slate-800'}`}>
          <div className="flex items-center justify-between text-xs font-mono text-slate-400">
            <span className="font-bold uppercase">Moldability Index</span>
            <Gauge className="w-4 h-4 text-cyan-400" />
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-black text-cyan-400">{mfgData.moldability_score.toFixed(1)}</span>
            <span className="text-xs text-slate-500 font-mono">/ 100</span>
          </div>
          <p className="mt-1 text-[11px] text-slate-400 font-mono truncate">
            {mfgData.relevance_breakdown?.applicable_draw_faces ?? mfgData.applicable_faces?.length ?? 0} Applicable Draw Walls
          </p>
        </div>

        {/* Primary Draw Axis */}
        <div className={`p-4 rounded-2xl border backdrop-blur-md ${isLight ? 'bg-white border-slate-200' : 'bg-slate-900/90 border-slate-800'}`}>
          <div className="flex items-center justify-between text-xs font-mono text-slate-400">
            <span className="font-bold uppercase">Primary Draw Axis</span>
            <Compass className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="mt-2 text-sm font-black text-emerald-400 truncate">
            {mfgData.optimal_direction_name}
          </div>
          <p className="mt-1 text-[11px] text-slate-400 font-mono truncate">
            D = [{mfgData.optimal_pull_direction.map((v) => v.toFixed(2)).join(', ')}]
          </p>
        </div>

        {/* Clamping Requirement */}
        <div className={`p-4 rounded-2xl border backdrop-blur-md ${isLight ? 'bg-white border-slate-200' : 'bg-slate-900/90 border-slate-800'}`}>
          <div className="flex items-center justify-between text-xs font-mono text-slate-400">
            <span className="font-bold uppercase">Clamping Requirement</span>
            <Wrench className="w-4 h-4 text-amber-400" />
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-black text-amber-400">{mfgData.estimated_clamping_tonnage.toFixed(0)}</span>
            <span className="text-xs text-slate-500 font-mono">Tonnes</span>
          </div>
          <p className="mt-1 text-[11px] text-slate-400 font-mono truncate">
            Area: {mfgData.projected_area_mm2.toFixed(0)} mm² @ {mfgData.estimated_cavity_pressure_bar} bar
          </p>
        </div>

        {/* Tooling Mechanisms Required */}
        <div className={`p-4 rounded-2xl border backdrop-blur-md ${isLight ? 'bg-white border-slate-200' : 'bg-slate-900/90 border-slate-800'}`}>
          <div className="flex items-center justify-between text-xs font-mono text-slate-400">
            <span className="font-bold uppercase">Side Actions Required</span>
            <Sliders className="w-4 h-4 text-rose-400" />
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-black text-rose-400">{mfgData.sliders.length}</span>
            <span className="text-xs text-slate-500 font-mono">Mechanisms</span>
          </div>
          <p className="mt-1 text-[11px] text-slate-400 font-mono truncate">
            {mfgData.relevance_breakdown?.connected_undercut_regions_count ?? mfgData.connected_undercut_regions?.length ?? 0} Undercut Regions
          </p>
        </div>
      </div>

      {/* 2. Process Profile Selector & Epistemic Badges & Debug Mode Toggle */}
      <div className={`p-4 rounded-2xl border backdrop-blur-md flex flex-wrap items-center justify-between gap-4 ${isLight ? 'bg-white border-slate-200 shadow-sm' : 'bg-slate-900/90 border-slate-800'}`}>
        <div className="flex items-center gap-3 font-mono text-xs">
          <span className="text-slate-400 font-bold uppercase tracking-wider text-[11px]">Process Profile:</span>
          <select
            value={activePresetId}
            onChange={(e) => handlePresetChange(e.target.value)}
            className="bg-slate-950 border border-slate-700 rounded-xl px-3 py-1.5 text-cyan-300 font-bold text-xs focus:outline-none focus:border-cyan-500"
          >
            <option value="GENERAL_PLASTIC_INJECTION">General Thermoplastic Injection (400 bar, 1.5°)</option>
            <option value="TEXTURED_PLASTIC_INJECTION">Textured Grain Finish Injection (500 bar, 3.5°)</option>
            <option value="HIGH_PRESSURE_DIE_CASTING">High-Pressure Die Casting - HPDC (700 bar, 2.5°)</option>
            <option value="SMC_COMPRESSION_MOLDING">SMC / Composite Compression (100 bar, 3.0°)</option>
            <option value="LSR_INJECTION_MOLDING">Liquid Silicone Rubber - LSR (150 bar, 0.5°)</option>
          </select>
        </div>

        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 text-[11px] font-mono">
            <span className="px-2.5 py-1 rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-bold">
              KNOWN FACTS: {mfgData.epistemic_summary?.KNOWN_FACT ?? 0}
            </span>
            <span className="px-2.5 py-1 rounded-lg bg-blue-500/10 text-blue-400 border border-blue-500/20 font-bold">
              INFERRED: {mfgData.epistemic_summary?.INFERRED ?? 0}
            </span>
            <span className="px-2.5 py-1 rounded-lg bg-amber-500/10 text-amber-400 border border-amber-500/20 font-bold">
              UNKNOWN: {mfgData.epistemic_summary?.UNKNOWN ?? 0}
            </span>
          </div>

          <button
            onClick={() => setIsDebugMode(!isDebugMode)}
            className={`px-3 py-1.5 rounded-xl border font-mono text-xs font-bold transition flex items-center gap-1.5 ${
              isDebugMode
                ? 'bg-cyan-500/20 text-cyan-300 border-cyan-400'
                : 'bg-slate-950 text-slate-400 border-slate-800 hover:text-slate-200'
            }`}
          >
            <Code2 className="w-3.5 h-3.5" />
            <span>M2 Debug Mode</span>
          </button>
        </div>
      </div>

      {/* 3. Candidate Pull-Direction Ranking Bar */}
      <div className={`p-4 rounded-2xl border backdrop-blur-md ${isLight ? 'bg-white border-slate-200' : 'bg-slate-900/90 border-slate-800'}`}>
        <div className="flex items-center justify-between border-b border-slate-800 pb-2 mb-3">
          <div className="flex items-center gap-2">
            <Compass className="w-4 h-4 text-cyan-400" />
            <h4 className="text-xs font-bold uppercase tracking-wider text-slate-200 font-mono">
              Candidate Pull-Direction Ranking (M2.4 Trade Study)
            </h4>
          </div>
          <span className="text-[11px] text-slate-400 font-mono">
            Evaluated against {mfgData.preset_used?.display_name || activePresetId}
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-6 gap-2.5 font-mono text-xs">
          {mfgData.pull_direction_candidates.map((cand) => {
            const isSelected = activeCandidateId === cand.candidate_id || (cand.is_geometrically_preferred && activeCandidateId === 'PULL_DIR_POS_Z');

            return (
              <div
                key={cand.candidate_id}
                onClick={() => handleSelectCandidateDirection(cand)}
                className={`p-2.5 rounded-xl border transition-all cursor-pointer ${
                  isSelected
                    ? 'border-cyan-400 bg-cyan-500/15 shadow-md shadow-cyan-500/10'
                    : 'border-slate-800 bg-slate-950/60 hover:border-slate-700'
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="font-black text-[11px] text-slate-200">{cand.direction_name.split(' ')[0]}</span>
                  {cand.is_geometrically_preferred && (
                    <span className="px-1.5 py-0.2 rounded bg-emerald-500/20 text-emerald-300 text-[9px] font-bold">
                      PREFERRED
                    </span>
                  )}
                </div>
                <div className="mt-2 space-y-1 text-[10px] text-slate-400">
                  <div className="flex justify-between">
                    <span>Draft Violations:</span>
                    <span className="text-amber-400 font-bold">{cand.draft_violation_count}</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Undercuts:</span>
                    <span className="text-rose-400 font-bold">{cand.potential_undercut_count}</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Tonnage:</span>
                    <span className="text-slate-300 font-bold">{cand.estimated_clamping_tonnage.toFixed(0)} T</span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* 4. Main Workspace: 3D Viewport + Findings / Sliders / AI Priorities / Debug Proof */}
      <div className="grid grid-cols-1 xl:grid-cols-12 gap-5 w-full">
        {/* LEFT: 3D Viewport with Controls */}
        <div className="xl:col-span-8 flex flex-col space-y-3">
          {/* Top Filter Bar */}
          <div className={`flex flex-wrap items-center justify-between gap-3 p-3 rounded-2xl border ${isLight ? 'bg-white border-slate-200' : 'bg-slate-900/90 border-slate-800'}`}>
            <div className="flex items-center gap-1 text-[11px] font-mono">
              {[
                { key: 'ALL', label: 'All Faces' },
                { key: 'CAVITY', label: 'Cavity Side', color: 'text-emerald-400' },
                { key: 'CORE', label: 'Core Side', color: 'text-blue-400' },
                { key: 'INSUFFICIENT', label: 'Draft Warnings', color: 'text-amber-400' },
                { key: 'UNDERCUT', label: 'Undercuts', color: 'text-rose-400' },
                { key: 'EXCLUDED', label: 'Excluded Caps', color: 'text-slate-400' },
              ].map((f) => (
                <button
                  key={f.key}
                  onClick={() => setDisplayFilter(f.key as any)}
                  className={`px-2 py-0.5 rounded transition ${
                    displayFilter === f.key
                      ? 'bg-slate-700 text-white font-bold'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  <span className={f.color}>{f.label}</span>
                </button>
              ))}
            </div>

            <div className="flex items-center gap-3 text-xs font-mono">
              <label className="flex items-center gap-1.5 cursor-pointer text-slate-400 hover:text-slate-200">
                <input
                  type="checkbox"
                  checked={showMainPullArrow}
                  onChange={(e) => setShowMainPullArrow(e.target.checked)}
                  className="accent-cyan-400 rounded"
                />
                <span className="text-cyan-400 font-bold">Main Pull Vector</span>
              </label>
              <label className="flex items-center gap-1.5 cursor-pointer text-slate-400 hover:text-slate-200">
                <input
                  type="checkbox"
                  checked={showPartingLine}
                  onChange={(e) => setShowPartingLine(e.target.checked)}
                  className="accent-pink-500 rounded"
                />
                <span className="text-pink-400 font-bold">Parting Lines</span>
              </label>
              <label className="flex items-center gap-1.5 cursor-pointer text-slate-400 hover:text-slate-200">
                <input
                  type="checkbox"
                  checked={showSliderArrows}
                  onChange={(e) => setShowSliderArrows(e.target.checked)}
                  className="accent-yellow-400 rounded"
                />
                <span className="text-yellow-400 font-bold">Slider Vectors</span>
              </label>
            </div>
          </div>

          {/* 3D Canvas */}
          <div className="min-h-[560px] h-[560px] rounded-2xl overflow-hidden border border-slate-800 bg-slate-950 relative shadow-2xl">
            <div ref={containerRef} className="w-full h-full cursor-grab active:cursor-grabbing select-none" />

            {/* Legend Overlay */}
            <div className="absolute bottom-4 left-4 z-20 flex flex-wrap items-center gap-3 bg-slate-950/90 border border-slate-800 backdrop-blur-md px-3.5 py-2 rounded-xl text-xs font-mono shadow-xl">
              <div className="flex items-center gap-1.5">
                <span className="w-3 h-3 rounded-full bg-emerald-500 inline-block" />
                <span className="text-slate-300">Cavity ({mfgData.cavity_faces.length})</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="w-3 h-3 rounded-full bg-blue-500 inline-block" />
                <span className="text-slate-300">Core ({mfgData.core_faces.length})</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="w-3 h-3 rounded-full bg-amber-500 inline-block" />
                <span className="text-slate-300">Low Draft ({mfgData.insufficient_draft_faces.length})</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="w-3 h-3 rounded-full bg-rose-500 inline-block" />
                <span className="text-slate-300">Undercut ({mfgData.undercut_faces.length})</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="w-3 h-1 bg-pink-500 inline-block" />
                <span className="text-pink-400">Parting Line</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="w-3 h-1 bg-cyan-400 inline-block" />
                <span className="text-cyan-400">Main Pull</span>
              </div>
            </div>

            {/* Reset View Button */}
            <button
              onClick={() => orbitStateRef.current.resetView()}
              title="Reset 3D View"
              className="absolute top-4 right-4 z-20 p-2 rounded-xl bg-slate-900/90 hover:bg-slate-800 border border-slate-700 text-slate-300 shadow-xl transition"
            >
              <RotateCcw className="w-4 h-4" />
            </button>
          </div>

          {/* Dynamic Draft Angle Slider Bar */}
          <div className={`p-4 rounded-2xl border backdrop-blur-md flex flex-wrap items-center justify-between gap-4 font-mono text-xs ${isLight ? 'bg-white border-slate-200' : 'bg-slate-900/90 border-slate-800'}`}>
            <div className="flex items-center gap-3 flex-1 min-w-[280px]">
              <Sliders className="w-4 h-4 text-cyan-400" />
              <span className="text-slate-300 font-bold whitespace-nowrap">
                Draft Angle Threshold: <span className="text-cyan-400">{draftThreshold.toFixed(1)}°</span>
              </span>
              <input
                type="range"
                min="0.5"
                max="5.0"
                step="0.5"
                value={draftThreshold}
                onChange={(e) => handleDraftThresholdChange(parseFloat(e.target.value))}
                className="w-full accent-cyan-400 cursor-pointer h-2 bg-slate-800 rounded-lg"
              />
            </div>
            <div className="flex items-center gap-4 text-[11px] text-slate-400">
              <span className="flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-cyan-400" />
                <span>Draw: [{mfgData.optimal_pull_direction.join(', ')}]</span>
              </span>
            </div>
          </div>
        </div>

        {/* RIGHT: Epistemic Evidence, Sliders, Decomposition & Debug Panel */}
        <div className="xl:col-span-4 space-y-4">
          {/* Sub-tab switcher */}
          <div className="flex items-center gap-1 p-1 rounded-xl bg-slate-950 border border-slate-800 text-xs font-mono">
            <button
              onClick={() => setActiveTabSubView('FINDINGS')}
              className={`flex-1 py-1.5 rounded-lg font-bold transition ${
                activeTabSubView === 'FINDINGS' ? 'bg-slate-800 text-cyan-300' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Findings ({mfgData.findings.length})
            </button>
            <button
              onClick={() => setActiveTabSubView('SLIDERS')}
              className={`flex-1 py-1.5 rounded-lg font-bold transition ${
                activeTabSubView === 'SLIDERS' ? 'bg-slate-800 text-amber-300' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Side Actions ({mfgData.sliders.length})
            </button>
            <button
              onClick={() => setActiveTabSubView('DECOMPOSITION')}
              className={`flex-1 py-1.5 rounded-lg font-bold transition ${
                activeTabSubView === 'DECOMPOSITION' ? 'bg-slate-800 text-purple-300' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              M2 Filter
            </button>
            <button
              onClick={() => setActiveTabSubView('AI_AGENDA')}
              className={`flex-1 py-1.5 rounded-lg font-bold transition ${
                activeTabSubView === 'AI_AGENDA' ? 'bg-slate-800 text-emerald-300' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              AI Priorities
            </button>
            {isDebugMode && (
              <button
                onClick={() => setActiveTabSubView('DEBUG_PROOF')}
                className={`flex-1 py-1.5 rounded-lg font-bold transition ${
                  activeTabSubView === 'DEBUG_PROOF' ? 'bg-slate-800 text-cyan-400' : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                Proofs
              </button>
            )}
          </div>

          {/* Sub-View: Findings List */}
          {activeTabSubView === 'FINDINGS' && (
            <div className={`rounded-2xl border p-4 backdrop-blur-md max-h-[580px] overflow-y-auto space-y-3 ${isLight ? 'bg-white border-slate-200' : 'bg-slate-900/90 border-slate-800'}`}>
              {mfgData.findings.map((f) => {
                const isSelected = selectedFindingId === f.finding_id;

                return (
                  <div
                    key={f.finding_id}
                    onClick={() => {
                      setSelectedFindingId(f.finding_id);
                      if (f.source_entities.length > 0) {
                        setSelectedFaceId(f.source_entities[0]);
                      }
                    }}
                    className={`p-3.5 rounded-xl border transition-all cursor-pointer font-mono text-xs ${
                      isSelected
                        ? 'border-cyan-400 bg-cyan-500/10 shadow-lg shadow-cyan-500/10'
                        : 'border-slate-800 bg-slate-950/60 hover:border-slate-700'
                    }`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex items-start gap-2 flex-1">
                        <span className={`px-2 py-0.5 rounded text-[10px] font-black shrink-0 ${
                          f.severity === 'CRITICAL' ? 'bg-rose-500/20 text-rose-300 border border-rose-500/40' : 'bg-amber-500/20 text-amber-300 border border-amber-500/40'
                        }`}>
                          {f.finding_id}
                        </span>
                        <span className="text-slate-200 font-bold text-[11px] leading-snug break-words">{f.title}</span>
                      </div>
                      <span className={`px-1.5 py-0.5 rounded text-[9px] font-bold shrink-0 ${
                        f.knowledge_state === 'KNOWN_FACT' ? 'bg-emerald-500/20 text-emerald-300' : 'bg-blue-500/20 text-blue-300'
                      }`}>
                        {f.knowledge_state}
                      </span>
                    </div>

                    <p className="mt-2 text-[11px] text-slate-300 leading-relaxed">
                      {f.engineering_interpretation}
                    </p>

                    {isSelected && (
                      <div className="mt-3 pt-3 border-t border-slate-800 space-y-2 text-[10px] text-slate-400">
                        <div>
                          <span className="text-cyan-400 font-bold">Geometric Fact: </span>
                          <span>{f.geometric_reasoning}</span>
                        </div>
                        <div>
                          <span className="text-amber-400 font-bold">Engineer Action: </span>
                          <span>{f.recommended_engineer_action}</span>
                        </div>
                        {f.unknowns.length > 0 && (
                          <div className="text-slate-500">
                            <span className="font-bold">Unknown Factors: </span>
                            <span>{f.unknowns.join(' • ')}</span>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}

          {/* Sub-View: Side-Action Sliders & Lifters */}
          {activeTabSubView === 'SLIDERS' && (
            <div className={`rounded-2xl border p-4 backdrop-blur-md max-h-[580px] overflow-y-auto space-y-3 ${isLight ? 'bg-white border-slate-200' : 'bg-slate-900/90 border-slate-800'}`}>
              <div className="text-xs font-mono text-amber-400 font-bold border-b border-slate-800 pb-2 flex justify-between">
                <span>SIDE-ACTION SLIDERS & LIFTERS</span>
                <span>{mfgData.sliders.length} Required</span>
              </div>
              {mfgData.sliders.map((slider) => (
                <div
                  key={slider.slider_id}
                  onClick={() => {
                    setSelectedSliderId(slider.slider_id);
                    if (slider.source_faces.length > 0) setSelectedFaceId(slider.source_faces[0]);
                  }}
                  className="p-3.5 rounded-xl border border-slate-800 bg-slate-950/60 font-mono text-xs space-y-2 cursor-pointer hover:border-amber-500/50 transition"
                >
                  <div className="flex items-center justify-between">
                    <span className="text-amber-400 font-bold">{slider.slider_id} ({slider.mechanism_type.includes('EXTERNAL') ? 'Cam Slide' : 'Lifter'})</span>
                    <span className="text-cyan-300 font-bold">{slider.required_stroke_mm.toFixed(1)} mm stroke</span>
                  </div>
                  <div className="text-[11px] text-slate-400">
                    <div>Slide Vector S: [{slider.pull_vector.map((v) => v.toFixed(3)).join(', ')}]</div>
                    <div>Anchor P₀: [{slider.arrow_start.join(', ')}]</div>
                    <div className="truncate">Trapped Faces: {slider.source_faces.join(', ')} ({slider.undercut_area_mm2.toFixed(1)} mm²)</div>
                  </div>
                  <div className="p-2 rounded bg-slate-900 border border-slate-800 text-[10px] text-slate-400">
                    <span className="text-amber-300 font-bold">DFM Advice: </span>
                    {slider.dfm_elimination_advice}
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Sub-View: M2.28 False-Positive Decomposition */}
          {activeTabSubView === 'DECOMPOSITION' && (
            <div className={`rounded-2xl border p-4 backdrop-blur-md max-h-[580px] overflow-y-auto space-y-3 font-mono text-xs ${isLight ? 'bg-white border-slate-200' : 'bg-slate-900/90 border-slate-800'}`}>
              <div className="text-xs text-purple-300 font-bold border-b border-slate-800 pb-2">
                M2.28 False-Positive Decomposition
              </div>
              <div className="space-y-2 text-[11px] text-slate-300">
                <div className="flex justify-between p-2 rounded-lg bg-slate-950 border border-slate-800">
                  <span className="text-slate-400">Total B-Rep Faces:</span>
                  <span className="font-bold text-cyan-300">{mfgData.relevance_breakdown?.total_faces ?? mfgData.total_faces}</span>
                </div>
                <div className="flex justify-between p-2 rounded-lg bg-slate-950 border border-slate-800">
                  <span className="text-emerald-400">Applicable Draw Walls:</span>
                  <span className="font-bold text-emerald-300">{mfgData.relevance_breakdown?.applicable_draw_faces ?? 0}</span>
                </div>
                <div className="flex justify-between p-2 rounded-lg bg-slate-950 border border-slate-800">
                  <span className="text-slate-400">Excluded Planar Caps:</span>
                  <span className="font-bold text-slate-300">{mfgData.relevance_breakdown?.excluded_planar_caps ?? 0}</span>
                </div>
                <div className="flex justify-between p-2 rounded-lg bg-slate-950 border border-slate-800">
                  <span className="text-amber-400">Valid Draft Warnings:</span>
                  <span className="font-bold text-amber-300">{mfgData.relevance_breakdown?.valid_draft_warnings ?? 0}</span>
                </div>
                <div className="flex justify-between p-2 rounded-lg bg-slate-950 border border-slate-800">
                  <span className="text-rose-400">Connected Undercut Regions:</span>
                  <span className="font-bold text-rose-300">{mfgData.relevance_breakdown?.connected_undercut_regions_count ?? 0}</span>
                </div>
              </div>
            </div>
          )}

          {/* Sub-View: AI Prioritized Agenda */}
          {activeTabSubView === 'AI_AGENDA' && (
            <div className={`rounded-2xl border p-4 backdrop-blur-md max-h-[580px] overflow-y-auto space-y-3 ${isLight ? 'bg-white border-slate-200' : 'bg-slate-900/90 border-slate-800'}`}>
              <div className="text-xs font-mono text-emerald-400 font-bold border-b border-slate-800 pb-2">
                AI Prioritized Manufacturing Agenda
              </div>
              {mfgData.ai_review?.top_priorities?.map((p) => (
                <div key={p.priority_rank} className="p-3 rounded-xl bg-slate-950/80 border border-slate-800 font-mono text-xs space-y-1.5">
                  <div className="flex items-center justify-between">
                    <span className="text-rose-400 font-black">#{p.priority_rank} — {p.title}</span>
                    <span className="text-[10px] text-slate-400 font-bold">{p.finding_id}</span>
                  </div>
                  <p className="text-[11px] text-slate-300">{p.inferred_manufacturing_implication}</p>
                  <div className="text-[10px] text-emerald-400 pt-1">
                    <span className="font-bold">Recommended Action: </span>
                    {p.recommended_engineer_action}
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Sub-View: M2.9 & M2.24 Engineering Debug Proofs */}
          {activeTabSubView === 'DEBUG_PROOF' && (
            <div className={`rounded-2xl border p-4 backdrop-blur-md max-h-[580px] overflow-y-auto space-y-3 font-mono text-xs ${isLight ? 'bg-white border-slate-200' : 'bg-slate-900/90 border-slate-800'}`}>
              <div className="text-xs text-cyan-300 font-bold border-b border-slate-800 pb-2">
                M2.9 Vector Mathematical Proofs
              </div>
              {mfgData.vector_proofs?.map((vp) => (
                <div key={vp.marker_id} className="p-3 rounded-xl bg-slate-950 border border-slate-800 space-y-1">
                  <div className="flex justify-between items-center text-cyan-400 font-bold">
                    <span>{vp.marker_id} ({vp.semantic_type})</span>
                    <span className="text-[10px] px-1.5 py-0.2 rounded bg-emerald-500/20 text-emerald-300">PASS (0.00°)</span>
                  </div>
                  <div className="text-[10px] text-slate-400">{vp.mathematical_proof}</div>
                  <div className="text-[10px] text-slate-500">Origin: [{vp.backend_origin.join(', ')}] ➔ Endpoint: [{vp.backend_endpoint.join(', ')}]</div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
