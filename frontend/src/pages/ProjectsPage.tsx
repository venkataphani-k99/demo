import React, { useState, useRef } from 'react';
import { Upload, FileCode2, Play, CheckCircle2, ArrowRight, Layers, Cpu, Sparkles, AlertCircle, Loader2 } from 'lucide-react';
import { ProjectResponse, api } from '../../lib/api';

interface ProjectsPageProps {
  onSelectProject: (projectId: string) => void;
}

export const ProjectsPage: React.FC<ProjectsPageProps> = ({ onSelectProject }) => {
  const [file, setFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState<boolean>(false);
  const [isAnalyzing, setIsAnalyzing] = useState<boolean>(false);
  const [uploadedProject, setUploadedProject] = useState<ProjectResponse | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = e.target.files?.[0];
    if (selected) {
      if (!selected.name.toLowerCase().endsWith('.step') && !selected.name.toLowerCase().endsWith('.stp')) {
        setErrorMessage('Please upload a valid 3D CAD STEP file (.step or .stp)');
        return;
      }
      setFile(selected);
      setErrorMessage(null);
    }
  };

  const handleUpload = async () => {
    if (!file) return;
    setIsUploading(true);
    setErrorMessage(null);
    try {
      const proj = await api.createProject(file);
      if (proj.status === 'analyzed') {
        // Already processed — open immediately with zero re-processing!
        onSelectProject(proj.project_id);
      } else {
        setUploadedProject(proj);
      }
    } catch (err: unknown) {
      setErrorMessage(err instanceof Error ? err.message : String(err));
    } finally {
      setIsUploading(false);
    }
  };

  const handleAnalyze = async () => {
    if (!uploadedProject) return;
    setIsAnalyzing(true);
    setErrorMessage(null);
    try {
      await api.analyzeProject(uploadedProject.project_id);
      onSelectProject(uploadedProject.project_id);
    } catch (err: unknown) {
      setErrorMessage(err instanceof Error ? err.message : String(err));
    } finally {
      setIsAnalyzing(false);
    }
  };

  return (
    <div className="mx-auto max-w-5xl px-4 py-12 sm:px-6">
      {/* Hero Header */}
      <div className="text-center space-y-3 mb-10">
        <div className="inline-flex items-center space-x-2 rounded-full border border-cyan-500/20 bg-cyan-500/10 px-3 py-1 text-xs font-semibold text-cyan-300">
          <Sparkles className="h-3.5 w-3.5" />
          <span>Automated B-Rep Dimensioning & AI Intelligence</span>
        </div>
        <h1 className="text-4xl font-extrabold tracking-tight text-white sm:text-5xl font-sans">
          Autonomous CAD Engineering Platform
        </h1>
        <p className="mx-auto max-w-2xl text-base text-slate-400">
          Upload any standard 3D STEP part to automatically extract exact B-Rep topology, recognize manufacturing features, generate TechDraw drawings, and run multimodal AI reviews.
        </p>
      </div>

      {errorMessage && (
        <div className="mb-6 rounded-xl border border-rose-500/30 bg-rose-500/10 p-4 text-sm text-rose-300 flex items-center space-x-3">
          <AlertCircle className="h-5 w-5 shrink-0 text-rose-400" />
          <span>{errorMessage}</span>
        </div>
      )}

      {/* Upload Box */}
      <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-8 backdrop-blur-xl shadow-2xl">
        <div
          onClick={() => fileInputRef.current?.click()}
          className="group relative flex flex-col items-center justify-center rounded-xl border-2 border-dashed border-slate-700 bg-slate-950/40 p-10 text-center cursor-pointer transition-all hover:border-cyan-500/50 hover:bg-slate-900/80"
        >
          <input
            ref={fileInputRef}
            type="file"
            accept=".step,.stp"
            onChange={handleFileChange}
            className="hidden"
          />

          <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-cyan-500/10 border border-cyan-500/20 text-cyan-400 mb-4 transition-transform group-hover:scale-110">
            <Upload className="h-7 w-7" />
          </div>

          <h3 className="text-base font-semibold text-white">
            {file ? file.name : 'Choose 3D CAD STEP file'}
          </h3>
          <p className="mt-1 text-xs text-slate-400">
            {file
              ? `${(file.size / 1024).toFixed(1)} KB • Click to change file`
              : 'Drag and drop your .step or .stp CAD file here, or click to browse'}
          </p>

          <div className="mt-4 flex items-center space-x-2 text-[11px] text-slate-500 font-mono">
            <span>Supported: AP203 / AP214 / AP242 STEP</span>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="mt-6 flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center space-x-2 text-xs text-slate-400">
            <Cpu className="h-4 w-4 text-cyan-400" />
            <span>Deterministic OpenCASCADE Kernel Pipeline</span>
          </div>

          <div className="flex items-center space-x-3">
            {!uploadedProject ? (
              <button
                onClick={handleUpload}
                disabled={!file || isUploading}
                className="flex items-center space-x-2 rounded-xl bg-cyan-600 px-5 py-2.5 text-sm font-bold text-white shadow-lg shadow-cyan-600/25 transition-all hover:bg-cyan-500 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isUploading ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin text-cyan-200" />
                    <span>Uploading CAD File...</span>
                  </>
                ) : (
                  <>
                    <Upload className="h-4 w-4" />
                    <span>Upload STEP</span>
                  </>
                )}
              </button>
            ) : (
              <button
                onClick={handleAnalyze}
                disabled={isAnalyzing}
                className={`flex items-center space-x-2 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 px-6 py-2.5 text-sm font-bold text-white shadow-xl shadow-cyan-500/25 transition-all hover:from-cyan-400 hover:to-blue-500 ${
                  isAnalyzing ? 'cursor-wait opacity-90 ring-2 ring-cyan-400/50 animate-pulse' : ''
                }`}
              >
                {isAnalyzing ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin text-cyan-100" />
                    <span>Analyzing CAD Topology & Mesh...</span>
                  </>
                ) : (
                  <>
                    <Play className="h-4 w-4" />
                    <span>Analyze Model</span>
                    <ArrowRight className="h-4 w-4" />
                  </>
                )}
              </button>
            )}
          </div>
        </div>

        {/* Uploaded Card Preview */}
        {uploadedProject && (
          <div className="mt-6 rounded-xl border border-emerald-500/30 bg-emerald-500/5 p-4 animate-in fade-in">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-3">
                <CheckCircle2 className="h-5 w-5 text-emerald-400" />
                <div>
                  <h4 className="text-sm font-semibold text-white font-mono">{uploadedProject.filename}</h4>
                  <p className="text-xs text-slate-400 font-mono">Project ID: {uploadedProject.project_id}</p>
                </div>
              </div>
              <span className="rounded-full bg-emerald-500/10 px-3 py-1 text-xs font-bold text-emerald-400 border border-emerald-500/20">
                Uploaded Successfully
              </span>
            </div>
          </div>
        )}
      </div>

      {/* Feature Pillars */}
      <div className="mt-12 grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-5 backdrop-blur-md">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-cyan-500/10 border border-cyan-500/20 text-cyan-400 mb-3">
            <Cpu className="h-5 w-5" />
          </div>
          <h3 className="text-sm font-bold text-white">100% Deterministic CAD</h3>
          <p className="mt-1 text-xs text-slate-400">
            Exact B-Rep topology graph extraction, geometry invariants, and zero pixel guessing.
          </p>
        </div>

        <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-5 backdrop-blur-md">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 mb-3">
            <Layers className="h-5 w-5" />
          </div>
          <h3 className="text-sm font-bold text-white">TechDraw 2D Automation</h3>
          <p className="mt-1 text-xs text-slate-400">
            Automatic Third-Angle orthographic projections and collision-free dimension placement.
          </p>
        </div>

        <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-5 backdrop-blur-md">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-amber-500/10 border border-amber-500/20 text-amber-400 mb-3">
            <Sparkles className="h-5 w-5" />
          </div>
          <h3 className="text-sm font-bold text-white">Multimodal Review Gate</h3>
          <p className="mt-1 text-xs text-slate-400">
            Claude 3.5 & Gemini 2.5 visual review validated against deterministic gatekeeper with human approval.
          </p>
        </div>
      </div>
    </div>
  );
};
