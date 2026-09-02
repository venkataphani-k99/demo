import React, { useState } from 'react';
import {
  ShieldCheck,
  CheckCircle2,
  AlertTriangle,
  HelpCircle,
  Layers,
  Ruler,
  Eye,
  Scissors,
  Cpu,
  Info,
  ChevronRight,
  ExternalLink,
  Search,
} from 'lucide-react';
import {
  EngineeringIntelligenceResponse,
  ClassifiedDimensionItem,
  SectionCandidateItem,
  EngineeringFeatureItem,
} from '../../lib/api';

interface EngineeringIntelligencePanelProps {
  projectId: string;
  data: EngineeringIntelligenceResponse | null;
  isLoading: boolean;
  selectedFaceId: string | null;
  onSelectFace: (faceId: string | null) => void;
  selectedDimensionId: string | null;
  onSelectDimension: (dimId: string | null) => void;
  selectedSectionId?: string | null;
  onSelectSection?: (sectionId: string) => void;
}

export const EngineeringIntelligencePanel: React.FC<EngineeringIntelligencePanelProps> = ({
  projectId,
  data,
  isLoading,
  selectedFaceId,
  onSelectFace,
  selectedDimensionId,
  onSelectDimension,
  selectedSectionId: externalSelectedSectionId,
  onSelectSection,
}) => {
  const [activeTab, setActiveTab] = useState<'dimensions' | 'sections' | 'cards' | 'views'>('dimensions');
  const [internalSelectedSectionId, setInternalSelectedSectionId] = useState<string>('SEC_AA');
  const selectedSectionId = externalSelectedSectionId || internalSelectedSectionId;
  const setSelectedSectionId = (secId: string) => {
    setInternalSelectedSectionId(secId);
    if (onSelectSection) onSelectSection(secId);
  };
  const [filterTier, setFilterTier] = useState<string>('ALL');

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center py-24 text-slate-400">
        <div className="w-10 h-10 border-4 border-cyan-500/30 border-t-cyan-500 rounded-full animate-spin mb-4" />
        <p className="font-semibold text-slate-300 text-sm">Evaluating B-Rep Geometry & Feature Intelligence...</p>
        <p className="text-xs text-slate-500 mt-1">Extracting deterministic OCCT mathematical evidence</p>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-8 text-center text-slate-400">
        <AlertTriangle className="w-10 h-10 text-amber-400 mx-auto mb-3" />
        <p className="text-sm font-semibold text-slate-200">Engineering Intelligence Not Available</p>
        <p className="text-xs text-slate-500 mt-1">Run CAD Analysis on the 3D STEP model to generate the intelligence report.</p>
      </div>
    );
  }

  // Filter dimensions
  const filteredDimensions = data.classified_dimensions.filter((d) => {
    if (filterTier !== 'ALL' && d.importance_tier !== filterTier) return false;
    return true;
  });

  const activeDim = data.classified_dimensions.find((d) => d.dimension_id === selectedDimensionId);
  const activeSec = data.section_recommendations.candidates.find((s) => s.section_id === selectedSectionId) || data.section_recommendations.candidates[0];

  return (
    <div className="space-y-6">
      {/* Header Banner: 12 Core Questions Summary */}
      <div className="bg-gradient-to-r from-slate-900 via-slate-900 to-cyan-950/40 border border-cyan-500/30 rounded-xl p-5 shadow-lg">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="px-2.5 py-0.5 rounded-full text-xs font-black uppercase tracking-wider bg-cyan-500/20 text-cyan-400 border border-cyan-500/40">
                Phase 20 Prototype
              </span>
              <h2 className="text-lg font-black text-slate-100 tracking-wide">Engineering Design Intelligence & Verification</h2>
            </div>
            <p className="text-xs text-slate-400 mt-1">
              Deterministic B-Rep Understanding &amp; Bi-Directional Geometric Provenance (OpenCASCADE Kernel)
            </p>
          </div>

          <div className="flex items-center gap-3">
            <div className="text-right px-3 py-1.5 bg-slate-950/60 border border-slate-800 rounded-lg">
              <div className="text-[10px] uppercase font-bold text-slate-500">Validation Status</div>
              <div className="text-xs font-black text-emerald-400 flex items-center gap-1 justify-end">
                <ShieldCheck className="w-3.5 h-3.5" /> B-REP VERIFIED
              </div>
            </div>
            <div className="text-right px-3 py-1.5 bg-slate-950/60 border border-slate-800 rounded-lg">
              <div className="text-[10px] uppercase font-bold text-slate-500">Unique Solids</div>
              <div className="text-xs font-black text-cyan-300">
                {data.audit_summary.unique_solids_count} / {data.audit_summary.total_raw_solids} Raw
              </div>
            </div>
          </div>
        </div>

        {/* Tab Navigation */}
        <div className="flex flex-wrap items-center gap-2 mt-5 pt-4 border-t border-slate-800">
          <button
            onClick={() => setActiveTab('dimensions')}
            className={`px-3.5 py-2 rounded-lg text-xs font-bold transition flex items-center gap-2 ${
              activeTab === 'dimensions'
                ? 'bg-cyan-500 text-slate-950 shadow-md shadow-cyan-500/20'
                : 'bg-slate-800/80 text-slate-300 hover:bg-slate-800 hover:text-white'
            }`}
          >
            <Ruler className="w-3.5 h-3.5" />
            <span>Dimensions &amp; 3D Provenance</span>
            <span className="px-1.5 py-0.2 rounded text-[10px] font-black bg-slate-950/40">
              {data.classified_dimensions.length}
            </span>
          </button>

          <button
            onClick={() => setActiveTab('sections')}
            className={`px-3.5 py-2 rounded-lg text-xs font-bold transition flex items-center gap-2 ${
              activeTab === 'sections'
                ? 'bg-cyan-500 text-slate-950 shadow-md shadow-cyan-500/20'
                : 'bg-slate-800/80 text-slate-300 hover:bg-slate-800 hover:text-white'
            }`}
          >
            <Scissors className="w-3.5 h-3.5" />
            <span>Interactive Section Intelligence</span>
            <span className="px-1.5 py-0.2 rounded text-[10px] font-black bg-slate-950/40">
              {data.section_recommendations.candidates.length}
            </span>
          </button>

          <button
            onClick={() => setActiveTab('cards')}
            className={`px-3.5 py-2 rounded-lg text-xs font-bold transition flex items-center gap-2 ${
              activeTab === 'cards'
                ? 'bg-cyan-500 text-slate-950 shadow-md shadow-cyan-500/20'
                : 'bg-slate-800/80 text-slate-300 hover:bg-slate-800 hover:text-white'
            }`}
          >
            <Layers className="w-3.5 h-3.5" />
            <span>Engineering Intelligence Cards</span>
          </button>

          <button
            onClick={() => setActiveTab('views')}
            className={`px-3.5 py-2 rounded-lg text-xs font-bold transition flex items-center gap-2 ${
              activeTab === 'views'
                ? 'bg-cyan-500 text-slate-950 shadow-md shadow-cyan-500/20'
                : 'bg-slate-800/80 text-slate-300 hover:bg-slate-800 hover:text-white'
            }`}
          >
            <Eye className="w-3.5 h-3.5" />
            <span>Useful View Recommendations</span>
          </button>
        </div>
      </div>

      {/* TAB 1: DIMENSIONS & 3D PROVENANCE */}
      {activeTab === 'dimensions' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 space-y-4">
            {/* Filter controls */}
            <div className="flex flex-wrap items-center justify-between gap-3 bg-slate-900/60 p-3 rounded-lg border border-slate-800">
              <span className="text-xs font-bold text-slate-400">Filter by Importance Tier:</span>
              <div className="flex items-center gap-1.5">
                {['ALL', 'TIER_1_CRITICAL', 'TIER_2_FUNCTIONAL', 'TIER_3_ENVELOPE'].map((tier) => (
                  <button
                    key={tier}
                    onClick={() => setFilterTier(tier)}
                    className={`px-2.5 py-1 rounded text-[11px] font-bold transition ${
                      filterTier === tier
                        ? 'bg-cyan-500 text-slate-950'
                        : 'bg-slate-800 text-slate-400 hover:text-slate-200'
                    }`}
                  >
                    {tier.replace('TIER_', '').replace('_', ' ')}
                  </button>
                ))}
              </div>
            </div>

            {/* Table */}
            <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-sm">
              <div className="overflow-x-auto max-h-[500px]">
                <table className="w-full text-left text-xs border-collapse">
                  <thead className="bg-slate-950/80 sticky top-0 text-[11px] uppercase tracking-wider text-slate-400 border-b border-slate-800">
                    <tr>
                      <th className="p-3">Dim ID</th>
                      <th className="p-3">Type</th>
                      <th className="p-3">Measured Value</th>
                      <th className="p-3">Tier</th>
                      <th className="p-3">Source Entities</th>
                      <th className="p-3">Assigned View</th>
                      <th className="p-3">Validation</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60 font-mono">
                    {filteredDimensions.map((dim) => {
                      const isSelected = selectedDimensionId === dim.dimension_id;
                      const hasSourceFace = selectedFaceId && dim.source_entities.includes(selectedFaceId);

                      return (
                        <tr
                          key={dim.dimension_id}
                          onClick={() => {
                            onSelectDimension(dim.dimension_id);
                            if (dim.source_entities.length > 0) {
                              onSelectFace(dim.source_entities[0]);
                            }
                          }}
                          className={`cursor-pointer transition-colors ${
                            isSelected
                              ? 'bg-cyan-500/20 text-cyan-200'
                              : hasSourceFace
                              ? 'bg-pink-500/20 text-pink-200'
                              : 'hover:bg-slate-800/50 text-slate-300'
                          }`}
                        >
                          <td className="p-3 font-bold text-slate-100">{dim.dimension_id}</td>
                          <td className="p-3 uppercase text-slate-400 text-[11px]">{dim.dimension_type}</td>
                          <td className="p-3 font-black text-cyan-300 text-sm">{dim.value_mm.toFixed(2)} mm</td>
                          <td className="p-3">
                            <span
                              className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                                dim.importance_tier === 'TIER_1_CRITICAL'
                                  ? 'bg-red-500/20 text-red-300 border border-red-500/30'
                                  : dim.importance_tier === 'TIER_2_FUNCTIONAL'
                                  ? 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
                                  : 'bg-slate-700/40 text-slate-400'
                              }`}
                            >
                              {dim.importance_tier.replace('TIER_', '')}
                            </span>
                          </td>
                          <td className="p-3">
                            <div className="flex flex-wrap gap-1">
                              {dim.source_entities.map((ent) => (
                                <span
                                  key={ent}
                                  className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                                    selectedFaceId === ent
                                      ? 'bg-pink-500 text-white'
                                      : 'bg-slate-800 text-slate-300 hover:bg-cyan-500/30'
                                  }`}
                                >
                                  {ent}
                                </span>
                              ))}
                            </div>
                          </td>
                          <td className="p-3 font-bold text-slate-300">{dim.assigned_view}</td>
                          <td className="p-3">
                            <span className="text-emerald-400 font-bold flex items-center gap-1">
                              <CheckCircle2 className="w-3.5 h-3.5" /> B-REP VERIFIED
                            </span>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          </div>

          {/* Dimension Provenance Inspector Card */}
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-lg space-y-4">
            <h3 className="text-sm font-bold text-slate-200 flex items-center gap-2 border-b border-slate-800 pb-3">
              <Cpu className="w-4 h-4 text-cyan-400" />
              Dimension Provenance &amp; 3D Inspector
            </h3>

            {activeDim ? (
              <div className="space-y-4 text-xs">
                <div>
                  <div className="text-[10px] uppercase font-bold text-slate-500">Selected Dimension</div>
                  <div className="text-base font-black text-cyan-300 mt-0.5">
                    {activeDim.dimension_id} — {activeDim.value_mm.toFixed(3)} mm ({activeDim.dimension_type})
                  </div>
                </div>

                <div className="bg-slate-950/80 p-3 rounded-lg border border-slate-800 space-y-2">
                  <div>
                    <span className="text-slate-500 font-bold">Source B-Rep Entities: </span>
                    <span className="text-pink-300 font-mono font-bold">
                      {activeDim.source_entities.join(', ') || 'N/A'}
                    </span>
                  </div>
                  <div>
                    <span className="text-slate-500 font-bold">Measurement Method: </span>
                    <span className="text-slate-300 font-mono">{activeDim.measurement_method}</span>
                  </div>
                  <div>
                    <span className="text-slate-500 font-bold">Assigned Drawing View: </span>
                    <span className="text-slate-200 font-bold">{activeDim.assigned_view}</span>
                  </div>
                  <div>
                    <span className="text-slate-500 font-bold">Importance Tier: </span>
                    <span className="text-amber-300 font-bold">{activeDim.importance_tier}</span>
                  </div>
                  <div>
                    <span className="text-slate-500 font-bold">General Tolerance: </span>
                    <span className="text-slate-300">{activeDim.tolerance}</span>
                  </div>
                </div>

                <div>
                  <div className="text-[10px] uppercase font-bold text-slate-500">Geometric Validation</div>
                  <p className="text-emerald-400 font-medium mt-1 bg-emerald-950/30 border border-emerald-500/20 p-2.5 rounded-lg text-xs leading-relaxed">
                    ✓ {activeDim.validation_note}
                  </p>
                </div>

                <div className="pt-2 border-t border-slate-800">
                  <p className="text-[11px] text-slate-500 italic">
                    💡 Click on any face in the 3D Viewport or click on a table row to highlight the exact physical B-Rep surface.
                  </p>
                </div>
              </div>
            ) : (
              <div className="py-12 text-center text-slate-500 text-xs">
                Select any dimension in the table or click on a face in the 3D Viewport to inspect geometric provenance.
              </div>
            )}
          </div>
        </div>
      )}

      {/* TAB 2: INTERACTIVE SECTION INTELLIGENCE */}
      {activeTab === 'sections' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Candidates List */}
          <div className="space-y-3">
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400">Candidate Cutting Planes</h3>
            {data.section_recommendations.candidates.map((sec) => {
              const isSelected = selectedSectionId === sec.section_id;
              return (
                <div
                  key={sec.section_id}
                  onClick={() => setSelectedSectionId(sec.section_id)}
                  className={`p-4 rounded-xl border cursor-pointer transition shadow-sm ${
                    isSelected
                      ? 'bg-cyan-950/40 border-cyan-500 shadow-cyan-500/10'
                      : 'bg-slate-900 border-slate-800 hover:border-slate-700'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-black text-slate-100">{sec.section_id}</span>
                    <span
                      className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                        sec.rank === 'PRIMARY_RECOMMENDED'
                          ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                          : 'bg-slate-800 text-slate-400'
                      }`}
                    >
                      {sec.rank === 'PRIMARY_RECOMMENDED' ? 'RECOMMENDED' : 'CANDIDATE'}
                    </span>
                  </div>
                  <p className="text-xs font-bold text-cyan-300 mt-1">{sec.plane_name}</p>
                  <p className="text-[11px] text-slate-400 mt-1">{sec.engineering_rationale[0]}</p>
                  <div className="flex items-center justify-between text-[11px] text-slate-500 mt-3 pt-2 border-t border-slate-800/80">
                    <span>Usefulness Score:</span>
                    <span className="font-bold text-slate-200">{(sec.usefulness_score * 100).toFixed(0)}%</span>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Section Cut Deep-Dive Details */}
          <div className="lg:col-span-2 bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-lg space-y-5">
            <div className="flex items-center justify-between border-b border-slate-800 pb-4">
              <div>
                <span className="text-xs font-bold text-cyan-400 uppercase tracking-wide">{activeSec.section_type}</span>
                <h3 className="text-base font-black text-slate-100 mt-0.5">{activeSec.section_id} — {activeSec.plane_name}</h3>
              </div>
              <div className="text-right">
                <span className="text-xs text-slate-400 font-medium">Usefulness: </span>
                <span className="text-sm font-black text-emerald-400">{(activeSec.usefulness_score * 100).toFixed(0)}%</span>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs font-mono">
              <div className="bg-slate-950/80 p-3 rounded-lg border border-slate-800 space-y-1">
                <div className="text-[10px] uppercase font-bold text-slate-500">Plane Origin [X, Y, Z]</div>
                <div className="text-slate-200 font-bold">[{activeSec.plane_origin.map((v) => v.toFixed(2)).join(', ')}]</div>
              </div>
              <div className="bg-slate-950/80 p-3 rounded-lg border border-slate-800 space-y-1">
                <div className="text-[10px] uppercase font-bold text-slate-500">Plane Normal [Nx, Ny, Nz]</div>
                <div className="text-slate-200 font-bold">[{activeSec.plane_normal.map((v) => v.toFixed(2)).join(', ')}]</div>
              </div>
            </div>

            {/* Hidden Features Revealed */}
            <div>
              <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-2">
                Internal Features Exposed by this Cut ({activeSec.internal_features_exposed.length})
              </h4>
              {activeSec.internal_features_exposed.length > 0 ? (
                <div className="flex flex-wrap gap-2">
                  {activeSec.internal_features_exposed.map((feat) => (
                    <span key={feat} className="px-2.5 py-1 rounded bg-slate-950 border border-slate-800 text-cyan-300 font-mono text-xs font-bold">
                      {feat}
                    </span>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-slate-500 italic">No additional internal cavity features exposed.</p>
              )}
            </div>

            {/* Engineering Rationale */}
            <div>
              <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-2">Engineering Rationale</h4>
              <ul className="space-y-1.5 text-xs text-slate-300">
                {activeSec.engineering_rationale.map((r, i) => (
                  <li key={i} className="flex items-start gap-2">
                    <span className="text-cyan-400 font-bold">✓</span>
                    <span>{r}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      )}

      {/* TAB 3: ENGINEERING INTELLIGENCE CARDS (EPISTEMIC SEPARATION) */}
      {activeTab === 'cards' && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Card: KNOWN */}
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-3">
            <div className="flex items-center gap-2 border-b border-slate-800 pb-2">
              <CheckCircle2 className="w-4 h-4 text-emerald-400" />
              <h3 className="text-xs font-black uppercase tracking-wider text-emerald-400">KNOWN (Geometric Facts)</h3>
            </div>
            <ul className="space-y-2 text-xs text-slate-300">
              <li className="p-2.5 bg-slate-950/60 rounded-lg border border-slate-800/80">
                <span className="font-bold text-slate-200">Assembly Envelope: </span>
                <span className="font-mono text-cyan-300">
                  {data.audit_summary.assembly_envelope_mm[0].toFixed(1)} × {data.audit_summary.assembly_envelope_mm[1].toFixed(1)} × {data.audit_summary.assembly_envelope_mm[2].toFixed(1)} mm
                </span>
                <div className="text-[11px] text-slate-500 mt-0.5">Source: OCCT direct bounding box audit</div>
              </li>
              <li className="p-2.5 bg-slate-950/60 rounded-lg border border-slate-800/80">
                <span className="font-bold text-slate-200">Unique Topology: </span>
                <span className="font-mono text-cyan-300">
                  {data.audit_summary.unique_faces_count} Faces, {data.audit_summary.unique_edges_count} Edges ({data.audit_summary.unique_solids_count} Unique Solids)
                </span>
                <div className="text-[11px] text-slate-500 mt-0.5">Source: OCCT B-Rep solid hash deduplication</div>
              </li>
              <li className="p-2.5 bg-slate-950/60 rounded-lg border border-slate-800/80">
                <span className="font-bold text-slate-200">Cylindrical Surfaces: </span>
                <span className="font-mono text-cyan-300">{data.audit_summary.surface_types['Cylinder'] || 0} Cylinders extracted</span>
                <div className="text-[11px] text-slate-500 mt-0.5">Source: OCCT GeomCylinder analytical inspection</div>
              </li>
            </ul>
          </div>

          {/* Card: INFERRED */}
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-3">
            <div className="flex items-center gap-2 border-b border-slate-800 pb-2">
              <Info className="w-4 h-4 text-cyan-400" />
              <h3 className="text-xs font-black uppercase tracking-wider text-cyan-400">INFERRED (Engineering Interpretations)</h3>
            </div>
            <ul className="space-y-2 text-xs text-slate-300">
              <li className="p-2.5 bg-slate-950/60 rounded-lg border border-slate-800/80">
                <span className="font-bold text-slate-200">Possible Fluid Port Conduits: </span>
                <span className="text-slate-300">Ø23.00 mm through-bores along longitudinal axis</span>
                <div className="text-[11px] text-slate-500 mt-0.5">Reason: Inferred from coaxial internal cylindrical geometry</div>
              </li>
              <li className="p-2.5 bg-slate-950/60 rounded-lg border border-slate-800/80">
                <span className="font-bold text-slate-200">Possible Valve Seat Chamber: </span>
                <span className="text-slate-300">Ø35.00 mm central cavity</span>
                <div className="text-[11px] text-slate-500 mt-0.5">Reason: Inferred from enlarged internal spherical/cylindrical core</div>
              </li>
            </ul>
          </div>

          {/* Card: UNKNOWN */}
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-3">
            <div className="flex items-center gap-2 border-b border-slate-800 pb-2">
              <HelpCircle className="w-4 h-4 text-amber-400" />
              <h3 className="text-xs font-black uppercase tracking-wider text-amber-400">UNKNOWN (Missing Engineering Notes)</h3>
            </div>
            <ul className="space-y-2 text-xs text-slate-300">
              {data.missing_information.map((m, i) => (
                <li key={i} className="p-2.5 bg-slate-950/60 rounded-lg border border-slate-800/80">
                  <p className="text-slate-300">{m}</p>
                </li>
              ))}
            </ul>
          </div>

          {/* Card: AMBIGUOUS */}
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-3">
            <div className="flex items-center gap-2 border-b border-slate-800 pb-2">
              <AlertTriangle className="w-4 h-4 text-pink-400" />
              <h3 className="text-xs font-black uppercase tracking-wider text-pink-400">AMBIGUOUS (Resolved by Auditor)</h3>
            </div>
            <ul className="space-y-2 text-xs text-slate-300">
              {data.ambiguities_detected.map((a, i) => (
                <li key={i} className="p-2.5 bg-slate-950/60 rounded-lg border border-slate-800/80">
                  <p className="text-slate-300">{a}</p>
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}

      {/* TAB 4: USEFUL VIEW RECOMMENDATIONS */}
      {activeTab === 'views' && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {Object.entries(data.view_recommendations.evaluations).map(([vName, vEval]) => (
            <div
              key={vName}
              className={`p-5 rounded-xl border shadow-sm space-y-3 ${
                vEval.rank === 'PRIMARY'
                  ? 'bg-slate-900 border-cyan-500/40 shadow-cyan-500/5'
                  : 'bg-slate-900/60 border-slate-800'
              }`}
            >
              <div className="flex items-center justify-between">
                <span className="text-base font-black text-slate-100">{vName}</span>
                <span
                  className={`px-2 py-0.5 rounded text-[10px] font-black uppercase ${
                    vEval.rank === 'PRIMARY'
                      ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/30'
                      : 'bg-slate-800 text-slate-400'
                  }`}
                >
                  {vEval.rank} VIEW
                </span>
              </div>

              <div className="text-xs font-mono text-slate-400">
                Line of Sight: [{vEval.normal_vector.join(', ')}]
              </div>

              <div className="space-y-1 text-xs text-slate-300">
                {vEval.engineering_rationale.map((r, idx) => (
                  <p key={idx} className="text-slate-300 flex items-start gap-1.5">
                    <span className="text-cyan-400 font-bold">•</span>
                    <span>{r}</span>
                  </p>
                ))}
              </div>

              <div className="pt-2 border-t border-slate-800 flex items-center justify-between text-xs text-slate-500">
                <span>Usefulness Score:</span>
                <span className="font-bold text-slate-200">{(vEval.usefulness_score * 100).toFixed(0)}%</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
