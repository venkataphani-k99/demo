import React, { useState, useMemo } from 'react';
import {
  Sparkles, Cpu, CheckCircle2, ChevronRight, ChevronDown, Search,
  Filter, Layers, ArrowRight, ShieldCheck, Box, Compass
} from 'lucide-react';
import { RecognizedFeature } from '../../lib/api';

interface FeaturesTableProps {
  features: RecognizedFeature[];
  selectedFeatureId: string | null;
  onSelectFeature: (featureId: string) => void;
  theme?: 'light' | 'dark';
}

export const FeaturesTable: React.FC<FeaturesTableProps> = ({
  features,
  selectedFeatureId,
  onSelectFeature,
  theme = 'dark',
}) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedType, setSelectedType] = useState<string>('ALL');
  const [expandedRow, setExpandedRow] = useState<string | null>(null);

  const isLight = theme === 'light';
  const bgCard = isLight ? 'bg-white border-slate-200/90 shadow-md' : 'bg-slate-900/60 border-slate-800 shadow-xl';
  const bgHeader = isLight ? 'bg-slate-50/90 border-slate-200' : 'bg-slate-950/80 border-slate-800';
  const textHeading = isLight ? 'text-slate-900' : 'text-white';
  const textMuted = isLight ? 'text-slate-500' : 'text-slate-400';
  const bgInput = isLight ? 'bg-white border-slate-300 text-slate-900 placeholder-slate-400' : 'bg-slate-900/90 border-slate-700 text-white placeholder-slate-500';
  const bgThead = isLight ? 'bg-slate-100/90 text-slate-600 border-slate-200' : 'bg-slate-950/95 text-slate-400 border-slate-800';
  const bgRowHover = isLight ? 'hover:bg-slate-50 text-slate-700' : 'hover:bg-slate-800/40 text-slate-300';
  const borderDivider = isLight ? 'divide-slate-200' : 'divide-slate-800/60';

  // Extract unique feature types
  const featureTypes = useMemo(() => {
    const types = new Set<string>();
    features.forEach((f) => {
      if (f.type) types.add(f.type);
    });
    return Array.from(types).sort();
  }, [features]);

  // Filter features based on search & type
  const filteredFeatures = useMemo(() => {
    return features.filter((f) => {
      const featId = f.id || (f as unknown as { feature_id: string }).feature_id || '';
      const featType = f.type || '';
      const faces = (f.source_entities || (f as unknown as { faces: string[] }).faces || []).join(' ');

      const matchesSearch =
        searchTerm === '' ||
        featId.toLowerCase().includes(searchTerm.toLowerCase()) ||
        featType.toLowerCase().includes(searchTerm.toLowerCase()) ||
        faces.toLowerCase().includes(searchTerm.toLowerCase());

      const matchesType = selectedType === 'ALL' || featType === selectedType;

      return matchesSearch && matchesType;
    });
  }, [features, searchTerm, selectedType]);

  const formatParams = (params?: Record<string, number | string | boolean | number[]>) => {
    if (!params) return 'N/A';
    if (params.bore_diameter !== undefined && params.counterbore_diameter !== undefined) {
      return `Ø${Number(params.bore_diameter).toFixed(1)} / Ø${Number(params.counterbore_diameter).toFixed(1)} mm`;
    }
    if (params.diameter !== undefined) {
      return `Ø${Number(params.diameter).toFixed(1)} mm`;
    }
    if (params.radius !== undefined) {
      return `R${Number(params.radius).toFixed(1)} mm`;
    }
    if (params.depth !== undefined) {
      return `Depth: ${Number(params.depth).toFixed(1)} mm`;
    }
    if (params.length !== undefined) {
      return `Length: ${Number(params.length).toFixed(1)} mm`;
    }
    return (
      Object.entries(params)
        .slice(0, 2)
        .map(([k, v]) => `${k}: ${typeof v === 'number' ? v.toFixed(1) : v}`)
        .join(', ') || 'N/A'
    );
  };

  const toggleExpand = (featId: string) => {
    setExpandedRow((prev) => (prev === featId ? null : featId));
  };

  return (
    <div className={`rounded-xl border overflow-hidden backdrop-blur-md flex flex-col ${bgCard}`}>
      {/* Table Header & Controls */}
      <div className={`border-b px-4 py-3 space-y-3 ${bgHeader}`}>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center space-x-2">
            <Cpu className="h-4 w-4 text-cyan-500" />
            <h3 className={`text-sm font-bold ${textHeading}`}>Recognized Engineering Features</h3>
            <span className="rounded-full bg-cyan-500/10 px-2.5 py-0.5 text-xs font-mono font-bold text-cyan-600 dark:text-cyan-300 border border-cyan-500/20">
              {filteredFeatures.length} / {features.length} Features
            </span>
          </div>

          <div className={`flex items-center space-x-2 text-xs ${textMuted}`}>
            <ShieldCheck className="h-3.5 w-3.5 text-emerald-500" />
            <span className="font-mono text-emerald-600 dark:text-emerald-300 font-bold">100% Deterministic OCCT Engine</span>
          </div>
        </div>

        {/* Search & Filter Pills */}
        <div className="flex flex-wrap items-center justify-between gap-3 pt-1">
          {/* Search Box */}
          <div className="relative flex-1 min-w-[200px] max-w-sm">
            <Search className={`absolute left-2.5 top-2.5 h-3.5 w-3.5 ${textMuted}`} />
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Search feature ID, type, face..."
              className={`w-full rounded-lg border pl-8 pr-3 py-1.5 text-xs focus:border-cyan-500 focus:outline-none focus:ring-1 focus:ring-cyan-500 font-mono transition ${bgInput}`}
            />
          </div>

          {/* Feature Type Filter Pills */}
          <div className="flex items-center flex-wrap gap-1.5">
            <button
              onClick={() => setSelectedType('ALL')}
              className={`rounded-lg px-2.5 py-1 text-xs font-mono font-bold transition-colors ${
                selectedType === 'ALL'
                  ? 'bg-cyan-500 text-white shadow-sm shadow-cyan-500/25'
                  : isLight ? 'bg-slate-100 hover:bg-slate-200 text-slate-600 border border-slate-200' : 'bg-slate-800/80 text-slate-400 hover:text-white border border-slate-700'
              }`}
            >
              All ({features.length})
            </button>
            {featureTypes.map((t) => {
              const count = features.filter((f) => f.type === t).length;
              return (
                <button
                  key={t}
                  onClick={() => setSelectedType(t)}
                  className={`rounded-lg px-2 py-1 text-xs font-mono font-medium transition-colors ${
                    selectedType === t
                      ? 'bg-cyan-500 text-white shadow-sm shadow-cyan-500/25'
                      : isLight ? 'bg-slate-100 hover:bg-slate-200 text-slate-600 border border-slate-200' : 'bg-slate-800/60 text-slate-400 hover:text-white border border-slate-700/60'
                  }`}
                >
                  {t} ({count})
                </button>
              );
            })}
          </div>
        </div>
      </div>

      {/* Table Container */}
      <div className="overflow-x-auto max-h-[560px]">
        <table className="w-full text-left text-xs">
          <thead className={`sticky top-0 border-b z-10 ${bgThead}`}>
            <tr>
              <th className="py-2.5 px-3 font-bold">Feature ID</th>
              <th className="py-2.5 px-3 font-bold">Type</th>
              <th className="py-2.5 px-3 font-bold">Size / Dimensions</th>
              <th className="py-2.5 px-3 font-bold">Axis / Location</th>
              <th className="py-2.5 px-3 font-bold">B-Rep Faces</th>
              <th className="py-2.5 px-3 font-bold">Confidence</th>
              <th className="py-2.5 px-3 font-bold">Status</th>
              <th className="py-2.5 px-3 font-bold text-right">Details</th>
            </tr>
          </thead>
          <tbody className={`divide-y font-mono ${borderDivider}`}>
            {filteredFeatures.length === 0 ? (
              <tr>
                <td colSpan={8} className="py-12 text-center text-slate-500">
                  No engineering features match your filter criteria.
                </td>
              </tr>
            ) : (
              filteredFeatures.map((feature) => {
                const featId = feature.id || (feature as unknown as { feature_id: string }).feature_id;
                const isSelected = selectedFeatureId === featId;
                const isExpanded = expandedRow === featId;
                const faces = feature.source_entities || (feature as unknown as { faces: string[] }).faces || [];
                const dims = feature.dimensions || (feature as unknown as { parameters: Record<string, number> }).parameters || {};
                const axis = feature.axis || [];
                const pos = feature.position || [];
                const confidence = feature.confidence ?? 1.0;

                return (
                  <React.Fragment key={featId}>
                    <tr
                      onClick={() => onSelectFeature(featId)}
                      className={`cursor-pointer transition-colors ${
                        isSelected
                          ? 'bg-cyan-500/15 text-cyan-200 border-l-2 border-cyan-400'
                          : 'hover:bg-slate-800/40 text-slate-300'
                      }`}
                    >
                      {/* Feature ID */}
                      <td className="py-2.5 px-3 font-bold text-white flex items-center space-x-1.5">
                        <Sparkles className="h-3.5 w-3.5 text-cyan-400 flex-shrink-0" />
                        <span>{featId}</span>
                      </td>

                      {/* Feature Type */}
                      <td className="py-2.5 px-3">
                        <span className="rounded bg-indigo-500/10 px-2 py-0.5 text-[11px] text-indigo-300 border border-indigo-500/20">
                          {feature.type}
                        </span>
                      </td>

                      {/* Size / Dimensions */}
                      <td className="py-2.5 px-3 text-cyan-300 font-bold">
                        {formatParams(dims)}
                      </td>

                      {/* Axis / Location */}
                      <td className="py-2.5 px-3 text-[11px] text-slate-400">
                        {axis.length === 3 ? (
                          <span>[{axis.map((n) => Number(n).toFixed(0)).join(', ')}]</span>
                        ) : pos.length === 3 ? (
                          <span>({pos.map((n) => Number(n).toFixed(1)).join(', ')})</span>
                        ) : (
                          <span className="text-slate-600">—</span>
                        )}
                      </td>

                      {/* B-Rep Faces */}
                      <td className="py-2.5 px-3">
                        <div className="flex flex-wrap gap-1">
                          {faces.slice(0, 3).map((face) => (
                            <span
                              key={face}
                              className="rounded bg-slate-800 px-1.5 py-0.5 text-[10px] text-slate-400 border border-slate-700"
                            >
                              {face}
                            </span>
                          ))}
                          {faces.length > 3 && (
                            <span className="text-[10px] text-slate-500">+{faces.length - 3}</span>
                          )}
                        </div>
                      </td>

                      {/* Confidence */}
                      <td className="py-2.5 px-3 text-[11px]">
                        <span className="text-emerald-400 font-bold">{(confidence * 100).toFixed(0)}%</span>
                      </td>

                      {/* Status */}
                      <td className="py-2.5 px-3">
                        <span className="inline-flex items-center space-x-1 rounded-full bg-emerald-500/10 px-2 py-0.5 text-[10px] font-medium text-emerald-400 border border-emerald-500/20">
                          <CheckCircle2 className="h-3 w-3" />
                          <span>Confirmed</span>
                        </span>
                      </td>

                      {/* Expand Details Button */}
                      <td className="py-2.5 px-3 text-right">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            toggleExpand(featId);
                          }}
                          className="text-cyan-400 hover:text-cyan-200 transition-colors p-1"
                          title="Toggle Detailed Parameter Drawer"
                        >
                          {isExpanded ? (
                            <ChevronDown className="h-4 w-4" />
                          ) : (
                            <ChevronRight className="h-4 w-4" />
                          )}
                        </button>
                      </td>
                    </tr>

                    {/* Expandable Parameter & B-Rep Entity Drawer */}
                    {isExpanded && (
                      <tr className="bg-slate-950/80 border-b border-cyan-500/20">
                        <td colSpan={8} className="p-4 space-y-3">
                          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs font-mono">
                            {/* Parameters Card */}
                            <div className="rounded-lg border border-slate-800 bg-slate-900 p-3 space-y-2">
                              <p className="text-slate-400 font-semibold uppercase tracking-wider text-[10px] flex items-center space-x-1">
                                <Box className="h-3.5 w-3.5 text-cyan-400" />
                                <span>Geometric Parameters</span>
                              </p>
                              <div className="space-y-1 text-slate-300">
                                {Object.entries(dims).map(([k, v]) => (
                                  <div key={k} className="flex justify-between border-b border-slate-800/60 pb-0.5">
                                    <span className="text-slate-500">{k}:</span>
                                    <span className="font-bold text-white">
                                      {typeof v === 'number' ? `${v.toFixed(3)} mm` : String(v)}
                                    </span>
                                  </div>
                                ))}
                              </div>
                            </div>

                            {/* Position & Orientation Card */}
                            <div className="rounded-lg border border-slate-800 bg-slate-900 p-3 space-y-2">
                              <p className="text-slate-400 font-semibold uppercase tracking-wider text-[10px] flex items-center space-x-1">
                                <Compass className="h-3.5 w-3.5 text-indigo-400" />
                                <span>3D Orientation & Position</span>
                              </p>
                              <div className="space-y-1 text-slate-300">
                                <div className="flex justify-between border-b border-slate-800/60 pb-0.5">
                                  <span className="text-slate-500">Vector Axis:</span>
                                  <span className="font-bold text-indigo-300">
                                    {axis.length > 0 ? `[${axis.join(', ')}]` : 'N/A'}
                                  </span>
                                </div>
                                <div className="flex justify-between border-b border-slate-800/60 pb-0.5">
                                  <span className="text-slate-500">Center Point:</span>
                                  <span className="font-bold text-indigo-300">
                                    {pos.length > 0 ? `(${pos.map((n) => Number(n).toFixed(2)).join(', ')})` : 'N/A'}
                                  </span>
                                </div>
                              </div>
                            </div>

                            {/* All B-Rep Faces Card */}
                            <div className="rounded-lg border border-slate-800 bg-slate-900 p-3 space-y-2">
                              <p className="text-slate-400 font-semibold uppercase tracking-wider text-[10px] flex items-center space-x-1">
                                <Layers className="h-3.5 w-3.5 text-emerald-400" />
                                <span>Referenced B-Rep Faces ({faces.length})</span>
                              </p>
                              <div className="flex flex-wrap gap-1 max-h-24 overflow-y-auto">
                                {faces.map((f) => (
                                  <span
                                    key={f}
                                    className="rounded bg-slate-800 px-2 py-0.5 text-[11px] text-cyan-300 border border-slate-700"
                                  >
                                    {f}
                                  </span>
                                ))}
                              </div>
                            </div>
                          </div>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};
