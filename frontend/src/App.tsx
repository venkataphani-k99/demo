import React, { useState, useEffect } from 'react';
import { Navigation } from './components/Navigation';
import { ProjectsPage } from './pages/ProjectsPage';
import { ProjectDashboard } from './pages/ProjectDashboard';
import { DrawingProjectsPage } from './pages/DrawingProjectsPage';
import { DrawingDashboard } from './pages/DrawingDashboard';

type Mode = 'uc1' | 'uc2';

export const App: React.FC = () => {
  const [mode, setMode] = useState<Mode>(() => {
    const params = new URLSearchParams(window.location.search);
    return (params.get('mode') as Mode) || 'uc1';
  });

  // UC1 state
  const [currentProjectId, setCurrentProjectId] = useState<string | null>(() => {
    const params = new URLSearchParams(window.location.search);
    return params.get('project') || null;
  });

  // UC2 state
  const [currentDrawingProjectId, setCurrentDrawingProjectId] = useState<string | null>(() => {
    const params = new URLSearchParams(window.location.search);
    return params.get('drawing') || null;
  });

  const pushUrl = (updates: Record<string, string | null>) => {
    const url = new URL(window.location.href);
    Object.entries(updates).forEach(([k, v]) => {
      if (v === null) url.searchParams.delete(k);
      else url.searchParams.set(k, v);
    });
    window.history.pushState({}, '', url.toString());
  };

  const handleSwitchMode = (m: Mode) => {
    setMode(m);
    pushUrl({ mode: m, project: null, drawing: null });
    setCurrentProjectId(null);
    setCurrentDrawingProjectId(null);
  };

  // UC1 handlers
  const handleSelectProject = (id: string) => {
    setCurrentProjectId(id);
    pushUrl({ project: id });
  };
  const handleBackToProjects = () => {
    setCurrentProjectId(null);
    pushUrl({ project: null });
  };

  // UC2 handlers
  const handleSelectDrawingProject = (id: string) => {
    setCurrentDrawingProjectId(id);
    pushUrl({ drawing: id });
  };
  const handleBackToDrawingProjects = () => {
    setCurrentDrawingProjectId(null);
    pushUrl({ drawing: null });
  };

  const isBackNeeded =
    (mode === 'uc1' && !!currentProjectId) ||
    (mode === 'uc2' && !!currentDrawingProjectId);

  const handleBack = isBackNeeded
    ? mode === 'uc1' ? handleBackToProjects : handleBackToDrawingProjects
    : undefined;

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col">
      <Navigation
        mode={mode}
        onSwitchMode={handleSwitchMode}
        currentProjectId={mode === 'uc1' ? currentProjectId ?? undefined : undefined}
        currentDrawingProjectId={mode === 'uc2' ? currentDrawingProjectId ?? undefined : undefined}
        onBack={handleBack}
      />

      <main className="flex-1">
        {mode === 'uc1' ? (
          currentProjectId ? (
            <ProjectDashboard projectId={currentProjectId} />
          ) : (
            <ProjectsPage onSelectProject={handleSelectProject} />
          )
        ) : (
          currentDrawingProjectId ? (
            <DrawingDashboard projectId={currentDrawingProjectId} />
          ) : (
            <DrawingProjectsPage onSelectProject={handleSelectDrawingProject} />
          )
        )}
      </main>

      <footer className="border-t border-slate-900 bg-slate-950 py-6 text-center text-xs text-slate-500">
        <div className="mx-auto max-w-7xl px-4 flex flex-wrap items-center justify-between gap-4">
          <p>© 2026 CAD Intelligence Platform. Powered by FreeCAD / OpenCASCADE & Multimodal AI.</p>
          <div className="flex items-center space-x-4">
            <span className="font-mono text-slate-400">Phase 17 UC1+UC2</span>
            <span>•</span>
            <span className="text-emerald-400">Human Approval Enforced</span>
            <span>•</span>
            <span className="text-violet-400">No Auto CAD Mutation</span>
          </div>
        </div>
      </footer>
    </div>
  );
};

export default App;
