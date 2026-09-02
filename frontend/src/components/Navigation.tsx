import React, { useEffect, useState } from 'react';
import { Layers, Cpu, ArrowLeft, RefreshCw, FileCode2, ScanLine, Sun, Moon } from 'lucide-react';
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
  theme?: 'light' | 'dark';
  onToggleTheme?: () => void;
}

export const Navigation: React.FC<NavigationProps> = ({
  mode = 'uc1',
  onSwitchMode,
  currentProjectId,
  currentDrawingProjectId,
  projectName,
  onBack,
  onRefresh,
  theme = 'light',
  onToggleTheme,
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

  const isLight = theme === 'light';

  return (
    <header className={`sticky top-0 z-50 w-full border-b backdrop-blur-md transition-colors duration-200 ${
      isLight ? 'bg-white/95 border-slate-200 shadow-sm' : 'bg-slate-950/90 border-slate-800 shadow-md'
    }`}>
      <div className="mx-auto flex max-w-[1920px] items-center justify-between px-4 py-2.5 sm:px-8">
        {/* Left: logo + back + mode tabs */}
        <div className="flex items-center gap-3 min-w-0">
          {onBack && (
            <button
              id="btn-nav-back"
              onClick={onBack}
              className={`mr-1 flex items-center rounded-lg border px-3 py-1.5 text-xs font-semibold transition-all ${
                isLight
                  ? 'border-slate-200 bg-slate-100/80 hover:bg-slate-200 text-slate-700'
                  : 'border-slate-800 bg-slate-900 hover:bg-slate-800 text-slate-300 hover:text-white'
              }`}
            >
              <ArrowLeft className="mr-1.5 h-3.5 w-3.5 text-cyan-500" />
              Back
            </button>
          )}

          <div className="flex items-center space-x-2.5">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-cyan-500 to-blue-600 shadow-md shadow-cyan-500/20 text-white">
              <Layers className="h-4.5 w-4.5" />
            </div>
            <div className="hidden sm:block">
              <div className="flex items-center gap-2">
                <span className={`text-base font-black tracking-tight font-sans ${isLight ? 'text-slate-900' : 'text-white'}`}>
                  CAD Intelligence
                </span>
                <span className="rounded-full bg-cyan-500/15 px-2 py-0.5 text-[10px] font-mono font-bold text-cyan-600 dark:text-cyan-400 border border-cyan-500/30">
                  Engineering Suite
                </span>
              </div>
              <p className="text-[10px] text-slate-400 font-mono">B-Rep Understanding &amp; AI Design Review</p>
            </div>
          </div>

          {/* Use-case mode switcher */}
          {onSwitchMode && (
            <div className={`ml-4 flex items-center rounded-xl border p-0.5 gap-0.5 ${
              isLight ? 'border-slate-200 bg-slate-100' : 'border-slate-800 bg-slate-900/80'
            }`}>
              <button
                id="nav-tab-uc1"
                onClick={() => onSwitchMode('uc1')}
                className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-bold transition-all ${
                  mode === 'uc1'
                    ? 'bg-cyan-500 text-white shadow-sm font-black'
                    : isLight
                    ? 'text-slate-600 hover:text-slate-900'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                <FileCode2 className="w-3.5 h-3.5" />
                <span>3D CAD Analysis</span>
              </button>
              <button
                id="nav-tab-uc2"
                onClick={() => onSwitchMode('uc2')}
                className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-bold transition-all ${
                  mode === 'uc2'
                    ? 'bg-gradient-to-r from-violet-500 to-indigo-600 text-white shadow-sm font-black'
                    : isLight
                    ? 'text-slate-600 hover:text-slate-900'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                <ScanLine className="w-3.5 h-3.5" />
                <span>2D Drawing Ingestion</span>
              </button>
            </div>
          )}

          {projectName && (
            <div className={`hidden items-center space-x-2 border-l pl-4 md:flex ${isLight ? 'border-slate-200' : 'border-slate-800'}`}>
              <span className="text-xs text-slate-400 font-medium">Active:</span>
              <span className={`rounded-lg px-2.5 py-1 font-mono text-xs font-bold border ${
                isLight ? 'bg-slate-100 border-slate-200 text-cyan-700' : 'bg-slate-900 border-slate-800 text-cyan-300'
              }`}>
                {projectName}
              </span>
            </div>
          )}
        </div>

        {/* Right: status indicators & theme toggle */}
        <div className="flex items-center space-x-2.5 flex-shrink-0">
          {onRefresh && (
            <button
              onClick={onRefresh}
              title="Refresh project data"
              className={`flex items-center rounded-xl border p-2 text-xs font-bold transition-all ${
                isLight ? 'border-slate-200 bg-slate-100 text-slate-600 hover:bg-slate-200' : 'border-slate-800 bg-slate-900 text-slate-400 hover:text-white'
              }`}
            >
              <RefreshCw className="h-3.5 w-3.5" />
            </button>
          )}

          {/* Global Theme Toggle */}
          {onToggleTheme && (
            <button
              onClick={onToggleTheme}
              className={`px-3 py-1.5 rounded-xl border text-xs font-bold font-mono flex items-center gap-1.5 transition-all ${
                isLight
                  ? 'border-slate-200 bg-slate-100 hover:bg-slate-200 text-slate-700'
                  : 'border-slate-800 bg-slate-900 hover:bg-slate-800 text-amber-300'
              }`}
              title={`Switch to ${isLight ? 'Dark' : 'Light'} Mode`}
            >
              {isLight ? <Moon className="w-3.5 h-3.5 text-slate-700" /> : <Sun className="w-3.5 h-3.5 text-amber-400" />}
              <span>{isLight ? 'Dark' : 'Light'}</span>
            </button>
          )}

          {/* Backend Status Badge */}
          <div className={`hidden sm:flex items-center space-x-1.5 rounded-xl border px-3 py-1.5 text-xs font-mono font-bold ${
            backendStatus === 'online'
              ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400'
              : 'border-amber-500/30 bg-amber-500/10 text-amber-600 dark:text-amber-400'
          }`}>
            <span className={`h-2 w-2 rounded-full ${backendStatus === 'online' ? 'bg-emerald-500 animate-pulse' : 'bg-amber-500'}`} />
            <span>{backendStatus === 'online' ? 'API Online' : 'Connecting'}</span>
          </div>
        </div>
      </div>
    </header>
  );
};
