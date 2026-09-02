import React, { useState, useEffect } from 'react';
import { Navigation } from './components/Navigation';
import { ProjectsPage } from './pages/ProjectsPage';
import { ProjectDashboard } from './pages/ProjectDashboard';
import { DrawingProjectsPage } from './pages/DrawingProjectsPage';
import { DrawingDashboard } from './pages/DrawingDashboard';

type Mode = 'uc1' | 'uc2';
export type ThemeMode = 'light' | 'dark';

export const App: React.FC = () => {
  const [theme, setTheme] = useState<ThemeMode>(() => {
    return (localStorage.getItem('cad_theme') as ThemeMode) || 'light';
  });

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

  useEffect(() => {
    localStorage.setItem('cad_theme', theme);
    if (theme === 'dark') {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
  }, [theme]);

  const handleToggleTheme = () => {
    setTheme((prev) => (prev === 'light' ? 'dark' : 'light'));
  };

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

  const isLight = theme === 'light';

  return (
    <div className={`min-h-screen flex flex-col font-sans transition-colors duration-200 ${
      isLight ? 'bg-slate-50 text-slate-900' : 'bg-slate-950 text-slate-100'
    }`}>
      <Navigation
        mode={mode}
        onSwitchMode={handleSwitchMode}
        currentProjectId={mode === 'uc1' ? currentProjectId ?? undefined : undefined}
        currentDrawingProjectId={mode === 'uc2' ? currentDrawingProjectId ?? undefined : undefined}
        onBack={handleBack}
        theme={theme}
        onToggleTheme={handleToggleTheme}
      />

      <main className="flex-1 w-full">
        {mode === 'uc1' ? (
          currentProjectId ? (
            <ProjectDashboard projectId={currentProjectId} theme={theme} onToggleTheme={handleToggleTheme} />
          ) : (
            <ProjectsPage onSelectProject={handleSelectProject} theme={theme} />
          )
        ) : (
          currentDrawingProjectId ? (
            <DrawingDashboard projectId={currentDrawingProjectId} theme={theme} />
          ) : (
            <DrawingProjectsPage onSelectProject={handleSelectDrawingProject} theme={theme} />
          )
        )}
      </main>

      <footer className={`border-t py-4 text-center text-xs transition-colors duration-200 ${
        isLight ? 'border-slate-200 bg-white text-slate-500' : 'border-slate-900 bg-slate-950 text-slate-500'
      }`}>
        <div className="mx-auto max-w-[1920px] px-4 sm:px-8 flex flex-wrap items-center justify-between gap-4">
          <p>© 2026 CAD Intelligence Platform. Powered by FreeCAD / OpenCASCADE &amp; Multimodal AI.</p>
          <div className="flex items-center space-x-4 font-mono text-[11px]">
            <span className={isLight ? 'text-slate-600' : 'text-slate-400'}>Phase 24 Engineering Cockpit</span>
            <span>•</span>
            <span className="text-emerald-500 font-semibold">Human Approval Enforced</span>
            <span>•</span>
            <span className="text-cyan-500 font-semibold">Immutable B-Rep Ground Truth</span>
          </div>
        </div>
      </footer>
    </div>
  );
};

export default App;
