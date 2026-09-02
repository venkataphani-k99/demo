import React, { useEffect, useRef, useState, useMemo } from 'react';
import * as THREE from 'three';
import {
  RotateCw,
  RotateCcw,
  ZoomIn,
  Sparkles,
  Layers,
  Box,
  Move,
  MousePointer2,
  ListTree,
  Search,
  X,
  ChevronRight,
  Info,
  CheckCircle2,
  CircleDot,
  Hash,
} from 'lucide-react';
import { CADAnalysisResponse, CADMeshResponse, RecognizedFeature, FaceMeshData, EdgeMeshData } from '../../lib/api';

export interface DirectionalArrowProp {
  origin?: [number, number, number];
  direction: [number, number, number];
  length?: number;
  color: string;
  label?: string;
}

interface Viewer3DProps {
  projectId?: string;
  summary?: CADAnalysisResponse;
  features?: RecognizedFeature[];
  selectedFeatureId?: string | null;
  onSelectFeature?: (featureId: string | null) => void;
  meshUrl?: string;
  faceColorMap?: Record<string, string>;
  directionalArrows?: DirectionalArrowProp[];
  highlightEdges?: number[][];
  onSelectFace?: (faceId: string | null) => void;
}

export const Viewer3D: React.FC<Viewer3DProps> = ({
  projectId,
  summary,
  features = [],
  selectedFeatureId,
  onSelectFeature,
  meshUrl,
  faceColorMap,
  directionalArrows,
  highlightEdges,
  onSelectFace,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const canvasWrapperRef = useRef<HTMLDivElement>(null);
  const [wireframe, setWireframe] = useState<boolean>(false);
  const [activeView, setActiveView] = useState<string>('ISO');
  const [meshData, setMeshData] = useState<CADMeshResponse | null>(null);
  const [isLoadingMesh, setIsLoadingMesh] = useState<boolean>(false);
  const [meshLoadError, setMeshLoadError] = useState<string | null>(null);

  // Inspector & Selection Modes
  const [inspectionMode, setInspectionMode] = useState<'features' | 'topology'>('features');
  const [topologyTarget, setTopologyTarget] = useState<'faces' | 'edges'>('faces');
  const [selectedFaceId, setSelectedFaceId] = useState<string | null>(null);
  const [selectedEdgeId, setSelectedEdgeId] = useState<string | null>(null);
  const [isBrowserOpen, setIsBrowserOpen] = useState<boolean>(false);
  const [browserSearch, setBrowserSearch] = useState<string>('');
  const [browserTab, setBrowserTab] = useState<'faces' | 'edges'>('faces');

  // Hover Tooltip State
  const [hoverInfo, setHoverInfo] = useState<{
    id: string;
    type: string;
    parentFeature?: string | null;
    x: number;
    y: number;
  } | null>(null);

  // Three.js References
  const sceneRef = useRef<THREE.Scene | null>(null);
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null);
  const rendererRef = useRef<THREE.WebGLRenderer | null>(null);
  const solidMeshRef = useRef<THREE.Mesh | null>(null);
  const highlightMeshRef = useRef<THREE.Group | null>(null);
  const overlaysGroupRef = useRef<THREE.Group | null>(null);
  const edgesLineRef = useRef<THREE.LineSegments | null>(null);

  // Raycasting Group references
  const faceMeshGroupRef = useRef<THREE.Group | null>(null);
  const edgeLineGroupRef = useRef<THREE.Group | null>(null);
  const uuidToFaceRef = useRef<Map<string, string>>(new Map());
  const uuidToEdgeRef = useRef<Map<string, string>>(new Map());
  const faceToFeatureMapRef = useRef<Map<string, RecognizedFeature>>(new Map());

  // Mutable refs for mouse events
  const inspectionModeRef = useRef<'features' | 'topology'>('features');
  const topologyTargetRef = useRef<'faces' | 'edges'>('faces');
  const meshDataRef = useRef<CADMeshResponse | null>(null);

  useEffect(() => { inspectionModeRef.current = inspectionMode; }, [inspectionMode]);
  useEffect(() => { topologyTargetRef.current = topologyTarget; }, [topologyTarget]);
  useEffect(() => { meshDataRef.current = meshData; }, [meshData]);

  // Orbit / Pan Camera State
  const orbitStateRef = useRef({
    target: new THREE.Vector3(0, 0, 0),
    spherical: { radius: 170, theta: Math.PI / 4, phi: Math.PI / 3 },
    updateCamera: () => {},
    resetView: () => {},
    setPreset: (view: 'ISO' | 'FRONT' | 'TOP' | 'RIGHT' | 'BOTTOM') => {},
  });

  // 1. Build Face -> Feature mapping
  useEffect(() => {
    const map = new Map<string, RecognizedFeature>();
    if (features && Array.isArray(features)) {
      for (const feat of features) {
        const faces = feat.source_entities || feat.faces || [];
        for (const fId of faces) {
          map.set(fId, feat);
        }
      }
    }
    faceToFeatureMapRef.current = map;
  }, [features]);

  // 2. Fetch Mesh Data
  const loadMesh = React.useCallback(() => {
    if (!projectId && !meshUrl) return;
    setIsLoadingMesh(true);
    setMeshLoadError(null);
    const targetUrl = meshUrl || `http://127.0.0.1:8000/api/v1/projects/${projectId}/mesh`;
    fetch(targetUrl)
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status} (${res.statusText})`);
        return res.json();
      })
      .then((data: CADMeshResponse) => {
        if (data && data.vertices && Array.isArray(data.vertices) && data.vertices.length > 0) {
          setMeshData(data);
          setMeshLoadError(null);
        } else {
          throw new Error('Mesh geometry contains 0 vertices.');
        }
        setIsLoadingMesh(false);
      })
      .catch((err) => {
        console.error('Failed to load mesh:', err);
        setMeshLoadError(err instanceof Error ? err.message : String(err));
        setIsLoadingMesh(false);
      });
  }, [projectId, meshUrl]);

  useEffect(() => {
    loadMesh();
  }, [loadMesh]);

  // 3. Initialize Three.js Viewport
  useEffect(() => {
    if (!canvasWrapperRef.current) return;
    const canvasWrapper = canvasWrapperRef.current;
    const container = containerRef.current || canvasWrapper;

    const width = canvasWrapper.clientWidth || container.clientWidth || 800;
    const height = canvasWrapper.clientHeight || container.clientHeight || 520;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x070b19);
    sceneRef.current = scene;

    const camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 8000);
    cameraRef.current = camera;

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false, powerPreference: 'high-performance' });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    rendererRef.current = renderer;

    canvasWrapper.innerHTML = '';
    canvasWrapper.appendChild(renderer.domElement);

    // Lighting
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.9);
    scene.add(ambientLight);

    const dirLight1 = new THREE.DirectionalLight(0xe0f2fe, 1.4);
    dirLight1.position.set(160, 220, 180);
    scene.add(dirLight1);

    const dirLight2 = new THREE.DirectionalLight(0x38bdf8, 0.8);
    dirLight2.position.set(-160, -100, -140);
    scene.add(dirLight2);

    const dirLight3 = new THREE.DirectionalLight(0xa855f7, 0.4);
    dirLight3.position.set(0, 200, -200);
    scene.add(dirLight3);

    // Floor Grid
    const grid = new THREE.GridHelper(280, 28, 0x1e293b, 0x0f172a);
    grid.position.y = -40;
    scene.add(grid);

    // Highlight Group
    const highlightGroup = new THREE.Group();
    scene.add(highlightGroup);
    highlightMeshRef.current = highlightGroup;

    // Custom Overlays Group (Mold Analysis Face Colors, Arrows, Parting Lines)
    const overlaysGroup = new THREE.Group();
    scene.add(overlaysGroup);
    overlaysGroupRef.current = overlaysGroup;

    // Camera Orbit/Pan Helpers
    const target = new THREE.Vector3(0, 0, 0);
    const spherical = { radius: 170, theta: Math.PI / 4, phi: Math.PI / 3 };

    const updateCameraPosition = () => {
      camera.position.x = target.x + spherical.radius * Math.sin(spherical.phi) * Math.sin(spherical.theta);
      camera.position.y = target.y + spherical.radius * Math.cos(spherical.phi);
      camera.position.z = target.z + spherical.radius * Math.sin(spherical.phi) * Math.cos(spherical.theta);
      camera.lookAt(target);
    };
    updateCameraPosition();

    const computeMaxDim = () => {
      const mData = meshDataRef.current;
      if (!mData) return 50;
      if (mData.bounds) {
        return Math.max(mData.bounds.x_len || 0, mData.bounds.y_len || 0, mData.bounds.z_len || 0, 30);
      }
      return 50;
    };

    orbitStateRef.current.target = target;
    orbitStateRef.current.spherical = spherical;
    orbitStateRef.current.updateCamera = updateCameraPosition;

    orbitStateRef.current.resetView = () => {
      target.set(0, 0, 0);
      const maxDim = computeMaxDim();
      spherical.radius = Math.max(80, maxDim * 2.3);
      spherical.theta = Math.PI / 4;
      spherical.phi = Math.PI / 3;
      updateCameraPosition();
      setActiveView('ISO');
    };

    orbitStateRef.current.setPreset = (view: 'ISO' | 'FRONT' | 'TOP' | 'RIGHT' | 'BOTTOM') => {
      setActiveView(view);
      target.set(0, 0, 0);
      const maxDim = computeMaxDim();
      spherical.radius = Math.max(80, maxDim * 2.3);

      switch (view) {
        case 'ISO': spherical.theta = Math.PI / 4; spherical.phi = Math.PI / 3; break;
        case 'FRONT': spherical.theta = 0; spherical.phi = Math.PI / 2; break;
        case 'TOP': spherical.theta = 0; spherical.phi = 0.001; break;
        case 'RIGHT': spherical.theta = Math.PI / 2; spherical.phi = Math.PI / 2; break;
        case 'BOTTOM': spherical.theta = 0; spherical.phi = Math.PI - 0.001; break;
      }
      updateCameraPosition();
    };

    // Mouse Controls & Raycasting
    let isDragging = false;
    let mouseDownPos = { x: 0, y: 0 };
    let dragMode: 'orbit' | 'pan' = 'orbit';
    let previousMousePosition = { x: 0, y: 0 };

    const raycaster = new THREE.Raycaster();
    const getNDC = (e: MouseEvent) => {
      const rect = container.getBoundingClientRect();
      return new THREE.Vector2(
        ((e.clientX - rect.left) / rect.width) * 2 - 1,
        -((e.clientY - rect.top) / rect.height) * 2 + 1
      );
    };

    const performRaycast = (e: MouseEvent) => {
      if (!cameraRef.current) return null;
      raycaster.setFromCamera(getNDC(e), cameraRef.current);

      if (inspectionModeRef.current === 'topology' && topologyTargetRef.current === 'edges') {
        const edgeGroup = edgeLineGroupRef.current;
        if (!edgeGroup) return null;
        raycaster.params.Line = { threshold: 2.5 };
        const hits = raycaster.intersectObjects(edgeGroup.children, false);
        if (hits.length === 0) return null;
        const edgeId = uuidToEdgeRef.current.get(hits[0].object.uuid) ?? null;
        return { type: 'edge', id: edgeId };
      }

      // Default: Face Raycasting
      const faceGroup = faceMeshGroupRef.current;
      if (!faceGroup) return null;
      const hits = raycaster.intersectObjects(faceGroup.children, false);
      if (hits.length === 0) return null;
      const faceId = uuidToFaceRef.current.get(hits[0].object.uuid) ?? null;
      const parentFeat = faceId ? faceToFeatureMapRef.current.get(faceId) : null;
      return {
        type: 'face',
        id: faceId,
        parentFeatureId: parentFeat ? parentFeat.id || parentFeat.feature_id : null,
      };
    };

    const onMouseDown = (e: MouseEvent) => {
      mouseDownPos = { x: e.clientX, y: e.clientY };
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
      if (!isDragging) {
        const hit = performRaycast(e);
        if (hit && hit.id) {
          const rect = container.getBoundingClientRect();
          setHoverInfo({
            id: hit.id,
            type: hit.type,
            parentFeature: (hit as any).parentFeatureId,
            x: e.clientX - rect.left,
            y: e.clientY - rect.top,
          });
        } else {
          setHoverInfo(null);
        }
      }

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

    const onMouseUp = (e: MouseEvent) => {
      const wasDrag = Math.abs(e.clientX - mouseDownPos.x) > 4 || Math.abs(e.clientY - mouseDownPos.y) > 4;
      isDragging = false;

      if (e.button === 0 && !wasDrag) {
        const hit = performRaycast(e);
        if (inspectionModeRef.current === 'features') {
          if (hit && (hit as any).parentFeatureId && onSelectFeature) {
            onSelectFeature((hit as any).parentFeatureId);
          } else if (onSelectFeature) {
            onSelectFeature(null);
          }
        } else {
          // B-Rep Topology Mode
          if (topologyTargetRef.current === 'faces') {
            setSelectedFaceId(hit?.id ?? null);
            setSelectedEdgeId(null);
          } else {
            setSelectedEdgeId(hit?.id ?? null);
            setSelectedFaceId(null);
          }
        }
        setHoverInfo(null);
      }
    };

    const onContextMenu = (e: MouseEvent) => e.preventDefault();
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      spherical.radius = Math.max(15, Math.min(1000, spherical.radius + e.deltaY * 0.15));
      updateCameraPosition();
    };

    container.addEventListener('mousedown', onMouseDown);
    container.addEventListener('contextmenu', onContextMenu);
    container.addEventListener('mousemove', onMouseMove);
    container.addEventListener('wheel', onWheel, { passive: false });
    window.addEventListener('mousemove', onMouseMove);
    window.addEventListener('mouseup', onMouseUp);

    let animId: number;
    const animate = () => {
      animId = requestAnimationFrame(animate);
      renderer.render(scene, camera);
    };
    animate();

    const handleResize = () => {
      if (!canvasWrapper || !rendererRef.current || !cameraRef.current) return;
      const w = canvasWrapper.clientWidth || container.clientWidth || 800;
      const h = canvasWrapper.clientHeight || container.clientHeight || 520;
      if (w > 0 && h > 0) {
        cameraRef.current.aspect = w / h;
        cameraRef.current.updateProjectionMatrix();
        rendererRef.current.setSize(w, h);
      }
    };

    window.addEventListener('resize', handleResize);
    const resizeObserver = new ResizeObserver(() => {
      handleResize();
    });
    resizeObserver.observe(canvasWrapper);
    if (container !== canvasWrapper) {
      resizeObserver.observe(container);
    }

    // Trigger initial resize after paint
    setTimeout(handleResize, 50);

    return () => {
      cancelAnimationFrame(animId);
      resizeObserver.disconnect();
      container.removeEventListener('mousedown', onMouseDown);
      container.removeEventListener('contextmenu', onContextMenu);
      container.removeEventListener('mousemove', onMouseMove);
      container.removeEventListener('wheel', onWheel);
      window.removeEventListener('mousemove', onMouseMove);
      window.removeEventListener('mouseup', onMouseUp);
      window.removeEventListener('resize', handleResize);
      renderer.dispose();
    };
  }, []);

  // 4. Render Mesh Geometry & Construct Per-Face / Per-Edge Raycasting Groups
  useEffect(() => {
    if (!sceneRef.current || !meshData || !meshData.vertices || !Array.isArray(meshData.vertices) || meshData.vertices.length === 0) return;
    const scene = sceneRef.current;

    // Cleanup old meshes
    if (solidMeshRef.current) { scene.remove(solidMeshRef.current); solidMeshRef.current.geometry.dispose(); }
    if (edgesLineRef.current) { scene.remove(edgesLineRef.current); edgesLineRef.current.geometry.dispose(); }
    if (faceMeshGroupRef.current) { scene.remove(faceMeshGroupRef.current); faceMeshGroupRef.current = null; }
    if (edgeLineGroupRef.current) { scene.remove(edgeLineGroupRef.current); edgeLineGroupRef.current = null; }

    const { vertices, indices, edges, bounds, faces_map, edges_map } = meshData;

    // Robust center calculation (from bounds or directly from vertices)
    let cx = bounds?.center?.[0];
    let cy = bounds?.center?.[1];
    let cz = bounds?.center?.[2];
    let maxDim = Math.max(bounds?.x_len || 0, bounds?.y_len || 0, bounds?.z_len || 0);

    if (cx == null || cy == null || cz == null || !maxDim) {
      let minX = Infinity, maxX = -Infinity;
      let minY = Infinity, maxY = -Infinity;
      let minZ = Infinity, maxZ = -Infinity;
      for (let i = 0; i < vertices.length; i += 3) {
        const x = vertices[i], y = vertices[i + 1], z = vertices[i + 2];
        if (x < minX) minX = x; if (x > maxX) maxX = x;
        if (y < minY) minY = y; if (y > maxY) maxY = y;
        if (z < minZ) minZ = z; if (z > maxZ) maxZ = z;
      }
      cx = (minX + maxX) / 2;
      cy = (minY + maxY) / 2;
      cz = (minZ + maxZ) / 2;
      maxDim = Math.max(maxX - minX, maxY - minY, maxZ - minZ, 10);
    }

    // A. Triangulated Solid Mesh
    const centeredVerts: number[] = [];
    for (let i = 0; i < vertices.length; i += 3) {
      centeredVerts.push(vertices[i] - cx, vertices[i + 1] - cy, vertices[i + 2] - cz);
    }
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.Float32BufferAttribute(centeredVerts, 3));
    geometry.setIndex(indices);
    geometry.computeVertexNormals();

    const material = new THREE.MeshStandardMaterial({
      color: 0x38bdf8,
      roughness: 0.35,
      metalness: 0.25,
      wireframe: wireframe,
      side: THREE.DoubleSide,
    });
    const solidMesh = new THREE.Mesh(geometry, material);
    scene.add(solidMesh);
    solidMeshRef.current = solidMesh;

    // B. Sharp Boundary Wireframe
    if (edges && edges.length > 0) {
      const edgeVerts: number[] = [];
      for (const seg of edges) {
        edgeVerts.push(
          seg[0] - cx, seg[1] - cy, seg[2] - cz,
          seg[3] - cx, seg[4] - cy, seg[5] - cz
        );
      }
      const edgeGeom = new THREE.BufferGeometry();
      edgeGeom.setAttribute('position', new THREE.Float32BufferAttribute(edgeVerts, 3));
      const lineSegments = new THREE.LineSegments(
        edgeGeom,
        new THREE.LineBasicMaterial({ color: 0x0284c7, transparent: true, opacity: 0.75 })
      );
      scene.add(lineSegments);
      edgesLineRef.current = lineSegments;
    }

    // C. Per-Face Raycast Meshes
    if (faces_map) {
      const faceGroup = new THREE.Group();
      const uuidToFace = new Map<string, string>();

      for (const [faceId, fData] of Object.entries(faces_map)) {
        if (!fData.vertices || !fData.indices) continue;
        const fVerts: number[] = [];
        for (let i = 0; i < fData.vertices.length; i += 3) {
          fVerts.push(fData.vertices[i] - cx, fData.vertices[i + 1] - cy, fData.vertices[i + 2] - cz);
        }
        const fGeom = new THREE.BufferGeometry();
        fGeom.setAttribute('position', new THREE.Float32BufferAttribute(fVerts, 3));
        fGeom.setIndex(fData.indices);
        fGeom.computeVertexNormals();

        const fMesh = new THREE.Mesh(
          fGeom,
          new THREE.MeshBasicMaterial({ transparent: true, opacity: 0, side: THREE.DoubleSide, depthWrite: false })
        );
        fMesh.userData['faceId'] = faceId;
        uuidToFace.set(fMesh.uuid, faceId);
        faceGroup.add(fMesh);
      }
      scene.add(faceGroup);
      faceMeshGroupRef.current = faceGroup;
      uuidToFaceRef.current = uuidToFace;
    }

    // D. Per-Edge Raycast Line Segments
    if (edges_map) {
      const edgeGroup = new THREE.Group();
      const uuidToEdge = new Map<string, string>();

      for (const [edgeId, eData] of Object.entries(edges_map)) {
        if (!eData.segments || eData.segments.length === 0) continue;
        const eVerts: number[] = [];
        for (const seg of eData.segments) {
          eVerts.push(
            seg[0] - cx, seg[1] - cy, seg[2] - cz,
            seg[3] - cx, seg[4] - cy, seg[5] - cz
          );
        }
        const eGeom = new THREE.BufferGeometry();
        eGeom.setAttribute('position', new THREE.Float32BufferAttribute(eVerts, 3));
        const lineSeg = new THREE.LineSegments(
          eGeom,
          new THREE.LineBasicMaterial({ transparent: true, opacity: 0, depthWrite: false })
        );
        lineSeg.userData['edgeId'] = edgeId;
        uuidToEdge.set(lineSeg.uuid, edgeId);
        edgeGroup.add(lineSeg);
      }
      scene.add(edgeGroup);
      edgeLineGroupRef.current = edgeGroup;
      uuidToEdgeRef.current = uuidToEdge;
    }

    // Auto-fit Camera view on initial mesh load
    orbitStateRef.current.resetView();
  }, [meshData, wireframe]);

  // 5. Dynamic 3D Highlighting for Features, B-Rep Faces, and B-Rep Edges
  useEffect(() => {
    if (!highlightMeshRef.current || !meshData || !meshData.vertices || !Array.isArray(meshData.vertices)) return;
    const highlightGroup = highlightMeshRef.current;

    while (highlightGroup.children.length > 0) {
      const child = highlightGroup.children[0] as THREE.Mesh;
      highlightGroup.remove(child);
      child.geometry?.dispose();
    }

    const { faces_map, edges_map, bounds } = meshData;
    const cx = bounds?.center?.[0] ?? 0;
    const cy = bounds?.center?.[1] ?? 0;
    const cz = bounds?.center?.[2] ?? 0;

    // A. Engineering Feature Highlighting
    if (inspectionMode === 'features' && selectedFeatureId) {
      const feat = Array.isArray(features) ? features.find((f) => f.id === selectedFeatureId || f.feature_id === selectedFeatureId) : undefined;
      const featFaces = feat ? feat.source_entities || feat.faces || [] : [];

      for (const faceId of featFaces) {
        const fData = faces_map?.[faceId];
        if (!fData || !fData.vertices || !fData.indices) continue;

        const fVerts: number[] = [];
        for (let i = 0; i < fData.vertices.length; i += 3) {
          fVerts.push(fData.vertices[i] - cx, fData.vertices[i + 1] - cy, fData.vertices[i + 2] - cz);
        }
        const fGeom = new THREE.BufferGeometry();
        fGeom.setAttribute('position', new THREE.Float32BufferAttribute(fVerts, 3));
        fGeom.setIndex(fData.indices);
        fGeom.computeVertexNormals();

        const fMesh = new THREE.Mesh(
          fGeom,
          new THREE.MeshStandardMaterial({
            color: 0xf59e0b,
            emissive: 0xf59e0b,
            emissiveIntensity: 0.6,
            roughness: 0.1,
            metalness: 0.2,
            side: THREE.DoubleSide,
            polygonOffset: true,
            polygonOffsetFactor: -1,
            polygonOffsetUnits: -1,
          })
        );
        highlightGroup.add(fMesh);

        const edgesGeom = new THREE.EdgesGeometry(fGeom, 15);
        const edgesMesh = new THREE.LineSegments(
          edgesGeom,
          new THREE.LineBasicMaterial({ color: 0xfef08a, linewidth: 2, transparent: true, opacity: 0.95 })
        );
        highlightGroup.add(edgesMesh);
      }
    }

    // B. Single B-Rep Face Highlighting
    if (inspectionMode === 'topology' && selectedFaceId && faces_map?.[selectedFaceId]) {
      const fData = faces_map[selectedFaceId];
      if (fData.vertices && fData.indices) {
        const fVerts: number[] = [];
        for (let i = 0; i < fData.vertices.length; i += 3) {
          fVerts.push(fData.vertices[i] - cx, fData.vertices[i + 1] - cy, fData.vertices[i + 2] - cz);
        }
        const fGeom = new THREE.BufferGeometry();
        fGeom.setAttribute('position', new THREE.Float32BufferAttribute(fVerts, 3));
        fGeom.setIndex(fData.indices);
        fGeom.computeVertexNormals();

        const fMesh = new THREE.Mesh(
          fGeom,
          new THREE.MeshStandardMaterial({
            color: 0xec4899, // Vibrant Pink/Violet for individual B-Rep face
            emissive: 0xec4899,
            emissiveIntensity: 0.7,
            roughness: 0.1,
            metalness: 0.2,
            side: THREE.DoubleSide,
            polygonOffset: true,
            polygonOffsetFactor: -1,
            polygonOffsetUnits: -1,
          })
        );
        highlightGroup.add(fMesh);

        const edgesGeom = new THREE.EdgesGeometry(fGeom, 15);
        const edgesMesh = new THREE.LineSegments(
          edgesGeom,
          new THREE.LineBasicMaterial({ color: 0xfdf2f8, linewidth: 2.5, transparent: true, opacity: 1.0 })
        );
        highlightGroup.add(edgesMesh);
      }
    }

    // C. Single B-Rep Edge Highlighting
    if (inspectionMode === 'topology' && selectedEdgeId && edges_map?.[selectedEdgeId]) {
      const eData = edges_map[selectedEdgeId];
      if (eData.segments && eData.segments.length > 0) {
        const eVerts: number[] = [];
        for (const seg of eData.segments) {
          eVerts.push(
            seg[0] - cx, seg[1] - cy, seg[2] - cz,
            seg[3] - cx, seg[4] - cy, seg[5] - cz
          );
        }
        const eGeom = new THREE.BufferGeometry();
        eGeom.setAttribute('position', new THREE.Float32BufferAttribute(eVerts, 3));
        const lineSeg = new THREE.LineSegments(
          eGeom,
          new THREE.LineBasicMaterial({ color: 0xfacc15, linewidth: 3.5, transparent: true, opacity: 1.0 })
        );
        highlightGroup.add(lineSeg);
      }
    }
  }, [inspectionMode, selectedFeatureId, selectedFaceId, selectedEdgeId, meshData, features]);

  // 6. Mold Analysis Custom Overlays (Face Color Maps, Directional Arrows, Parting Lines)
  useEffect(() => {
    if (!overlaysGroupRef.current || !meshData) return;
    const overlayGroup = overlaysGroupRef.current;

    while (overlayGroup.children.length > 0) {
      const child = overlayGroup.children[0] as THREE.Object3D;
      overlayGroup.remove(child);
      if ((child as any).geometry) (child as any).geometry.dispose();
    }

    const { faces_map, bounds } = meshData;
    const cx = bounds?.center?.[0] ?? 0;
    const cy = bounds?.center?.[1] ?? 0;
    const cz = bounds?.center?.[2] ?? 0;
    const maxDim = Math.max(bounds?.x_len || 0, bounds?.y_len || 0, bounds?.z_len || 0, 40);

    // A. Face Color Map
    if (faceColorMap && faces_map) {
      for (const [faceId, colorHex] of Object.entries(faceColorMap)) {
        const fData = faces_map[faceId];
        if (!fData || !fData.vertices || !fData.indices) continue;

        const fVerts: number[] = [];
        for (let i = 0; i < fData.vertices.length; i += 3) {
          fVerts.push(fData.vertices[i] - cx, fData.vertices[i + 1] - cy, fData.vertices[i + 2] - cz);
        }
        const fGeom = new THREE.BufferGeometry();
        fGeom.setAttribute('position', new THREE.Float32BufferAttribute(fVerts, 3));
        fGeom.setIndex(fData.indices);
        fGeom.computeVertexNormals();

        const colorVal = parseInt(colorHex.replace('#', ''), 16);
        const fMesh = new THREE.Mesh(
          fGeom,
          new THREE.MeshStandardMaterial({
            color: colorVal,
            emissive: colorVal,
            emissiveIntensity: 0.35,
            roughness: 0.3,
            metalness: 0.15,
            side: THREE.DoubleSide,
            polygonOffset: true,
            polygonOffsetFactor: -1.2,
            polygonOffsetUnits: -1.2,
          })
        );
        overlayGroup.add(fMesh);
      }
    }

    // B. Directional Arrows (Mold Opening, Sliders, Lifters, Ejection)
    if (directionalArrows && directionalArrows.length > 0) {
      for (const arrow of directionalArrows) {
        const dirVec = new THREE.Vector3(arrow.direction[0], arrow.direction[1], arrow.direction[2]).normalize();
        const originVec = arrow.origin
          ? new THREE.Vector3(arrow.origin[0] - cx, arrow.origin[1] - cy, arrow.origin[2] - cz)
          : new THREE.Vector3(0, 0, 0);

        const arrowLen = arrow.length || maxDim * 0.6;
        const arrowColor = parseInt(arrow.color.replace('#', ''), 16) || 0x10b981;
        const headLen = Math.min(arrowLen * 0.3, 12);
        const headWidth = Math.min(headLen * 0.5, 6);

        const arrowHelper = new THREE.ArrowHelper(dirVec, originVec, arrowLen, arrowColor, headLen, headWidth);
        overlayGroup.add(arrowHelper);
      }
    }

    // C. Highlight Edges (Parting Lines)
    if (highlightEdges && highlightEdges.length > 0) {
      const edgeVerts: number[] = [];
      for (const seg of highlightEdges) {
        edgeVerts.push(
          seg[0] - cx, seg[1] - cy, seg[2] - cz,
          seg[3] - cx, seg[4] - cy, seg[5] - cz
        );
      }
      const edgeGeom = new THREE.BufferGeometry();
      edgeGeom.setAttribute('position', new THREE.Float32BufferAttribute(edgeVerts, 3));
      const lineSeg = new THREE.LineSegments(
        edgeGeom,
        new THREE.LineBasicMaterial({ color: 0xd946ef, linewidth: 3, transparent: true, opacity: 0.95 })
      );
      overlayGroup.add(lineSeg);
    }
  }, [faceColorMap, directionalArrows, highlightEdges, meshData]);

  // Active details lookup
  const activeFaceData: FaceMeshData | null = selectedFaceId && meshData?.faces_map ? meshData.faces_map[selectedFaceId] || null : null;
  const activeEdgeData: EdgeMeshData | null = selectedEdgeId && meshData?.edges_map ? meshData.edges_map[selectedEdgeId] || null : null;
  const activeFaceParentFeature = selectedFaceId ? faceToFeatureMapRef.current.get(selectedFaceId) : null;
  const activeEdgeParentFeature = activeEdgeData?.parent_faces
    ? activeEdgeData.parent_faces.map((f) => faceToFeatureMapRef.current.get(f)).find(Boolean)
    : null;

  // Filtered lists for Topology Browser
  const filteredFaces = useMemo(() => {
    if (!meshData?.faces_map) return [];
    const entries = Object.entries(meshData.faces_map);
    if (!browserSearch) return entries;
    const q = browserSearch.toLowerCase();
    return entries.filter(([id, f]) => id.toLowerCase().includes(q) || (f.surface_type || '').toLowerCase().includes(q));
  }, [meshData, browserSearch]);

  const filteredEdges = useMemo(() => {
    if (!meshData?.edges_map) return [];
    const entries = Object.entries(meshData.edges_map);
    if (!browserSearch) return entries;
    const q = browserSearch.toLowerCase();
    return entries.filter(([id, e]) => id.toLowerCase().includes(q) || (e.curve_type || '').toLowerCase().includes(q));
  }, [meshData, browserSearch]);

  return (
    <div className="relative flex flex-col h-full rounded-xl border border-slate-800 bg-slate-900/60 overflow-hidden shadow-2xl backdrop-blur-md">
      {/* 3D Viewport Toolbar */}
      <div className="flex flex-wrap items-center justify-between border-b border-slate-800/80 bg-slate-950/70 px-4 py-2.5 z-10 gap-2">
        {/* Left: Mode Switcher */}
        <div className="flex items-center gap-2">
          <Box className="h-4 w-4 text-cyan-400" />
          <span className="text-xs font-bold text-white uppercase tracking-wider hidden sm:inline">
            3D Viewport
          </span>

          {/* Mode Switch: Engineering Features vs B-Rep Topology */}
          <div className="flex items-center rounded-lg bg-slate-900 p-0.5 border border-slate-800">
            <button
              onClick={() => {
                setInspectionMode('features');
                setSelectedFaceId(null);
                setSelectedEdgeId(null);
              }}
              className={`rounded px-2.5 py-1 text-xs font-bold transition-all ${
                inspectionMode === 'features'
                  ? 'bg-amber-500 text-slate-950 shadow'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Engineering Features
            </button>
            <button
              onClick={() => {
                setInspectionMode('topology');
                onSelectFeature && onSelectFeature(null);
              }}
              className={`rounded px-2.5 py-1 text-xs font-bold transition-all flex items-center gap-1.5 ${
                inspectionMode === 'topology'
                  ? 'bg-pink-500 text-white shadow'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <CircleDot className="w-3.5 h-3.5" />
              B-Rep Topology
            </button>
          </div>

          {/* Secondary selector for Topology mode (Faces vs Edges) */}
          {inspectionMode === 'topology' && (
            <div className="flex items-center rounded-lg bg-slate-900 p-0.5 border border-pink-500/30">
              <button
                onClick={() => {
                  setTopologyTarget('faces');
                  setSelectedEdgeId(null);
                }}
                className={`rounded px-2 py-0.5 text-[11px] font-mono font-bold transition-all ${
                  topologyTarget === 'faces'
                    ? 'bg-pink-500/20 text-pink-300 border border-pink-500/40'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                Faces ({meshData?.stats?.face_count ?? 0})
              </button>
              <button
                onClick={() => {
                  setTopologyTarget('edges');
                  setSelectedFaceId(null);
                }}
                className={`rounded px-2 py-0.5 text-[11px] font-mono font-bold transition-all ${
                  topologyTarget === 'edges'
                    ? 'bg-yellow-500/20 text-yellow-300 border border-yellow-500/40'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                Edges ({meshData?.stats?.edge_count ?? 0})
              </button>
            </div>
          )}
        </div>

        {/* Right: View Presets & Browser Drawer Button */}
        <div className="flex items-center gap-1.5">
          {/* Topology Browser Toggle */}
          <button
            onClick={() => setIsBrowserOpen((b) => !b)}
            className={`flex items-center gap-1.5 rounded px-2.5 py-1 text-xs font-bold border transition-colors ${
              isBrowserOpen
                ? 'bg-cyan-500/20 text-cyan-300 border-cyan-500/40 shadow-sm'
                : 'bg-slate-800 text-slate-300 border-slate-700 hover:bg-slate-700'
            }`}
          >
            <ListTree className="w-3.5 h-3.5" />
            <span>Topology Browser</span>
          </button>

          {/* Camera Presets */}
          {(['ISO', 'FRONT', 'TOP', 'RIGHT', 'BOTTOM'] as const).map((view) => (
            <button
              key={view}
              onClick={() => orbitStateRef.current.setPreset(view)}
              className={`rounded px-2 py-1 text-[10px] font-mono font-bold transition-colors ${
                activeView === view
                  ? 'bg-cyan-500 text-slate-950 font-bold shadow'
                  : 'bg-slate-800 text-slate-300 hover:bg-slate-700'
              }`}
            >
              {view}
            </button>
          ))}

          {/* Reset View */}
          <button
            onClick={() => orbitStateRef.current.resetView()}
            title="Reset & Center View"
            className="rounded bg-slate-800 p-1.5 text-slate-400 hover:bg-slate-700 hover:text-white transition-colors"
          >
            <RotateCcw className="h-3.5 w-3.5" />
          </button>

          {/* Wireframe */}
          <button
            onClick={() => setWireframe(!wireframe)}
            title="Toggle Wireframe"
            className={`rounded p-1.5 transition-colors ${
              wireframe ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40' : 'bg-slate-800 text-slate-400 hover:text-white'
            }`}
          >
            <Layers className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>

      {/* Main Viewport + Optional Topology Browser Layout */}
      <div className="relative flex flex-1 w-full h-[520px] min-h-[480px] overflow-hidden">
        {/* 3D Canvas Container */}
        <div
          ref={containerRef}
          className="relative flex-1 w-full h-full select-none overflow-hidden"
        >
          {/* Three.js Canvas Element Mount Target */}
          <div
            ref={canvasWrapperRef}
            className="absolute inset-0 w-full h-full cursor-grab active:cursor-grabbing"
          />

          {/* Loading Overlay */}
          {isLoadingMesh && (
            <div className="absolute inset-0 z-30 flex flex-col items-center justify-center bg-slate-950/80 backdrop-blur-sm gap-3 transition-opacity">
              <div className="relative">
                <div className="w-12 h-12 rounded-full border-2 border-cyan-500/20 border-t-cyan-400 animate-spin" />
                <Box className="w-5 h-5 text-cyan-400 absolute inset-0 m-auto animate-pulse" />
              </div>
              <p className="text-xs font-mono font-semibold text-slate-300">
                Generating & Loading 3D Solid (FreeCAD B-Rep Mesh)...
              </p>
            </div>
          )}

          {/* Mesh Loading Error State */}
          {meshLoadError && !meshData && !isLoadingMesh && (
            <div className="absolute inset-0 z-30 flex flex-col items-center justify-center bg-slate-950/90 p-6 text-center">
              <div className="max-w-md rounded-xl border border-amber-500/30 bg-amber-500/10 p-5 space-y-3">
                <p className="text-sm font-bold text-amber-300 flex items-center justify-center gap-2">
                  <Info className="w-4 h-4 text-amber-400" />
                  3D Reconstructed Model Notice
                </p>
                <p className="text-xs text-slate-400 font-mono">
                  {meshLoadError}
                </p>
                <button
                  onClick={loadMesh}
                  className="px-4 py-2 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-white font-semibold text-xs transition-colors inline-flex items-center gap-1.5 shadow"
                >
                  <RotateCcw className="w-3.5 h-3.5" />
                  Retry Loading 3D Model
                </button>
              </div>
            </div>
          )}

          {/* Hover Tooltip */}
          {hoverInfo && (
            <div
              className="pointer-events-none absolute z-20 rounded-lg border border-pink-500/50 bg-slate-950/95 px-3 py-2 shadow-2xl backdrop-blur-md text-xs font-mono"
              style={{ left: hoverInfo.x + 14, top: hoverInfo.y - 10 }}
            >
              <div className="font-bold text-pink-300 mb-0.5">
                {hoverInfo.type === 'edge' ? 'B-Rep Edge' : 'B-Rep Face'}: <span className="text-white">{hoverInfo.id}</span>
              </div>
              {hoverInfo.parentFeature ? (
                <div className="text-emerald-400 text-[11px]">
                  Feature: <span className="font-bold">{hoverInfo.parentFeature}</span>
                </div>
              ) : (
                <div className="text-slate-500 text-[11px]">Unclassified Face</div>
              )}
              <div className="mt-1 text-[10px] text-slate-400">Click to inspect</div>
            </div>
          )}
        </div>

        {/* B-Rep Topology Browser Side Drawer */}
        {isBrowserOpen && (
          <div className="w-80 border-l border-slate-800 bg-slate-950/95 flex flex-col z-20 backdrop-blur-xl animate-in slide-in-from-right-4 duration-200">
            <div className="flex items-center justify-between p-3 border-b border-slate-800">
              <div className="flex items-center gap-2">
                <ListTree className="w-4 h-4 text-cyan-400" />
                <span className="text-xs font-bold text-slate-100 uppercase tracking-wide">B-Rep Topology Browser</span>
              </div>
              <button
                onClick={() => setIsBrowserOpen(false)}
                className="text-slate-400 hover:text-slate-200 p-1"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Counts Badge bar */}
            <div className="grid grid-cols-3 gap-1 p-2 bg-slate-900/60 border-b border-slate-800/80 text-center font-mono text-[11px]">
              <div className="rounded bg-slate-800/60 p-1">
                <span className="text-slate-400 block text-[10px]">Faces</span>
                <span className="text-pink-300 font-bold">{meshData?.stats?.face_count ?? 0}</span>
              </div>
              <div className="rounded bg-slate-800/60 p-1">
                <span className="text-slate-400 block text-[10px]">Edges</span>
                <span className="text-yellow-300 font-bold">{meshData?.stats?.edge_count ?? 0}</span>
              </div>
              <div className="rounded bg-slate-800/60 p-1">
                <span className="text-slate-400 block text-[10px]">Vertices</span>
                <span className="text-cyan-300 font-bold">{meshData?.stats?.vertex_count ?? 0}</span>
              </div>
            </div>

            {/* Sub-tabs: Faces vs Edges */}
            <div className="flex border-b border-slate-800 text-xs font-bold">
              <button
                onClick={() => setBrowserTab('faces')}
                className={`flex-1 py-2 text-center transition-colors ${
                  browserTab === 'faces'
                    ? 'text-pink-400 border-b-2 border-pink-500 bg-pink-500/5'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                Faces ({meshData?.stats?.face_count ?? 0})
              </button>
              <button
                onClick={() => setBrowserTab('edges')}
                className={`flex-1 py-2 text-center transition-colors ${
                  browserTab === 'edges'
                    ? 'text-yellow-400 border-b-2 border-yellow-500 bg-yellow-500/5'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                Edges ({meshData?.stats?.edge_count ?? 0})
              </button>
            </div>

            {/* Search Input */}
            <div className="p-2 border-b border-slate-800">
              <div className="relative">
                <Search className="w-3.5 h-3.5 absolute left-2.5 top-2.5 text-slate-500" />
                <input
                  type="text"
                  placeholder={browserTab === 'faces' ? 'Search Face ID, surface...' : 'Search Edge ID, curve...'}
                  value={browserSearch}
                  onChange={(e) => setBrowserSearch(e.target.value)}
                  className="w-full pl-8 pr-3 py-1.5 text-xs bg-slate-900 border border-slate-800 rounded-lg text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500 font-mono"
                />
              </div>
            </div>

            {/* Scrollable Item List */}
            <div className="flex-1 overflow-y-auto divide-y divide-slate-900 text-xs font-mono p-1">
              {browserTab === 'faces' ? (
                filteredFaces.map(([faceId, fData]) => {
                  const isSelected = selectedFaceId === faceId;
                  const parentFeat = faceToFeatureMapRef.current.get(faceId);
                  return (
                    <button
                      key={faceId}
                      onClick={() => {
                        setInspectionMode('topology');
                        setTopologyTarget('faces');
                        setSelectedFaceId(faceId);
                        setSelectedEdgeId(null);
                        onSelectFeature && onSelectFeature(null);
                      }}
                      className={`w-full text-left p-2 rounded flex items-center justify-between transition-colors ${
                        isSelected
                          ? 'bg-pink-500/20 border border-pink-500/40 text-pink-200'
                          : 'hover:bg-slate-900 text-slate-300'
                      }`}
                    >
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-slate-100">{faceId}</span>
                        <span className="px-1.5 py-0.5 rounded bg-slate-800 text-[10px] text-slate-300">
                          {fData.surface_type || 'Face'}
                        </span>
                      </div>
                      <div className="text-right">
                        <span className="text-[10px] text-slate-400 block">{fData.area?.toFixed(1)} mm²</span>
                        {parentFeat ? (
                          <span className="text-[9px] text-emerald-400 font-bold">
                            {parentFeat.id || parentFeat.feature_id}
                          </span>
                        ) : (
                          <span className="text-[9px] text-slate-600">Unclassified</span>
                        )}
                      </div>
                    </button>
                  );
                })
              ) : (
                filteredEdges.map(([edgeId, eData]) => {
                  const isSelected = selectedEdgeId === edgeId;
                  return (
                    <button
                      key={edgeId}
                      onClick={() => {
                        setInspectionMode('topology');
                        setTopologyTarget('edges');
                        setSelectedEdgeId(edgeId);
                        setSelectedFaceId(null);
                        onSelectFeature && onSelectFeature(null);
                      }}
                      className={`w-full text-left p-2 rounded flex items-center justify-between transition-colors ${
                        isSelected
                          ? 'bg-yellow-500/20 border border-yellow-500/40 text-yellow-200'
                          : 'hover:bg-slate-900 text-slate-300'
                      }`}
                    >
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-slate-100">{edgeId}</span>
                        <span className="px-1.5 py-0.5 rounded bg-slate-800 text-[10px] text-slate-300">
                          {eData.curve_type || 'Edge'}
                        </span>
                      </div>
                      <span className="text-[10px] text-slate-400">{eData.length?.toFixed(1)} mm</span>
                    </button>
                  );
                })
              )}
            </div>
          </div>
        )}

        {/* Loading Spinner Overlay */}
        {isLoadingMesh && (
          <div className="absolute inset-0 z-30 flex flex-col items-center justify-center bg-slate-950/85 backdrop-blur-sm">
            <div className="h-8 w-8 animate-spin rounded-full border-2 border-cyan-400 border-t-transparent" />
            <p className="mt-3 text-xs font-medium text-slate-300">
              Extracting Complete B-Rep Topology Mesh...
            </p>
          </div>
        )}

        {/* Inspector Card Overlay 1: B-Rep Face Inspector */}
        {inspectionMode === 'topology' && selectedFaceId && activeFaceData && (
          <div className="absolute top-3 right-3 z-20 w-76 rounded-xl border border-pink-500/40 bg-slate-950/95 p-4 shadow-2xl backdrop-blur-lg animate-in fade-in zoom-in-95 font-mono text-xs">
            <div className="flex items-center justify-between border-b border-slate-800 pb-2 mb-3">
              <div className="flex items-center gap-1.5">
                <CircleDot className="w-4 h-4 text-pink-400" />
                <span className="text-sm font-bold text-pink-300">{selectedFaceId}</span>
              </div>
              <span className="px-2 py-0.5 rounded bg-pink-500/10 text-pink-400 border border-pink-500/30 text-[10px] font-bold uppercase">
                {activeFaceData.surface_type || 'B-Rep Face'}
              </span>
            </div>

            <div className="space-y-2 text-slate-300">
              <div className="flex justify-between">
                <span className="text-slate-500">Surface Type:</span>
                <span className="font-bold text-slate-200">{activeFaceData.surface_type || 'Unknown'}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Area:</span>
                <span className="font-bold text-cyan-300">{activeFaceData.area?.toFixed(2)} mm²</span>
              </div>
              {activeFaceData.radius && (
                <div className="flex justify-between">
                  <span className="text-slate-500">Radius / Dia:</span>
                  <span className="font-bold text-cyan-300">R {activeFaceData.radius.toFixed(2)} mm (Ø {(activeFaceData.radius * 2).toFixed(2)})</span>
                </div>
              )}
              <div className="flex justify-between">
                <span className="text-slate-500">Center (X, Y, Z):</span>
                <span className="text-slate-300 text-[11px]">
                  ({activeFaceData.center.map((c) => c.toFixed(1)).join(', ')})
                </span>
              </div>
              {activeFaceData.normal && (
                <div className="flex justify-between">
                  <span className="text-slate-500">Normal (Nx, Ny, Nz):</span>
                  <span className="text-slate-300 text-[11px]">
                    ({activeFaceData.normal.map((n) => n.toFixed(2)).join(', ')})
                  </span>
                </div>
              )}
              <div className="flex justify-between">
                <span className="text-slate-500">Boundary Edges:</span>
                <span className="text-slate-300">{activeFaceData.boundary_edges?.length ?? 0} edges</span>
              </div>

              {/* Feature Relationship */}
              <div className="pt-2 border-t border-slate-800 space-y-1">
                <div className="flex justify-between items-center">
                  <span className="text-slate-500">Parent Feature:</span>
                  {activeFaceParentFeature ? (
                    <span className="px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 text-[10px] font-bold">
                      {activeFaceParentFeature.id || activeFaceParentFeature.feature_id}
                    </span>
                  ) : (
                    <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-400 text-[10px]">
                      None / Unclassified
                    </span>
                  )}
                </div>
                {activeFaceParentFeature && (
                  <div className="flex justify-between">
                    <span className="text-slate-500">Feature Type:</span>
                    <span className="text-emerald-400 capitalize">{activeFaceParentFeature.type}</span>
                  </div>
                )}
              </div>
            </div>

            <button
              onClick={() => setSelectedFaceId(null)}
              className="mt-3 w-full rounded-lg border border-slate-800 bg-slate-900 py-1.5 text-[11px] text-slate-400 hover:bg-slate-800 hover:text-white transition-colors"
            >
              Clear Face Selection
            </button>
          </div>
        )}

        {/* Inspector Card Overlay 2: B-Rep Edge Inspector */}
        {inspectionMode === 'topology' && selectedEdgeId && activeEdgeData && (
          <div className="absolute top-3 right-3 z-20 w-76 rounded-xl border border-yellow-500/40 bg-slate-950/95 p-4 shadow-2xl backdrop-blur-lg animate-in fade-in zoom-in-95 font-mono text-xs">
            <div className="flex items-center justify-between border-b border-slate-800 pb-2 mb-3">
              <div className="flex items-center gap-1.5">
                <Hash className="w-4 h-4 text-yellow-400" />
                <span className="text-sm font-bold text-yellow-300">{selectedEdgeId}</span>
              </div>
              <span className="px-2 py-0.5 rounded bg-yellow-500/10 text-yellow-400 border border-yellow-500/30 text-[10px] font-bold uppercase">
                {activeEdgeData.curve_type || 'B-Rep Edge'}
              </span>
            </div>

            <div className="space-y-2 text-slate-300">
              <div className="flex justify-between">
                <span className="text-slate-500">Curve Type:</span>
                <span className="font-bold text-slate-200">{activeEdgeData.curve_type}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Length:</span>
                <span className="font-bold text-yellow-300">{activeEdgeData.length?.toFixed(2)} mm</span>
              </div>
              {activeEdgeData.radius && (
                <div className="flex justify-between">
                  <span className="text-slate-500">Radius:</span>
                  <span className="font-bold text-yellow-300">R {activeEdgeData.radius.toFixed(2)} mm</span>
                </div>
              )}
              <div className="flex justify-between">
                <span className="text-slate-500">Closed Curve:</span>
                <span className="text-slate-300">{activeEdgeData.is_closed ? 'Yes' : 'No'}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Parent Faces:</span>
                <span className="text-pink-300 text-[11px]">
                  {activeEdgeData.parent_faces?.join(', ') || 'N/A'}
                </span>
              </div>

              {/* Feature Relationship */}
              <div className="pt-2 border-t border-slate-800 space-y-1">
                <div className="flex justify-between items-center">
                  <span className="text-slate-500">Parent Feature:</span>
                  {activeEdgeParentFeature ? (
                    <span className="px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 text-[10px] font-bold">
                      {activeEdgeParentFeature.id || activeEdgeParentFeature.feature_id}
                    </span>
                  ) : (
                    <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-400 text-[10px]">
                      None / Unclassified
                    </span>
                  )}
                </div>
              </div>
            </div>

            <button
              onClick={() => setSelectedEdgeId(null)}
              className="mt-3 w-full rounded-lg border border-slate-800 bg-slate-900 py-1.5 text-[11px] text-slate-400 hover:bg-slate-800 hover:text-white transition-colors"
            >
              Clear Edge Selection
            </button>
          </div>
        )}

        {/* Inspector Card Overlay 3: Engineering Feature Inspector */}
        {inspectionMode === 'features' && selectedFeatureId && (
          (() => {
            const feat = features.find((f) => f.id === selectedFeatureId || f.feature_id === selectedFeatureId);
            if (!feat) return null;
            const fid = feat.id || feat.feature_id || '';
            const featFaces = feat.source_entities || feat.faces || [];
            const featDims = feat.dimensions || feat.parameters || {};

            return (
              <div className="absolute top-3 right-3 z-20 w-76 rounded-xl border border-amber-500/40 bg-slate-950/95 p-4 shadow-2xl backdrop-blur-lg animate-in fade-in zoom-in-95 font-mono text-xs">
                <div className="flex items-center justify-between border-b border-slate-800 pb-2 mb-3">
                  <div className="flex items-center gap-1.5">
                    <Sparkles className="w-4 h-4 text-amber-400" />
                    <span className="text-sm font-bold text-amber-300">{fid}</span>
                  </div>
                  <span className="px-2 py-0.5 rounded bg-amber-500/10 text-amber-400 border border-amber-500/30 text-[10px] font-bold uppercase">
                    {feat.type}
                  </span>
                </div>

                <div className="space-y-2 text-slate-300">
                  <div className="flex justify-between">
                    <span className="text-slate-500">Confidence:</span>
                    <span className="text-emerald-400 font-bold">100% (Deterministic)</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">B-Rep Faces:</span>
                    <span className="font-bold text-amber-300">{featFaces.join(', ') || 'N/A'}</span>
                  </div>
                  {Object.entries(featDims).map(([k, v]) => (
                    <div key={k} className="flex justify-between">
                      <span className="text-slate-500 capitalize">{k.replace(/_/g, ' ')}:</span>
                      <span className="text-slate-200">{typeof v === 'number' ? `${v.toFixed(2)} mm` : String(v)}</span>
                    </div>
                  ))}
                </div>

                <button
                  onClick={() => onSelectFeature && onSelectFeature(null)}
                  className="mt-3 w-full rounded-lg border border-slate-800 bg-slate-900 py-1.5 text-[11px] text-slate-400 hover:bg-slate-800 hover:text-white transition-colors"
                >
                  Clear Feature Selection
                </button>
              </div>
            );
          })()
        )}

        {/* Floating Instruction / Orbit Help HUD */}
        <div className="absolute bottom-3 left-3 z-10 pointer-events-none rounded-lg border border-slate-800/80 bg-slate-950/85 px-3 py-2 text-[11px] text-slate-400 backdrop-blur-md shadow-lg space-y-1 font-mono">
          <div className="flex items-center space-x-2">
            <MousePointer2 className="h-3.5 w-3.5 text-pink-400" />
            <span>
              {inspectionMode === 'topology' ? (
                <>Click any <strong className="text-pink-300">{topologyTarget === 'faces' ? 'Face' : 'Edge'}</strong> to inspect B-Rep topology</>
              ) : (
                <>Click any face to inspect <strong className="text-amber-300">Engineering Feature</strong></>
              )}
            </span>
          </div>
          <div className="flex items-center space-x-2">
            <RotateCw className="h-3.5 w-3.5 text-cyan-400" />
            <span><strong className="text-white">Left-click + Drag</strong> to Orbit</span>
          </div>
          <div className="flex items-center space-x-2">
            <Move className="h-3.5 w-3.5 text-cyan-400" />
            <span><strong className="text-white">Right-click / Shift+Drag</strong> to Pan</span>
          </div>
          <div className="flex items-center space-x-2">
            <ZoomIn className="h-3.5 w-3.5 text-cyan-400" />
            <span><strong className="text-white">Scroll Wheel</strong> to Zoom</span>
          </div>
        </div>
      </div>
    </div>
  );
};
