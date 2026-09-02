import React, { useEffect, useState } from 'react';
import { Layers, Cpu, ArrowLeft, RefreshCw, FileCode2, ScanLine } from 'lucide-react';
import { api } from '../../lib/api';

type Mode = 'uc1' | 'uc2';

interface NavigationProps {
  mode?: Mode;
  onSwitchMode?: (m: Mode) => void;
  currentProjectId?: string;
  currentDrawingProjectId?: string;
  projectName?: string;
  onBack?: () => void;
  onRefresh?: () => void;
}

export const Navigation: React.FC<NavigationProps> = ({
  mode = 'uc1',
  onSwitchMode,
  currentProjectId,
  currentDrawingProjectId,
  projectName,
  onBack,
  onRefresh,
}) => {
  const [backendStatus, setBackendStatus] = useState<'online' | 'offline' | 'checking'>('checking');

  useEffect(() => {
    let mounted = true;
    const check = async () => {
      try {
        await api.checkHealth();
        if (mounted) setBackendStatus('online');
      } catch {
        if (mounted) setBackendStatus('offline');
      }
    };
    check();
    const interval = setInterval(check, 10000);
    return () => { mounted = false; clearInterval(interval); };
  }, []);

  return (
    <header className="sticky top-0 z-50 w-full border-b border-slate-800 bg-slate-950/80 backdrop-blur-md">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3 sm:px-6">
        {/* Left: logo + back + mode tabs */}
        <div className="flex items-center gap-3 min-w-0">
          {onBack && (
            <button
              id="btn-nav-back"
              onClick={onBack}
              className="mr-1 flex items-center rounded-lg border border-slate-800 bg-slate-900/80 px-2.5 py-1.5 text-xs font-medium text-slate-300 transition-colors hover:border-slate-700 hover:bg-slate-800 hover:text-white"
            >
              <ArrowLeft className="mr-1.5 h-3.5 w-3.5 text-cyan-400" />
              Back
            </button>
          )}

          <div className="flex items-center space-x-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-cyan-500 to-blue-600 shadow-md shadow-cyan-500/20">
              <Layers className="h-5 w-5 text-white" />
            </div>
            <div className="hidden sm:block">
              <div className="flex items-center gap-2">
                <span className="text-base font-bold tracking-tight text-white font-sans">CAD Intelligence</span>
                <span className="rounded bg-cyan-500/10 px-1.5 py-0.5 text-[10px] font-semibold text-cyan-400 border border-cyan-500/20">
                  Phase 17
                </span>
              </div>
              <p className="text-[11px] text-slate-400">Deterministic B-Rep · Drawing Understanding</p>
            </div>
          </div>

          {/* Use-case mode switcher */}
          {onSwitchMode && (
            <div className="ml-4 flex items-center rounded-lg border border-slate-800 bg-slate-900/70 p-0.5 gap-0.5">
              <button
                id="nav-tab-uc1"
                onClick={() => onSwitchMode('uc1')}
                className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-semibold transition-all
                  ${mode === 'uc1'
                    ? 'bg-cyan-500/20 text-cyan-300 shadow-sm'
                    : 'text-slate-500 hover:text-slate-300'}`}
              >
                <FileCode2 className="w-3.5 h-3.5" />
                STEP → Drawing
              </button>
              <button
                id="nav-tab-uc2"
                onClick={() => onSwitchMode('uc2')}
                className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-semibold transition-all
                  ${mode === 'uc2'
                    ? 'bg-violet-500/20 text-violet-300 shadow-sm'
                    : 'text-slate-500 hover:text-slate-300'}`}
              >
                <ScanLine className="w-3.5 h-3.5" />
                Drawing → Understanding
              </button>
            </div>
          )}

          {projectName && (
            <div className="hidden items-center space-x-2 border-l border-slate-800 pl-4 md:flex">
              <span className="text-xs text-slate-400">Model:</span>
              <span className="rounded-md bg-slate-900 px-2 py-0.5 font-mono text-xs font-medium text-cyan-300 border border-slate-800">
                {projectName}
              </span>
            </div>
          )}
        </div>

        {/* Right: status indicators */}
        <div className="flex items-center space-x-2 flex-shrink-0">
          {onRefresh && (
            <button
              onClick={onRefresh}
              title="Refresh project data"
              className="flex items-center rounded-lg border border-slate-800 bg-slate-900/60 p-2 text-slate-400 hover:bg-slate-800 hover:text-slate-200"
            >
              <RefreshCw className="h-4 w-4" />
            </button>
          )}

          <div className="hidden sm:flex items-center space-x-2 rounded-full border border-slate-800 bg-slate-900/90 px-3 py-1 text-xs">
            <Cpu className="h-3.5 w-3.5 text-slate-400" />
            <span className="text-slate-400">FreeCAD/OCCT</span>
          </div>

          <div className="flex items-center space-x-1.5 rounded-full border border-slate-800 bg-slate-900/90 px-3 py-1 text-xs font-medium">
            {backendStatus === 'online' ? (
              <>
                <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
                <span className="text-emerald-400">API Online</span>
              </>
            ) : backendStatus === 'checking' ? (
              <>
                <span className="h-2 w-2 rounded-full bg-amber-400 animate-ping" />
                <span className="text-amber-400">Connecting…</span>
              </>
            ) : (
              <>
                <span className="h-2 w-2 rounded-full bg-rose-500" />
                <span className="text-rose-400">API Offline</span>
              </>
            )}
          </div>
        </div>
      </div>
    </header>
  );
};
