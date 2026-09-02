import React, { useState, useEffect, useRef } from 'react';
import {
  Upload, FileImage, FileText, Layers, Sparkles, AlertCircle,
  CheckCircle2, ArrowRight, Cpu, ScanLine, Eye
} from 'lucide-react';
import { drawingApi, DrawingProjectMeta } from '../../lib/drawingApi';

interface DrawingProjectsPageProps {
  onSelectProject: (projectId: string) => void;
}

const ACCEPTED_FORMATS = ['.pdf', '.png', '.jpg', '.jpeg', '.svg'];
const MIME_ICONS: Record<string, React.ReactNode> = {
  'application/pdf': <FileText className="w-8 h-8 text-red-400" />,
  'image/png': <FileImage className="w-8 h-8 text-blue-400" />,
  'image/jpeg': <FileImage className="w-8 h-8 text-amber-400" />,
  'image/svg+xml': <Layers className="w-8 h-8 text-emerald-400" />,
};

function formatBytes(b: number): string {
  if (b < 1024) return `${b} B`;
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)} KB`;
  return `${(b / 1024 / 1024).toFixed(2)} MB`;
}

export const DrawingProjectsPage: React.FC<DrawingProjectsPageProps> = ({ onSelectProject }) => {
  const [file, setFile] = useState<File | null>(null);
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [project, setProject] = useState<DrawingProjectMeta | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [recentProjects, setRecentProjects] = useState<DrawingProjectMeta[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const list = await drawingApi.listProjects();
        if (!cancelled) setRecentProjects(list);
      } catch {
        // ignore
      }
    })();
    return () => { cancelled = true; };
  }, []);

  const validateFile = (f: File): string | null => {
    const ext = f.name.toLowerCase().match(/\.[^.]+$/)?.[0] ?? '';
    if (!ACCEPTED_FORMATS.includes(ext)) {
      return `Unsupported format '${ext}'. Accepted: ${ACCEPTED_FORMATS.join(', ')}`;
    }
    return null;
  };

  const handleFileSelect = (f: File) => {
    const err = validateFile(f);
    if (err) { setError(err); return; }
    setFile(f);
    setError(null);
    setProject(null);
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (f) handleFileSelect(f);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const f = e.dataTransfer.files[0];
    if (f) handleFileSelect(f);
  };

  const handleUpload = async () => {
    if (!file) return;
    setUploading(true);
    setError(null);
    try {
      const proj = await drawingApi.createDrawingProject(file);
      setProject(proj);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setUploading(false);
    }
  };

  const handleAnalyze = async () => {
    if (!project) return;
    setAnalyzing(true);
    setError(null);
    try {
      await drawingApi.analyzeDrawingProject(project.project_id);
      onSelectProject(project.project_id);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setAnalyzing(false);
    }
  };

  const mimeType = file?.type || '';
  const mimeIcon = MIME_ICONS[mimeType] ?? <FileImage className="w-8 h-8 text-slate-400" />;

  return (
    <div className="mx-auto max-w-4xl px-4 py-12 sm:px-6">
      {/* Hero */}
      <div className="text-center space-y-3 mb-10">
        <div className="inline-flex items-center gap-2 rounded-full border border-violet-500/30 bg-violet-500/10 px-4 py-1.5 text-xs font-semibold text-violet-300 mb-2">
          <Cpu className="w-3.5 h-3.5" />
          Phase 17 — Use Case 2
        </div>
        <h1 className="text-4xl font-black tracking-tight text-slate-50">
          2D Drawing → Structured Understanding
        </h1>
        <p className="text-slate-400 text-base max-w-2xl mx-auto">
          Upload an engineering drawing (PDF, PNG, or SVG). Both Claude and Gemini visually
          analyze the actual image — views, dimensions, entities, and title block are extracted
          with full source traceability. No CAD geometry is generated.
        </p>
      </div>

      {/* Capabilities row */}
      <div className="grid grid-cols-3 gap-4 mb-10">
        {[
          { icon: <ScanLine className="w-5 h-5 text-violet-400" />, label: 'View Detection', desc: 'FRONT, TOP, ISO, SECTION …' },
          { icon: <Eye className="w-5 h-5 text-cyan-400" />, label: 'Dimension Extraction', desc: 'Ø, R, linear, angle, thread' },
          { icon: <Sparkles className="w-5 h-5 text-emerald-400" />, label: 'Dual-Model Consensus', desc: 'Claude + Gemini compared' },
        ].map((cap) => (
          <div key={cap.label} className="rounded-xl border border-slate-800 bg-slate-900/60 p-4 text-center">
            <div className="flex justify-center mb-2">{cap.icon}</div>
            <div className="text-sm font-semibold text-slate-200">{cap.label}</div>
            <div className="text-xs text-slate-500 mt-1">{cap.desc}</div>
          </div>
        ))}
      </div>

      {/* Upload zone */}
      <div
        className={`relative rounded-2xl border-2 border-dashed transition-all duration-200 cursor-pointer
          ${dragging ? 'border-violet-500 bg-violet-500/10' : 'border-slate-700 bg-slate-900/40 hover:border-slate-600 hover:bg-slate-900/60'}`}
        onClick={() => fileInputRef.current?.click()}
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept={ACCEPTED_FORMATS.join(',')}
          className="hidden"
          onChange={handleInputChange}
        />
        <div className="flex flex-col items-center justify-center py-14 space-y-4 pointer-events-none">
          {file ? (
            <>
              {mimeIcon}
              <div className="text-center">
                <p className="text-slate-100 font-semibold text-lg">{file.name}</p>
                <p className="text-slate-400 text-sm mt-1">{formatBytes(file.size)} • {file.type || 'unknown type'}</p>
              </div>
            </>
          ) : (
            <>
              <Upload className="w-12 h-12 text-slate-600" />
              <div className="text-center">
                <p className="text-slate-300 font-medium">Drop a drawing here or click to browse</p>
                <p className="text-slate-500 text-sm mt-1">PDF · PNG · JPEG · SVG</p>
              </div>
            </>
          )}
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="mt-4 flex items-start gap-3 rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3">
          <AlertCircle className="w-4 h-4 text-red-400 mt-0.5 flex-shrink-0" />
          <p className="text-sm text-red-300">{error}</p>
        </div>
      )}

      {/* Actions */}
      <div className="mt-6 flex flex-col sm:flex-row gap-3 items-center justify-center">
        {!project ? (
          <button
            id="btn-upload-drawing"
            disabled={!file || uploading}
            onClick={handleUpload}
            className="flex items-center gap-2 rounded-xl bg-violet-600 hover:bg-violet-500 disabled:opacity-40 disabled:cursor-not-allowed text-white font-semibold px-8 py-3 transition-all"
          >
            {uploading ? (
              <><span className="animate-spin inline-block w-4 h-4 border-2 border-white/30 border-t-white rounded-full" />Uploading…</>
            ) : (
              <><Upload className="w-4 h-4" />Upload Drawing</>
            )}
          </button>
        ) : (
          <div className="w-full space-y-4">
            {/* Project created card */}
            <div className="flex items-center gap-3 rounded-xl border border-emerald-500/30 bg-emerald-500/10 px-4 py-3">
              <CheckCircle2 className="w-5 h-5 text-emerald-400 flex-shrink-0" />
              <div className="flex-1 min-w-0">
                <p className="text-sm font-semibold text-emerald-300">Drawing project created</p>
                <p className="text-xs text-slate-400 font-mono mt-0.5 truncate">{project.project_id}</p>
              </div>
            </div>

            <button
              id="btn-analyze-drawing"
              disabled={analyzing}
              onClick={handleAnalyze}
              className="w-full flex items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-violet-600 to-cyan-600 hover:from-violet-500 hover:to-cyan-500 disabled:opacity-40 disabled:cursor-not-allowed text-white font-bold px-8 py-4 transition-all text-base shadow-lg shadow-violet-900/30"
            >
              {analyzing ? (
                <>
                  <span className="animate-spin inline-block w-5 h-5 border-2 border-white/30 border-t-white rounded-full" />
                  Running Claude + Gemini Visual Analysis (~30s)…
                </>
              ) : (
                <>
                  <Sparkles className="w-5 h-5" />
                  Analyze Drawing with Claude + Gemini
                  <ArrowRight className="w-4 h-4" />
                </>
              )}
            </button>
          </div>
        )}
      </div>

      {/* Recent Drawing Projects */}
      {recentProjects.length > 0 && (
        <div className="mt-12 space-y-3">
          <h3 className="text-sm font-bold text-slate-300 uppercase tracking-wider flex items-center gap-2">
            <ScanLine className="w-4 h-4 text-violet-400" />
            Existing Drawing Projects ({recentProjects.length})
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {recentProjects.map((p) => (
              <button
                key={p.project_id}
                onClick={() => onSelectProject(p.project_id)}
                className="text-left rounded-xl border border-slate-800 bg-slate-900/60 hover:bg-slate-800/80 hover:border-violet-500/50 p-4 transition-all flex items-center justify-between group shadow-md"
              >
                <div className="min-w-0 flex-1 pr-3">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="font-semibold text-slate-100 text-sm truncate">{p.filename}</span>
                    <span className={`text-[10px] font-semibold px-2 py-0.5 rounded border ${
                      p.status === 'ANALYZED'
                        ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300'
                        : 'border-slate-700 bg-slate-800 text-slate-400'
                    }`}>
                      {p.status}
                    </span>
                  </div>
                  <p className="font-mono text-xs text-slate-500 truncate">{p.project_id}</p>
                </div>
                <ArrowRight className="w-4 h-4 text-slate-500 group-hover:text-violet-400 group-hover:translate-x-0.5 transition-all flex-shrink-0" />
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Footer note */}
      <p className="mt-8 text-center text-xs text-slate-600">
        The original drawing file is preserved as immutable source evidence and never modified.
      </p>
    </div>
  );
};
