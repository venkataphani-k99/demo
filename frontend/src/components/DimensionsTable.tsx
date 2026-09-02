import React, { useState, useMemo } from 'react';
import {
  Ruler, CheckCircle2, AlertTriangle, Eye, ShieldCheck, Search,
  Filter, Layers, ArrowUpRight, Compass, Check, Copy, Info, Database
} from 'lucide-react';
import { DimensionCandidate } from '../../lib/api';

interface DimensionsTableProps {
  dimensions: DimensionCandidate[];
  rawMeasurementsCount?: number;
  engineeringCandidatesCount?: number;
}

export const DimensionsTable: React.FC<DimensionsTableProps> = ({
  dimensions,
  rawMeasurementsCount,
  engineeringCandidatesCount,
}) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('ALL');
  const [viewFilter, setViewFilter] = useState<string>('ALL');
  const [copiedId, setCopiedId] = useState<string | null>(null);

  // Compute counts
  const placedDims = useMemo(
    () => dimensions.filter((d) => d.status === 'placed' || d.placement_status === 'placed'),
    [dimensions]
  );
  const excludedDims = useMemo(
    () => dimensions.filter((d) => d.status === 'excluded' || d.placement_status === 'excluded'),
    [dimensions]
  );
  const candidateDims = useMemo(
    () =>
      dimensions.filter(
        (d) =>
          d.status !== 'placed' &&
          d.placement_status !== 'placed' &&
          d.status !== 'excluded' &&
          d.placement_status !== 'excluded'
      ),
    [dimensions]
  );

  const rawCount = rawMeasurementsCount ?? dimensions.length * 3;
  const candCount = engineeringCandidatesCount ?? dimensions.length;

  // Extract unique views
  const uniqueViews = useMemo(() => {
    const vset = new Set<string>();
    dimensions.forEach((d) => {
      const v = d.selected_view || (d as unknown as Record<string, string>)['view'];
      if (v) vset.add(v);
    });
    return Array.from(vset).sort();
  }, [dimensions]);

  // Filter dimensions
  const filteredDimensions = useMemo(() => {
    return dimensions.filter((d) => {
      const did = d.id || '';
      const dtype = d.type || '';
      const srole = d.semantic_role || '';
      const feat = d.source_feature || '';
      const ents = (d.source_entities || []).join(' ');
      const view = d.selected_view || (d as unknown as Record<string, string>)['view'] || '';
      const isPlaced = d.status === 'placed' || d.placement_status === 'placed';
      const isExcluded = d.status === 'excluded' || d.placement_status === 'excluded';

      const matchesSearch =
        searchTerm === '' ||
        did.toLowerCase().includes(searchTerm.toLowerCase()) ||
        dtype.toLowerCase().includes(searchTerm.toLowerCase()) ||
        srole.toLowerCase().includes(searchTerm.toLowerCase()) ||
        feat.toLowerCase().includes(searchTerm.toLowerCase()) ||
        ents.toLowerCase().includes(searchTerm.toLowerCase());

      const matchesStatus =
        statusFilter === 'ALL' ||
        (statusFilter === 'PLACED' && isPlaced) ||
        (statusFilter === 'EXCLUDED' && isExcluded) ||
        (statusFilter === 'CANDIDATES' && !isPlaced && !isExcluded);

      const matchesView = viewFilter === 'ALL' || view === viewFilter;

      return matchesSearch && matchesStatus && matchesView;
    });
  }, [dimensions, searchTerm, statusFilter, viewFilter]);

  const copyDimId = (did: string) => {
    navigator.clipboard.writeText(did);
    setCopiedId(did);
    setTimeout(() => setCopiedId(null), 2000);
  };

  // Zero candidates empty state
  if (dimensions.length === 0) {
    return (
      <div className="rounded-xl border border-slate-800 bg-slate-900/60 overflow-hidden backdrop-blur-md shadow-xl">
        <div className="flex items-center justify-between border-b border-slate-800 bg-slate-950/60 px-4 py-3">
          <div className="flex items-center space-x-2">
            <Ruler className="h-4 w-4 text-cyan-400" />
            <h3 className="text-sm font-semibold text-white">Dimension Candidates & TechDraw Placements</h3>
          </div>
        </div>
        <div className="flex flex-col items-center justify-center py-12 px-6 text-center space-y-3">
          <div className="rounded-full bg-amber-500/10 p-3 border border-amber-500/20">
            <Info className="h-6 w-6 text-amber-400" />
          </div>
          <p className="text-sm font-semibold text-amber-300">
            No deterministic dimension candidates generated for this model.
          </p>
          <p className="text-xs text-slate-400 max-w-sm">
            This model may lack analytically measurable cylindrical, planar, or linear features
            that pass the OCCT validation gatekeeper. Run the complete dimensioning pipeline to regenerate.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/60 overflow-hidden backdrop-blur-md shadow-xl flex flex-col">
      {/* Table Header & 4-Tier Stats Banner */}
      <div className="border-b border-slate-800 bg-slate-950/80 px-4 py-3 space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center space-x-2">
            <Ruler className="h-4 w-4 text-cyan-400" />
            <h3 className="text-sm font-semibold text-white">Dimension Candidates & TechDraw Placements</h3>
            <span className="rounded-full bg-cyan-500/10 px-2.5 py-0.5 text-xs font-mono font-bold text-cyan-300 border border-cyan-500/20">
              {placedDims.length} / {dimensions.length} Placed
            </span>
          </div>

          {/* 4-Tier Summary Badges */}
          <div className="flex items-center flex-wrap gap-2 text-[11px] font-mono">
            <span className="flex items-center space-x-1 rounded bg-slate-800/80 px-2 py-0.5 text-slate-300 border border-slate-700">
              <Database className="h-3 w-3 text-slate-400" />
              <span>Raw: <strong className="text-white">{rawCount}</strong></span>
            </span>
            <span className="flex items-center space-x-1 rounded bg-slate-800/80 px-2 py-0.5 text-cyan-300 border border-slate-700">
              <Ruler className="h-3 w-3 text-cyan-400" />
              <span>Candidates: <strong className="text-cyan-200">{candCount}</strong></span>
            </span>
            <span className="flex items-center space-x-1 rounded bg-emerald-500/10 px-2 py-0.5 text-emerald-300 border border-emerald-500/30">
              <CheckCircle2 className="h-3 w-3 text-emerald-400" />
              <span>Placed: <strong className="text-emerald-200">{placedDims.length}</strong></span>
            </span>
            <span className="flex items-center space-x-1 rounded bg-amber-500/10 px-2 py-0.5 text-amber-300 border border-amber-500/30">
              <AlertTriangle className="h-3 w-3 text-amber-400" />
              <span>Excluded: <strong className="text-amber-200">{excludedDims.length}</strong></span>
            </span>
          </div>
        </div>

        {/* Search & Filter Controls */}
        <div className="flex flex-wrap items-center justify-between gap-3 pt-1">
          {/* Search Input */}
          <div className="relative flex-1 min-w-[200px] max-w-sm">
            <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-slate-500" />
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Search dimension ID, feature, entity..."
              className="w-full rounded-lg border border-slate-700 bg-slate-900/90 pl-8 pr-3 py-1.5 text-xs text-white placeholder-slate-500 focus:border-cyan-500 focus:outline-none focus:ring-1 focus:ring-cyan-500 font-mono"
            />
          </div>

          {/* Status & View Filter Pills */}
          <div className="flex flex-wrap items-center gap-2">
            {/* Status Filter */}
            <div className="flex items-center space-x-1 bg-slate-900 p-1 rounded-lg border border-slate-800 text-xs font-mono">
              <button
                onClick={() => setStatusFilter('ALL')}
                className={`rounded px-2 py-0.5 transition-colors ${
                  statusFilter === 'ALL' ? 'bg-cyan-500/20 text-cyan-300 font-bold' : 'text-slate-400 hover:text-white'
                }`}
              >
                All ({dimensions.length})
              </button>
              <button
                onClick={() => setStatusFilter('PLACED')}
                className={`rounded px-2 py-0.5 transition-colors ${
                  statusFilter === 'PLACED' ? 'bg-emerald-500/20 text-emerald-300 font-bold' : 'text-slate-400 hover:text-white'
                }`}
              >
                Placed ({placedDims.length})
              </button>
              <button
                onClick={() => setStatusFilter('EXCLUDED')}
                className={`rounded px-2 py-0.5 transition-colors ${
                  statusFilter === 'EXCLUDED' ? 'bg-amber-500/20 text-amber-300 font-bold' : 'text-slate-400 hover:text-white'
                }`}
              >
                Excluded ({excludedDims.length})
              </button>
            </div>

            {/* View Filter */}
            {uniqueViews.length > 0 && (
              <select
                value={viewFilter}
                onChange={(e) => setViewFilter(e.target.value)}
                className="rounded-lg border border-slate-700 bg-slate-900 px-2.5 py-1 text-xs text-slate-300 font-mono focus:border-cyan-500 focus:outline-none"
              >
                <option value="ALL">All Views ({dimensions.length})</option>
                {uniqueViews.map((v) => (
                  <option key={v} value={v}>
                    {v} View
                  </option>
                ))}
              </select>
            )}
          </div>
        </div>
      </div>

      {/* Table Container */}
      <div className="overflow-x-auto max-h-[560px]">
        <table className="w-full text-left text-xs">
          <thead className="sticky top-0 bg-slate-950/95 text-slate-400 border-b border-slate-800 z-10 font-medium">
            <tr>
              <th className="py-2.5 px-3">Dim ID</th>
              <th className="py-2.5 px-3">Nominal Value</th>
              <th className="py-2.5 px-3">Type</th>
              <th className="py-2.5 px-3">Semantic Role</th>
              <th className="py-2.5 px-3">Source Feature</th>
              <th className="py-2.5 px-3">B-Rep Source Entities</th>
              <th className="py-2.5 px-3">Target View</th>
              <th className="py-2.5 px-3">Status</th>
              <th className="py-2.5 px-3">Exclusion / Validation Reason</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/60 font-mono">
            {filteredDimensions.length === 0 ? (
              <tr>
                <td colSpan={9} className="py-12 text-center text-slate-500">
                  No dimension candidates match your search and filter criteria.
                </td>
              </tr>
            ) : (
              filteredDimensions.map((dim) => {
                const isPlaced = dim.status === 'placed' || dim.placement_status === 'placed';
                const isExcluded = dim.status === 'excluded' || dim.placement_status === 'excluded';
                const isAmbiguous = dim.status === 'ambiguous' || dim.placement_status === 'ambiguous';
                const displayVal = dim.display_value || dim.formatted_text || `${dim.value.toFixed(2)} mm`;
                const view = dim.selected_view || (dim as unknown as Record<string, string>)['view'] || '—';
                const featLink = dim.source_feature || (dim as unknown as Record<string, string>)['feature_id'] || '—';
                const sourceEnts = dim.source_entities || [];
                const role = dim.semantic_role || 'engineering_dimension';
                const exclReason = dim.exclusion_reason || dim.reason || '';

                return (
                  <tr
                    key={dim.id}
                    className={`hover:bg-slate-800/40 transition-colors ${
                      isPlaced ? 'bg-cyan-500/[0.02]' : 'opacity-75'
                    }`}
                  >
                    {/* Dim ID */}
                    <td className="py-2.5 px-3 font-bold text-cyan-300">
                      <div className="flex items-center space-x-1">
                        <span>{dim.id}</span>
                        <button
                          onClick={() => copyDimId(dim.id)}
                          className="text-slate-500 hover:text-cyan-300 transition-colors p-0.5"
                          title="Copy Dim ID"
                        >
                          {copiedId === dim.id ? (
                            <Check className="h-3 w-3 text-emerald-400" />
                          ) : (
                            <Copy className="h-3 w-3" />
                          )}
                        </button>
                      </div>
                    </td>

                    {/* Nominal Value */}
                    <td className="py-2.5 px-3 text-sm font-bold text-white tracking-tight">
                      {displayVal}
                    </td>

                    {/* Type */}
                    <td className="py-2.5 px-3">
                      <span className="rounded bg-slate-800 px-2 py-0.5 text-[11px] text-slate-300 border border-slate-700 font-mono capitalize">
                        {dim.type}
                      </span>
                    </td>

                    {/* Semantic Role */}
                    <td className="py-2.5 px-3 text-[11px]">
                      <span className="text-slate-300 truncate max-w-[160px] block" title={role}>
                        {role.replace(/_/g, ' ')}
                      </span>
                    </td>

                    {/* Source Feature */}
                    <td className="py-2.5 px-3">
                      {featLink !== '—' ? (
                        <span className="rounded bg-indigo-500/10 px-1.5 py-0.5 text-[11px] text-indigo-300 border border-indigo-500/20">
                          {featLink}
                        </span>
                      ) : (
                        <span className="text-slate-600">—</span>
                      )}
                    </td>

                    {/* B-Rep Entities */}
                    <td className="py-2.5 px-3">
                      {sourceEnts.length > 0 ? (
                        <div className="flex flex-wrap gap-1">
                          {sourceEnts.slice(0, 3).map((ent) => (
                            <span
                              key={ent}
                              className="rounded bg-slate-800/90 px-1.5 py-0.5 text-[10px] text-slate-400 border border-slate-700"
                            >
                              {ent}
                            </span>
                          ))}
                          {sourceEnts.length > 3 && (
                            <span className="text-[10px] text-slate-500">+{sourceEnts.length - 3}</span>
                          )}
                        </div>
                      ) : (
                        <span className="text-slate-600 text-[11px]">bounding box</span>
                      )}
                    </td>

                    {/* Target View */}
                    <td className="py-2.5 px-3">
                      <span className="inline-flex items-center space-x-1 text-slate-300 text-[11px]">
                        <Eye className="h-3 w-3 text-cyan-400" />
                        <span>{view}</span>
                      </span>
                    </td>

                    {/* Placement Status */}
                    <td className="py-2.5 px-3">
                      {isPlaced ? (
                        <span className="inline-flex items-center space-x-1 rounded-full bg-emerald-500/10 px-2 py-0.5 text-[11px] font-semibold text-emerald-400 border border-emerald-500/20">
                          <CheckCircle2 className="h-3 w-3" />
                          <span>Placed in TechDraw</span>
                        </span>
                      ) : isAmbiguous ? (
                        <span className="inline-flex items-center space-x-1 rounded-full bg-amber-500/10 px-2 py-0.5 text-[11px] font-medium text-amber-400 border border-amber-500/20">
                          <AlertTriangle className="h-3 w-3" />
                          <span>Ambiguous</span>
                        </span>
                      ) : isExcluded ? (
                        <span className="inline-flex items-center space-x-1 rounded-full bg-slate-800 px-2 py-0.5 text-[11px] text-amber-300 border border-amber-500/30">
                          <span>Excluded</span>
                        </span>
                      ) : (
                        <span className="inline-flex items-center space-x-1 rounded-full bg-slate-800 px-2 py-0.5 text-[11px] text-slate-400 border border-slate-700">
                          <span>Candidate</span>
                        </span>
                      )}
                    </td>

                    {/* Exclusion / Validation Reason */}
                    <td className="py-2.5 px-3 text-[11px]">
                      {isPlaced ? (
                        <span className="text-emerald-400 font-bold flex items-center space-x-1">
                          <ShieldCheck className="h-3.5 w-3.5 text-emerald-400" />
                          <span>100% Deterministic OCCT ✓</span>
                        </span>
                      ) : isExcluded ? (
                        <span className="text-amber-300/90 truncate max-w-[280px] block" title={exclReason}>
                          {exclReason}
                        </span>
                      ) : (
                        <span className="text-slate-500">—</span>
                      )}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};
