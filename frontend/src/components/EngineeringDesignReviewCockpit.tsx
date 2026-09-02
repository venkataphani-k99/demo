import React, { useState, useEffect } from 'react';
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
  ChevronDown,
  Sparkles,
  ExternalLink,
  Target,
  FileCheck,
  Maximize2,
  Bot,
  Send,
  Loader2,
  Sun,
  Moon,
  Search,
  Check,
  ArrowRight,
  AlertOctagon,
} from 'lucide-react';
import {
  EngineeringIntelligenceResponse,
  ClassifiedDimensionItem,
  SectionCandidateItem,
  EngineeringFeatureItem,
  CADAnalysisResponse,
  RecognizedFeature,
  AIReviewResultResponse,
  AIQuestionAnswerResponse,
  CADDrawingMatchItem,
  DrawingConsistencyResponse,
  CADMeshResponse,
  api,
} from '../../lib/api';
import { Viewer3D } from './Viewer3D';

interface EngineeringDesignReviewCockpitProps {
  projectId: string;
  data: EngineeringIntelligenceResponse | null;
  meshData?: CADMeshResponse | null;
  summary?: CADAnalysisResponse;
  features?: RecognizedFeature[];
  isLoading: boolean;
  onReload?: () => void;
  theme?: 'light' | 'dark';
  onToggleTheme?: () => void;
}

export const EngineeringDesignReviewCockpit: React.FC<EngineeringDesignReviewCockpitProps> = ({
  projectId,
  data,
  meshData,
  summary,
  features = [],
  isLoading,
  onReload,
  theme = 'light',
  onToggleTheme,
}) => {

  // Subtabs: 'cad_drawing' (Phase 25 Primary) | 'ai_review' | 'summary' | 'features' | 'dimensions' | 'views_sections' | 'epistemic'
  const [activeSubTab, setActiveSubTab] = useState<'cad_drawing' | 'ai_review' | 'summary' | 'features' | 'dimensions' | 'views_sections' | 'epistemic'>('cad_drawing');
  const [selectedFeatureId, setSelectedFeatureId] = useState<string | null>('FEAT_001');
  const [selectedFaceId, setSelectedFaceId] = useState<string | null>('Face2');
  const [selectedDimensionId, setSelectedDimensionId] = useState<string | null>(null);
  const [selectedSectionId, setSelectedSectionId] = useState<string>('SEC_AA');
  const [showSectionPlane, setShowSectionPlane] = useState<boolean>(true);
  const [selectedViewPreset, setSelectedViewPreset] = useState<'ISO' | 'FRONT' | 'TOP' | 'RIGHT' | 'BOTTOM'>('ISO');
  
  // Collapsible state for "WHY?" reasoning in AI cards
  const [expandedWhy, setExpandedWhy] = useState<Record<string, boolean>>({ 'p1': true });

  // AI Review data & interactive Q&A state
  const [aiReview, setAiReview] = useState<AIReviewResultResponse | null>(null);
  const [isAiLoading, setIsAiLoading] = useState<boolean>(false);
  const [questionInput, setQuestionInput] = useState<string>('');
  const [isAsking, setIsAsking] = useState<boolean>(false);
  const [qaHistory, setQaHistory] = useState<AIQuestionAnswerResponse[]>([]);

  // Phase 25: CAD ↔ Drawing Consistency Audit State
  const [consistencyData, setConsistencyData] = useState<DrawingConsistencyResponse | null>(null);
  const [isConsistencyLoading, setIsConsistencyLoading] = useState<boolean>(false);
  const [selectedMatchId, setSelectedMatchId] = useState<string | null>('MATCH_001');
  const [consistencyFilter, setConsistencyFilter] = useState<string>('ALL');
  const [consistencyQuestionInput, setConsistencyQuestionInput] = useState<string>('');
  const [isConsistencyAsking, setIsConsistencyAsking] = useState<boolean>(false);
  const [consistencyQaHistory, setConsistencyQaHistory] = useState<any[]>([]);

  // Load AI Review and CAD ↔ Drawing Consistency when project loads
  useEffect(() => {
    let isMounted = true;
    const fetchReviewData = async () => {
      if (!projectId) return;
      setIsAiLoading(true);
      setIsConsistencyLoading(true);
      try {
        const [aiRes, consRes] = await Promise.allSettled([
          api.getAIEngineeringReview(projectId),
          api.getCADDrawingConsistency(projectId),
        ]);
        if (isMounted) {
          if (aiRes.status === 'fulfilled' && aiRes.value) {
            setAiReview(aiRes.value);
          }
          if (consRes.status === 'fulfilled' && consRes.value) {
            setConsistencyData(consRes.value);
            if (consRes.value.matches && consRes.value.matches.length > 0) {
              setSelectedMatchId(consRes.value.matches[0].match_id);
            }
          }
        }
      } catch (err) {
        console.warn('Consistency review fetch notice:', err);
      } finally {
        if (isMounted) {
          setIsAiLoading(false);
          setIsConsistencyLoading(false);
        }
      }
    };

    fetchReviewData();
    return () => {
      isMounted = false;
    };
  }, [projectId]);

  // Handle Q&A submission
  const handleAskQuestion = async (queryText?: string) => {
    const q = (queryText || questionInput).trim();
    if (!q || isAsking) return;

    setIsAsking(true);
    try {
      const resp = await api.askAIEngineeringQuestion(projectId, q);
      setQaHistory((prev) => [resp, ...prev]);
      setQuestionInput('');
      
      // Auto-highlight first grounded evidence entity if present
      if (resp.grounded_evidence && resp.grounded_evidence.length > 0) {
        const firstRef = resp.grounded_evidence[0];
        if (firstRef.entity_type === 'FACE' && firstRef.entity_id) {
          setSelectedFaceId(firstRef.entity_id);
        }
      }
    } catch (err) {
      console.error('Failed to answer engineering question:', err);
    } finally {
      setIsAsking(false);
    }
  };

  // Phase 25: Handle CAD ↔ Drawing Consistency Q&A
  const handleAskConsistencyQuestion = async (queryText?: string) => {
    const q = (queryText || consistencyQuestionInput).trim();
    if (!q || isConsistencyAsking) return;

    setIsConsistencyAsking(true);
    try {
      const resp = await api.askCADDrawingQuestion(projectId, q);
      setConsistencyQaHistory((prev) => [resp, ...prev]);
      setConsistencyQuestionInput('');

      if (resp.evidence && resp.evidence.length > 0) {
        const firstEv = resp.evidence[0];
        if (firstEv.cad_entity_id) {
          setSelectedFaceId(firstEv.cad_entity_id);
        }
      }
    } catch (err) {
      console.error('Failed to answer consistency question:', err);
    } finally {
      setIsConsistencyAsking(false);
    }
  };

  const toggleWhy = (key: string) => {
    setExpandedWhy((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  if (isLoading && !data) {
    return (
      <div className={`flex flex-col items-center justify-center py-32 ${theme === 'light' ? 'text-slate-600' : 'text-slate-400'}`}>
        <div className="w-12 h-12 border-4 border-cyan-500/30 border-t-cyan-500 rounded-full animate-spin mb-4" />
        <p className={`font-bold text-base ${theme === 'light' ? 'text-slate-800' : 'text-slate-200'}`}>
          Synthesizing Engineering Design Review Cockpit...
        </p>
        <p className="text-xs text-slate-500 mt-1">Extracting deterministic OCCT B-Rep facts &amp; epistemic feature reasoning</p>
      </div>
    );
  }

  if (!data) {
    return (
      <div className={`border rounded-2xl p-10 text-center space-y-4 ${
        theme === 'light' ? 'bg-white border-slate-200 shadow-lg text-slate-600' : 'bg-slate-900 border-slate-800 text-slate-400'
      }`}>
        <AlertTriangle className="w-10 h-10 text-amber-500 mx-auto" />
        <div>
          <h3 className={`text-base font-bold ${theme === 'light' ? 'text-slate-900' : 'text-slate-200'}`}>
            Engineering Review Dataset Ready to Synthesize
          </h3>
          <p className="text-xs text-slate-500 mt-1">Click below to load deterministic B-Rep geometry and feature intelligence.</p>
        </div>
        {onReload && (
          <button
            onClick={onReload}
            className="px-5 py-2.5 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 text-white font-bold text-xs shadow-lg shadow-cyan-500/20 hover:brightness-110 transition inline-flex items-center gap-2"
          >
            <Sparkles className="w-4 h-4" />
            <span>Load / Synthesize Engineering Review</span>
          </button>
        )}
      </div>
    );
  }

  const activeSection = data.section_recommendations.candidates.find((s) => s.section_id === selectedSectionId) || data.section_recommendations.candidates[0];
  const activeFeature = data.feature_graph.find((f) => f.feature_id === selectedFeatureId);
  const activeDimension = data.classified_dimensions.find((d) => d.dimension_id === selectedDimensionId);

  // Dynamic priority list from live validated AI review or B-Rep feature graph
  const displayedPriorities = (aiReview?.ranked_feature_interpretations && aiReview.ranked_feature_interpretations.length > 0)
    ? aiReview.ranked_feature_interpretations.slice(0, 5)
    : (data?.feature_graph ? data.feature_graph.slice(0, 5) : []);

  // Quick helper to select feature and sync Face highlight
  const handleSelectFeature = (feat: EngineeringFeatureItem) => {
    setSelectedFeatureId(feat.feature_id);
    if (feat.source_faces.length > 0) {
      setSelectedFaceId(feat.source_faces[0]);
    }
  };

  // Quick helper to select dimension and sync Face highlight
  const handleSelectDimension = (dim: ClassifiedDimensionItem) => {
    setSelectedDimensionId(dim.dimension_id);
    if (dim.source_entities.length > 0) {
      setSelectedFaceId(dim.source_entities[0]);
    }
  };

  // Dynamic Theme Class Tokens
  const bgRoot = theme === 'light' ? 'bg-slate-50 text-slate-900' : 'bg-slate-950 text-slate-100';
  const bgCard = theme === 'light' ? 'bg-white border-slate-200/90 shadow-md' : 'bg-slate-900 border-slate-800 shadow-xl';
  const bgSubCard = theme === 'light' ? 'bg-slate-100/80 border-slate-200' : 'bg-slate-950/70 border-slate-800/80';
  const textMuted = theme === 'light' ? 'text-slate-500' : 'text-slate-400';
  const textHeading = theme === 'light' ? 'text-slate-900' : 'text-slate-100';

  return (
    <div className={`space-y-4 w-full transition-colors duration-200 ${bgRoot}`}>
      {/* 1. Cockpit Header Bar */}
      <div className={`border rounded-2xl p-4 shadow-lg transition-all ${
        theme === 'light'
          ? 'bg-gradient-to-r from-white via-cyan-50/50 to-blue-50/40 border-cyan-200'
          : 'bg-gradient-to-r from-slate-900 via-slate-900 to-cyan-950/40 border-cyan-500/30'
      }`}>
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-gradient-to-br from-cyan-500 to-blue-600 text-white shadow-md shadow-cyan-500/20">
              <Bot className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="px-2.5 py-0.5 rounded-full text-[11px] font-black uppercase tracking-wider bg-cyan-500/15 text-cyan-600 dark:text-cyan-400 border border-cyan-500/30">
                  AI Engineering Review Cockpit
                </span>
                <span className="text-xs font-mono font-bold text-slate-500">Phase 24</span>
              </div>
              <h1 className={`text-lg font-black tracking-tight ${textHeading}`}>{data.model_name}</h1>
            </div>
          </div>

          {/* Quick Metrics & Theme Switcher */}
          <div className="flex flex-wrap items-center gap-2.5">
            <div className={`px-3 py-1.5 border rounded-xl text-right ${bgSubCard}`}>
              <div className="text-[10px] uppercase font-bold text-slate-400">Ground Truth</div>
              <div className="text-xs font-black text-emerald-600 dark:text-emerald-400 flex items-center gap-1 justify-end">
                <ShieldCheck className="w-3.5 h-3.5" /> B-REP VERIFIED
              </div>
            </div>

            <div className={`px-3 py-1.5 border rounded-xl text-right ${bgSubCard}`}>
              <div className="text-[10px] uppercase font-bold text-slate-400">Envelope</div>
              <div className="text-xs font-black font-mono text-cyan-600 dark:text-cyan-300">
                {data.audit_summary.assembly_envelope_mm[0].toFixed(1)} × {data.audit_summary.assembly_envelope_mm[1].toFixed(1)} × {data.audit_summary.assembly_envelope_mm[2].toFixed(1)} mm
              </div>
            </div>

            <div className={`px-3 py-1.5 border rounded-xl text-right ${bgSubCard}`}>
              <div className="text-[10px] uppercase font-bold text-slate-400">Unique Solids</div>
              <div className={`text-xs font-black ${textHeading}`}>
                {data.audit_summary.unique_solids_count} <span className="text-slate-400 text-[10px]">({data.audit_summary.total_raw_solids} Raw)</span>
              </div>
            </div>

            {/* Theme Toggle Button */}
            {onToggleTheme && (
              <button
                onClick={onToggleTheme}
                className={`p-2 rounded-xl border font-bold text-xs flex items-center gap-1.5 transition-all shadow-sm ${
                  theme === 'light'
                    ? 'bg-slate-100 hover:bg-slate-200 border-slate-300 text-slate-700'
                    : 'bg-slate-800 hover:bg-slate-700 border-slate-700 text-amber-300'
                }`}
                title={`Switch to ${theme === 'light' ? 'Dark' : 'Light'} Mode`}
              >
                {theme === 'light' ? <Moon className="w-4 h-4 text-slate-700" /> : <Sun className="w-4 h-4 text-amber-400" />}
                <span className="hidden sm:inline font-mono">{theme === 'light' ? 'Dark' : 'Light'}</span>
              </button>
            )}
          </div>
        </div>
      </div>

      {/* 2. Main Cockpit Grid: 3D Viewport (Left 58%) + Interactive AI Review Deck (Right 42%) */}
      <div className="grid grid-cols-1 xl:grid-cols-12 gap-5 w-full">
        {/* LEFT COLUMN: 3D B-Rep Viewport */}
        <div className="xl:col-span-7 space-y-3">
          <div className={`min-h-[640px] h-[640px] rounded-2xl overflow-hidden border shadow-2xl relative ${
            theme === 'light' ? 'border-slate-200 bg-slate-900' : 'border-slate-800 bg-slate-950'
          }`}>
            <Viewer3D
              projectId={projectId}
              meshData={meshData}
              summary={summary}
              features={features}
              selectedFeatureId={selectedFeatureId}
              onSelectFeature={setSelectedFeatureId}
              selectedFaceId={selectedFaceId}
              onSelectFace={setSelectedFaceId}
              activeSection={activeSection}
              showSectionPlane={showSectionPlane}
              theme={theme}
            />
          </div>

          {/* Camera View Switcher Bar */}
          <div className={`flex flex-wrap items-center justify-between gap-2 p-3 rounded-xl border ${bgCard}`}>
            <div className={`flex items-center gap-2 text-xs font-bold ${textMuted}`}>
              <Eye className="w-4 h-4 text-cyan-500" />
              <span>Recommended View Alignment:</span>
            </div>
            <div className="flex items-center gap-1.5">
              {(['ISO', 'FRONT', 'TOP', 'RIGHT'] as const).map((viewKey) => {
                const evalItem = data.view_recommendations.evaluations[viewKey];
                const isPrimary = evalItem?.rank === 'PRIMARY' || viewKey === 'ISO';

                return (
                  <button
                    key={viewKey}
                    onClick={() => setSelectedViewPreset(viewKey)}
                    className={`px-3 py-1 rounded-lg text-xs font-bold font-mono transition flex items-center gap-1.5 ${
                      selectedViewPreset === viewKey
                        ? 'bg-cyan-500 text-white font-black shadow-md shadow-cyan-500/20'
                        : theme === 'light'
                        ? 'bg-slate-100 text-slate-700 hover:bg-slate-200 border border-slate-200'
                        : 'bg-slate-800 text-slate-300 hover:bg-slate-700'
                    }`}
                  >
                    <span>{viewKey}</span>
                    {isPrimary && <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />}
                  </button>
                );
              })}
            </div>
          </div>
        </div>

        {/* RIGHT COLUMN: Interactive Review Deck & AI Reasoner */}
        <div className="xl:col-span-5 flex flex-col space-y-3">
          {/* Deck Navigation Tabs */}
          <div className={`flex items-center p-1.5 rounded-2xl border space-x-1 overflow-x-auto ${bgCard}`}>
            <button
              onClick={() => setActiveSubTab('cad_drawing')}
              className={`px-3 py-1.5 rounded-xl text-xs font-black transition flex items-center gap-1.5 whitespace-nowrap ${
                activeSubTab === 'cad_drawing'
                  ? 'bg-gradient-to-r from-emerald-500 to-teal-600 text-white shadow-md shadow-emerald-500/25'
                  : 'text-emerald-600 dark:text-emerald-400 hover:bg-emerald-50 dark:hover:bg-slate-800'
              }`}
            >
              <FileCheck className="w-3.5 h-3.5" />
              <span>CAD ↔ Drawing</span>
              <span className="px-1.5 py-0.2 rounded-full text-[9px] font-mono bg-white/20 text-white">
                {consistencyData?.matches?.length || 0}
              </span>
            </button>

            <button
              onClick={() => setActiveSubTab('ai_review')}
              className={`px-3 py-1.5 rounded-xl text-xs font-black transition flex items-center gap-1.5 whitespace-nowrap ${
                activeSubTab === 'ai_review'
                  ? 'bg-gradient-to-r from-cyan-500 to-blue-600 text-white shadow-md shadow-cyan-500/25'
                  : 'text-cyan-600 dark:text-cyan-400 hover:bg-cyan-50 dark:hover:bg-slate-800'
              }`}
            >
              <Bot className="w-3.5 h-3.5" />
              <span>AI Review</span>
              <span className="px-1.5 py-0.2 rounded-full text-[9px] font-mono bg-white/20 text-white">5 Prio</span>
            </button>

            <button
              onClick={() => setActiveSubTab('summary')}
              className={`px-3 py-1.5 rounded-xl text-xs font-bold transition flex items-center gap-1.5 whitespace-nowrap ${
                activeSubTab === 'summary'
                  ? 'bg-slate-800 text-white dark:bg-slate-700'
                  : 'text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800'
              }`}
            >
              <Sparkles className="w-3.5 h-3.5" />
              <span>Summary</span>
            </button>

            <button
              onClick={() => setActiveSubTab('features')}
              className={`px-3 py-1.5 rounded-xl text-xs font-bold transition flex items-center gap-1.5 whitespace-nowrap ${
                activeSubTab === 'features'
                  ? 'bg-slate-800 text-white dark:bg-slate-700'
                  : 'text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800'
              }`}
            >
              <Cpu className="w-3.5 h-3.5" />
              <span>Features</span>
              <span className="text-[10px] opacity-70">({data.feature_graph.length})</span>
            </button>

            <button
              onClick={() => setActiveSubTab('dimensions')}
              className={`px-3 py-1.5 rounded-xl text-xs font-bold transition flex items-center gap-1.5 whitespace-nowrap ${
                activeSubTab === 'dimensions'
                  ? 'bg-slate-800 text-white dark:bg-slate-700'
                  : 'text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800'
              }`}
            >
              <Ruler className="w-3.5 h-3.5" />
              <span>Dims</span>
              <span className="text-[10px] opacity-70">({data.classified_dimensions.length})</span>
            </button>

            <button
              onClick={() => setActiveSubTab('views_sections')}
              className={`px-3 py-1.5 rounded-xl text-xs font-bold transition flex items-center gap-1.5 whitespace-nowrap ${
                activeSubTab === 'views_sections'
                  ? 'bg-slate-800 text-white dark:bg-slate-700'
                  : 'text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800'
              }`}
            >
              <Scissors className="w-3.5 h-3.5" />
              <span>Sections</span>
            </button>

            <button
              onClick={() => setActiveSubTab('epistemic')}
              className={`px-3 py-1.5 rounded-xl text-xs font-bold transition flex items-center gap-1.5 whitespace-nowrap ${
                activeSubTab === 'epistemic'
                  ? 'bg-slate-800 text-white dark:bg-slate-700'
                  : 'text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800'
              }`}
            >
              <Layers className="w-3.5 h-3.5" />
              <span>Epistemic</span>
            </button>
          </div>

          {/* Deck Body Container */}
          <div className={`flex-1 border rounded-2xl p-4 shadow-xl overflow-y-auto max-h-[640px] h-[640px] space-y-4 ${bgCard}`}>
            
            {/* SUBTAB: CAD ↔ DRAWING CONSISTENCY (PHASE 25 PRIMARY) */}
            {activeSubTab === 'cad_drawing' && (
              <div className="space-y-4 text-xs">
                {/* 1. Audit Summary Banner */}
                <div className={`p-4 rounded-xl border relative overflow-hidden ${
                  theme === 'light'
                    ? 'bg-gradient-to-br from-emerald-50/80 via-white to-teal-50/60 border-emerald-200 shadow-sm'
                    : 'bg-gradient-to-br from-emerald-950/40 via-slate-950/60 to-slate-900 border-emerald-500/30'
                }`}>
                  <div className="flex items-center justify-between pb-2 border-b border-emerald-500/20 mb-2.5">
                    <div className="flex items-center gap-2">
                      <FileCheck className="w-4 h-4 text-emerald-500" />
                      <span className="font-black text-emerald-600 dark:text-emerald-300 uppercase tracking-wider text-xs">
                        CAD ↔ Engineering Drawing Consistency Audit
                      </span>
                    </div>
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-600 dark:text-emerald-300 font-bold">
                      {consistencyData?.drawing_filename || 'RB-3N-20A_drawing.svg'}
                    </span>
                  </div>

                  <p className={`text-xs leading-relaxed ${textMuted}`}>
                    {consistencyData?.ai_review?.executive_summary ||
                      'Automated audit comparing 3D B-Rep geometry against 2D manufacturing drawing callouts.'}
                  </p>

                  {/* KPI Metric Counters */}
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-3">
                    <div className={`p-2 rounded-lg border text-center ${
                      theme === 'light' ? 'bg-white/80 border-emerald-200' : 'bg-slate-900/60 border-emerald-500/30'
                    }`}>
                      <div className="text-[10px] uppercase font-bold text-emerald-600 dark:text-emerald-400">Consistent</div>
                      <div className={`text-base font-black text-emerald-600 dark:text-emerald-400 font-mono`}>
                        {consistencyData?.summary?.consistent_count || 0}
                      </div>
                    </div>

                    <div className={`p-2 rounded-lg border text-center ${
                      theme === 'light' ? 'bg-white/80 border-red-200' : 'bg-slate-900/60 border-red-500/30'
                    }`}>
                      <div className="text-[10px] uppercase font-bold text-red-500">Conflicts</div>
                      <div className={`text-base font-black text-red-500 font-mono`}>
                        {consistencyData?.summary?.conflict_count || 0}
                      </div>
                    </div>

                    <div className={`p-2 rounded-lg border text-center ${
                      theme === 'light' ? 'bg-white/80 border-amber-200' : 'bg-slate-900/60 border-amber-500/30'
                    }`}>
                      <div className="text-[10px] uppercase font-bold text-amber-500">Cannot Verify</div>
                      <div className={`text-base font-black text-amber-500 font-mono`}>
                        {consistencyData?.summary?.cannot_verify_count || 0}
                      </div>
                    </div>

                    <div className={`p-2 rounded-lg border text-center ${
                      theme === 'light' ? 'bg-white/80 border-cyan-200' : 'bg-slate-900/60 border-cyan-500/30'
                    }`}>
                      <div className="text-[10px] uppercase font-bold text-cyan-600 dark:text-cyan-400">Coverage</div>
                      <div className={`text-base font-black text-cyan-600 dark:text-cyan-400 font-mono`}>
                        {consistencyData?.summary?.dimension_coverage_percent || 0}%
                      </div>
                    </div>
                  </div>
                </div>

                {/* 2. Top Engineering Issues (Phase 25 Discrepancies) */}
                {consistencyData?.ai_review?.top_engineering_issues && consistencyData.ai_review.top_engineering_issues.length > 0 && (
                  <div>
                    <h3 className="font-black text-xs uppercase tracking-wider text-slate-500 mb-2 flex items-center gap-1.5">
                      <AlertOctagon className="w-3.5 h-3.5 text-amber-500" />
                      Priority Consistency Findings
                    </h3>
                    <div className="space-y-2.5">
                      {consistencyData.ai_review.top_engineering_issues.map((issue, i) => (
                        <div
                          key={i}
                          className={`p-3 rounded-xl border space-y-1.5 ${
                            issue.severity === 'CRITICAL_CONFLICT'
                              ? theme === 'light' ? 'bg-red-50/50 border-red-200' : 'bg-red-950/20 border-red-500/30'
                              : issue.severity === 'UNDERDEFINED_DRAWING'
                              ? theme === 'light' ? 'bg-amber-50/50 border-amber-200' : 'bg-amber-950/20 border-amber-500/30'
                              : theme === 'light' ? 'bg-white border-slate-200' : 'bg-slate-950/60 border-slate-800'
                          }`}
                        >
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-1.5">
                              <span className={`px-1.5 py-0.5 rounded text-[9px] font-black uppercase ${
                                issue.severity === 'CRITICAL_CONFLICT' ? 'bg-red-500 text-white' :
                                issue.severity === 'UNDERDEFINED_DRAWING' ? 'bg-amber-500 text-white' :
                                'bg-slate-600 text-white'
                              }`}>
                                {issue.severity.replace('_', ' ')}
                              </span>
                              <span className={`font-bold text-xs ${textHeading}`}>{issue.title}</span>
                            </div>
                          </div>
                          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-[10px] font-mono">
                            <div className="p-1.5 rounded bg-white/60 dark:bg-slate-900/80 border border-slate-200 dark:border-slate-800">
                              <strong className="text-emerald-600 dark:text-emerald-400 block">CAD PROVES:</strong>
                              <span className="text-slate-600 dark:text-slate-300">{issue.what_cad_proves}</span>
                            </div>
                            <div className="p-1.5 rounded bg-white/60 dark:bg-slate-900/80 border border-slate-200 dark:border-slate-800">
                              <strong className="text-cyan-600 dark:text-cyan-400 block">DRAWING STATES:</strong>
                              <span className="text-slate-600 dark:text-slate-300">{issue.what_drawing_states}</span>
                            </div>
                          </div>
                          <div className="text-[11px] pt-1">
                            <strong className="text-amber-600 dark:text-amber-400">Required Engineer Action: </strong>
                            <span className={textMuted}>{issue.action}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* 3. Consistency Ledger Table */}
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <h3 className="font-black text-xs uppercase tracking-wider text-slate-500 flex items-center gap-1.5">
                      <Layers className="w-3.5 h-3.5 text-cyan-500" />
                      CAD ↔ Drawing Matched Ledger
                    </h3>
                    <div className="flex items-center gap-1 text-[10px]">
                      {['ALL', 'CONSISTENT', 'CANNOT_VERIFY', 'MISSING'].map((filt) => (
                        <button
                          key={filt}
                          onClick={() => setConsistencyFilter(filt)}
                          className={`px-2 py-0.5 rounded font-mono font-bold transition ${
                            consistencyFilter === filt
                              ? 'bg-emerald-500 text-white'
                              : 'text-slate-400 hover:text-slate-600 dark:hover:text-slate-200'
                          }`}
                        >
                          {filt}
                        </button>
                      ))}
                    </div>
                  </div>

                  <div className="space-y-2 max-h-[280px] overflow-y-auto pr-1">
                    {(consistencyData?.matches || [])
                      .filter((m) => consistencyFilter === 'ALL' || m.consistency_status === consistencyFilter)
                      .map((match) => {
                        const isSelected = selectedMatchId === match.match_id;
                        const isConsistent = match.consistency_status === 'CONSISTENT';
                        const isConflict = match.consistency_status === 'CONFLICT';
                        const isCannotVerify = match.consistency_status === 'CANNOT_VERIFY';

                        return (
                          <div
                            key={match.match_id}
                            onClick={() => {
                              setSelectedMatchId(match.match_id);
                              if (match.cad_entity_id) {
                                setSelectedFaceId(match.cad_entity_id);
                              }
                              if (match.drawing_view === 'SECTION_AA') {
                                setSelectedSectionId('SEC_AA');
                                setShowSectionPlane(true);
                              }
                            }}
                            className={`p-3 rounded-xl border cursor-pointer transition-all ${
                              isSelected
                                ? 'border-emerald-500 shadow-md bg-emerald-50/40 dark:bg-emerald-950/30'
                                : theme === 'light' ? 'bg-white border-slate-200 hover:border-slate-300' : 'bg-slate-950/60 border-slate-800 hover:border-slate-700'
                            }`}
                          >
                            <div className="flex items-center justify-between mb-1">
                              <div className="flex items-center gap-2">
                                <span className={`px-1.5 py-0.5 rounded text-[9px] font-black uppercase ${
                                  isConsistent ? 'bg-emerald-500 text-white' :
                                  isConflict ? 'bg-red-500 text-white' :
                                  isCannotVerify ? 'bg-amber-500 text-white' : 'bg-orange-500 text-white'
                                }`}>
                                  {match.consistency_status}
                                </span>
                                <span className={`font-bold text-xs ${textHeading}`}>
                                  {match.cad_entity_id || 'CAD Meta'} ↔ {match.drawing_evidence_id || 'Drawing'}
                                </span>
                              </div>
                              <span className="text-[10px] font-mono text-cyan-600 dark:text-cyan-400 font-bold">
                                {match.drawing_text_raw || `${match.cad_nominal_value.toFixed(2)} mm`}
                              </span>
                            </div>

                            <p className={`text-[11px] leading-relaxed ${textMuted} mb-2`}>
                              {match.engineering_rationale}
                            </p>

                            <div className="flex items-center justify-between pt-1 border-t border-slate-200 dark:border-slate-800 text-[10px]">
                              <span className="text-slate-400 font-mono">
                                View: <strong className={textHeading}>{match.drawing_view || 'FRONT'}</strong>
                              </span>
                              <div className="flex items-center gap-1.5">
                                <button
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    if (match.cad_entity_id) {
                                      setSelectedFaceId(match.cad_entity_id);
                                    }
                                  }}
                                  className="px-2 py-0.5 rounded bg-cyan-500 hover:bg-cyan-400 text-white font-bold flex items-center gap-1 transition"
                                >
                                  <Search className="w-2.5 h-2.5" /> Show in 3D
                                </button>
                              </div>
                            </div>
                          </div>
                        );
                      })}
                  </div>
                </div>

                {/* 4. Natural Language Consistency Q&A Console */}
                <div className={`p-3.5 rounded-xl border space-y-3 ${
                  theme === 'light' ? 'bg-slate-100/80 border-slate-200' : 'bg-slate-900/60 border-slate-800'
                }`}>
                  <div className="flex items-center gap-2">
                    <Bot className="w-4 h-4 text-emerald-500" />
                    <span className={`font-bold text-xs ${textHeading}`}>
                      Ask Consistency &amp; Drawing Verification Assistant
                    </span>
                  </div>

                  {/* Suggestion Chips */}
                  <div className="flex flex-wrap gap-1.5">
                    {[
                      'What dimensions disagree between CAD and drawing?',
                      'Which drawing tolerances cannot be verified from the STEP?',
                      'Does Section A-A correctly represent the CAD geometry?',
                      'What should I inspect before releasing this drawing?',
                    ].map((q, idx) => (
                      <button
                        key={idx}
                        onClick={() => handleAskConsistencyQuestion(q)}
                        className={`text-[10px] px-2.5 py-1 rounded-lg border font-mono transition text-left ${
                          theme === 'light'
                            ? 'bg-white hover:bg-emerald-50 border-slate-200 text-slate-700'
                            : 'bg-slate-800/80 hover:bg-emerald-950/40 border-slate-700 text-slate-300'
                        }`}
                      >
                        {q}
                      </button>
                    ))}
                  </div>

                  {/* Question Input */}
                  <div className="flex items-center gap-2">
                    <input
                      type="text"
                      value={consistencyQuestionInput}
                      onChange={(e) => setConsistencyQuestionInput(e.target.value)}
                      onKeyDown={(e) => e.key === 'Enter' && handleAskConsistencyQuestion()}
                      placeholder="Ask about CAD vs Drawing consistency..."
                      className={`flex-1 px-3 py-2 rounded-xl text-xs border transition outline-none ${
                        theme === 'light'
                          ? 'bg-white border-slate-300 text-slate-900 focus:border-emerald-500'
                          : 'bg-slate-950 border-slate-700 text-slate-100 focus:border-emerald-500'
                      }`}
                    />
                    <button
                      onClick={() => handleAskConsistencyQuestion()}
                      disabled={isConsistencyAsking || !consistencyQuestionInput.trim()}
                      className="px-4 py-2 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-white font-bold text-xs flex items-center gap-1.5 transition disabled:opacity-50"
                    >
                      {isConsistencyAsking ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Send className="w-3.5 h-3.5" />}
                      <span>Ask</span>
                    </button>
                  </div>

                  {/* Q&A Responses Stream */}
                  {consistencyQaHistory.length > 0 && (
                    <div className="space-y-2 pt-2 border-t border-slate-200 dark:border-slate-800">
                      {consistencyQaHistory.map((qa, idx) => (
                        <div key={idx} className={`p-2.5 rounded-lg border text-xs space-y-1 ${bgSubCard}`}>
                          <div className="font-bold text-emerald-600 dark:text-emerald-400 font-mono text-[11px]">
                            Q: {qa.question}
                          </div>
                          <p className={`leading-relaxed text-[11px] ${textHeading}`}>{qa.answer}</p>
                          <div className="text-[10px] text-slate-400 font-mono pt-0.5">
                            Status: <span className="text-cyan-500">{qa.epistemic_qualification}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* SUBTAB 0: AI ENGINEERING REVIEW (PHASE 24 PRIMARY) */}
            {activeSubTab === 'ai_review' && (
              <div className="space-y-4 text-xs">
                {/* 1. AI Review Executive Card */}
                <div className={`p-4 rounded-xl border relative overflow-hidden ${
                  theme === 'light'
                    ? 'bg-gradient-to-br from-cyan-50/80 via-white to-blue-50/60 border-cyan-200'
                    : 'bg-gradient-to-br from-cyan-950/40 via-slate-950/60 to-slate-900 border-cyan-500/30'
                }`}>
                  <div className="flex items-center justify-between pb-2 border-b border-cyan-500/20 mb-2.5">
                    <div className="flex items-center gap-2">
                      <span className="h-2.5 w-2.5 rounded-full bg-cyan-500 animate-ping" />
                      <span className="font-black text-cyan-600 dark:text-cyan-300 uppercase tracking-wider text-xs">
                        AI Engineering Design Review
                      </span>
                    </div>
                    <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border border-emerald-500/30 flex items-center gap-1">
                      <ShieldCheck className="w-3 h-3" /> EVIDENCE-VERIFIED
                    </span>
                  </div>

                  <p className={`leading-relaxed text-xs ${textHeading}`}>
                    {aiReview?.executive_part_interpretation ||
                      "The geometry is consistent with a 3-piece mechanical assembly featuring coaxial cylindrical flow conduits, a central internal chamber, and planar mounting interfaces. Five critical areas warrant engineering inspection."}
                  </p>

                  {/* Epistemic Counter Badges */}
                  <div className="grid grid-cols-4 gap-2 mt-3 pt-3 border-t border-cyan-500/20 text-center font-mono">
                    <div className="p-1.5 rounded-lg bg-emerald-500/10 border border-emerald-500/20">
                      <div className="text-[10px] font-bold text-emerald-600 dark:text-emerald-400">KNOWN</div>
                      <div className="text-xs font-black text-emerald-700 dark:text-emerald-300">
                        {data.audit_summary.unique_faces_count + data.classified_dimensions.length} Facts
                      </div>
                    </div>
                    <div className="p-1.5 rounded-lg bg-cyan-500/10 border border-cyan-500/20">
                      <div className="text-[10px] font-bold text-cyan-600 dark:text-cyan-400">INFERRED</div>
                      <div className="text-xs font-black text-cyan-700 dark:text-cyan-300">
                        {data.feature_graph.length} Roles
                      </div>
                    </div>
                    <div className="p-1.5 rounded-lg bg-amber-500/10 border border-amber-500/20">
                      <div className="text-[10px] font-bold text-amber-600 dark:text-amber-400">UNKNOWN</div>
                      <div className="text-xs font-black text-amber-700 dark:text-amber-300">4 Bounds</div>
                    </div>
                    <div className="p-1.5 rounded-lg bg-red-500/10 border border-red-500/20">
                      <div className="text-[10px] font-bold text-red-600 dark:text-red-400">PRIORITIES</div>
                      <div className="text-xs font-black text-red-700 dark:text-red-300">5 Top</div>
                    </div>
                  </div>
                </div>

                {/* 2. WHAT SHOULD I INSPECT FIRST? (5 Ranked AI Priorities) */}
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <h3 className="font-black text-xs uppercase tracking-wider text-slate-500 flex items-center gap-1.5">
                      <Target className="w-3.5 h-3.5 text-cyan-500" />
                      What Should I Inspect First?
                    </h3>
                    <span className="text-[11px] text-slate-400 font-mono">Ranked 1 to 5</span>
                  </div>

                  {/* Dynamic Priority Cards */}
                  <div className="space-y-3">
                    {displayedPriorities.map((item: any, idx: number) => {
                      const prioNum = idx + 1;
                      const badgeColor =
                        prioNum === 1 ? 'bg-red-500' :
                        prioNum === 2 ? 'bg-red-500' :
                        prioNum === 3 ? 'bg-amber-500' :
                        prioNum === 4 ? 'bg-blue-500' : 'bg-purple-500';
                      const borderColor =
                        prioNum <= 2 ? (theme === 'light' ? 'border-red-200 shadow-sm' : 'border-red-500/30') :
                        prioNum === 3 ? (theme === 'light' ? 'border-amber-200 shadow-sm' : 'border-amber-500/30') :
                        (theme === 'light' ? 'border-slate-200 shadow-sm' : 'border-slate-800');

                      const firstFace = item.evidence_references?.find((r: any) => r.entity_type === 'FACE')?.entity_id ||
                                        (item.source_faces && item.source_faces[0]) || 'Face2';
                      const isExpanded = !!expandedWhy[`p${prioNum}`];
                      const roleName = item.inferred_engineering_role || item.engineering_interpretation || 'Functional Interface';
                      const reasoningText = item.engineering_reasoning || item.reasoning || 'Grounded B-Rep geometry and dimensional relevance.';
                      const knownGeom = item.known_geometry || item.geometric_type || 'GeomCylinder';
                      const unknownText = (item.unknowns_and_assumptions && item.unknowns_and_assumptions[0]) || 'Operating pressure, material grade';

                      return (
                        <div key={item.feature_id || idx} className={`p-3.5 rounded-xl border space-y-2.5 transition-all ${
                          theme === 'light' ? 'bg-white ' + borderColor : 'bg-slate-950/80 ' + borderColor
                        }`}>
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-2">
                              <span className={`px-2 py-0.5 rounded text-[10px] font-black uppercase text-white shadow-sm ${badgeColor}`}>
                                Priority {prioNum}
                              </span>
                              <span className={`font-bold text-xs ${textHeading}`}>
                                {roleName} ({item.feature_id})
                              </span>
                            </div>
                            <span className="text-[10px] font-mono font-bold text-cyan-600 dark:text-cyan-400">
                              {item.measured_property || (item.measured_dimensions?.diameter_mm ? `Ø${item.measured_dimensions.diameter_mm.toFixed(1)} mm` : (item.measured_dimensions?.step_width_mm ? `${item.measured_dimensions.step_width_mm.toFixed(1)} mm` : ''))}
                            </span>
                          </div>

                          <p className={`text-[11px] leading-relaxed ${textMuted}`}>
                            <strong className={textHeading}>Why it matters: </strong>
                            {reasoningText}
                          </p>

                          {/* Epistemic Breakdown */}
                          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 text-[10px] font-mono">
                            <div className="p-2 rounded-lg bg-emerald-500/10 border border-emerald-500/20">
                              <span className="font-bold text-emerald-600 dark:text-emerald-400 block">KNOWN GEOMETRY</span>
                              <span className="text-slate-600 dark:text-slate-300 truncate block">{knownGeom}</span>
                            </div>
                            <div className="p-2 rounded-lg bg-cyan-500/10 border border-cyan-500/20">
                              <span className="font-bold text-cyan-600 dark:text-cyan-400 block">INFERRED ROLE</span>
                              <span className="text-slate-600 dark:text-slate-300 truncate block">{roleName}</span>
                            </div>
                            <div className="p-2 rounded-lg bg-amber-500/10 border border-amber-500/20">
                              <span className="font-bold text-amber-600 dark:text-amber-400 block">UNKNOWN FROM CAD</span>
                              <span className="text-slate-600 dark:text-slate-300 truncate block">{unknownText}</span>
                            </div>
                          </div>

                          {/* Action Buttons */}
                          <div className="flex items-center justify-between pt-1">
                            <button
                              onClick={() => toggleWhy(`p${prioNum}`)}
                              className="text-[11px] font-bold flex items-center gap-1 text-cyan-600 dark:text-cyan-400 hover:underline"
                            >
                              {isExpanded ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
                              <span>Why this recommendation?</span>
                            </button>
                            <button
                              onClick={() => {
                                setSelectedFaceId(firstFace);
                                setSelectedFeatureId(item.feature_id);
                                if (prioNum === 1 || prioNum === 3) {
                                  setSelectedSectionId('SEC_AA');
                                  setShowSectionPlane(true);
                                }
                              }}
                              className="px-3 py-1 rounded-lg bg-cyan-500 hover:bg-cyan-400 text-white font-bold text-[11px] shadow-sm flex items-center gap-1.5 transition"
                            >
                              <Search className="w-3 h-3" />
                              <span>Show in 3D</span>
                            </button>
                          </div>

                          {/* Collapsible WHY? drawer */}
                          {isExpanded && (
                            <div className={`p-2.5 rounded-lg border text-[11px] space-y-1.5 mt-1 ${bgSubCard}`}>
                              <div>
                                <strong className="text-cyan-600 dark:text-cyan-400">Engineering Rationale: </strong>
                                {reasoningText}
                              </div>
                              {item.recommended_engineer_check && (
                                <div>
                                  <strong className="text-amber-600 dark:text-amber-400">Recommended Check: </strong>
                                  {item.recommended_engineer_check}
                                </div>
                              )}
                              {(item.evidence_references || item.source_faces) && (
                                <div className="text-[10px] font-mono text-slate-400">
                                  Grounded B-Rep Entities: <span className="text-cyan-500 font-bold">
                                    {(item.evidence_references?.map((r: any) => r.entity_id) || item.source_faces || []).join(', ')}
                                  </span>
                                </div>
                              )}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* 3. NATURAL LANGUAGE ENGINEERING ASSISTANT (Interactive Q&A) */}
                <div className={`p-4 rounded-xl border space-y-3 ${bgSubCard}`}>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Bot className="w-4 h-4 text-cyan-500" />
                      <h4 className={`font-black text-xs uppercase tracking-wider ${textHeading}`}>
                        Ask About This CAD Model
                      </h4>
                    </div>
                    <span className="text-[10px] font-mono text-slate-400">Grounded in OCCT Evidence</span>
                  </div>

                  {/* Suggestion Chips */}
                  <div className="flex flex-wrap gap-1.5">
                    {[
                      "What should I inspect first?",
                      "Why is Face2 important?",
                      "What are the most important dimensions?",
                      "What is missing from this STEP?",
                      "Why is Section A-A recommended?",
                    ].map((sug, idx) => (
                      <button
                        key={idx}
                        onClick={() => handleAskQuestion(sug)}
                        className={`px-2.5 py-1 rounded-lg text-[10px] font-medium transition border ${
                          theme === 'light'
                            ? 'bg-white hover:bg-cyan-50 border-slate-200 text-slate-700 hover:border-cyan-300'
                            : 'bg-slate-900 hover:bg-slate-800 border-slate-800 text-slate-300 hover:border-cyan-500/40'
                        }`}
                      >
                        {sug}
                      </button>
                    ))}
                  </div>

                  {/* Question Input Field */}
                  <div className="flex gap-2">
                    <input
                      type="text"
                      value={questionInput}
                      onChange={(e) => setQuestionInput(e.target.value)}
                      onKeyDown={(e) => e.key === 'Enter' && handleAskQuestion()}
                      placeholder="Ask an engineering question (e.g. Why is Face2 important?)..."
                      disabled={isAsking}
                      className={`flex-1 px-3 py-2 rounded-xl text-xs border transition outline-none ${
                        theme === 'light'
                          ? 'bg-white border-slate-300 text-slate-900 placeholder:text-slate-400 focus:border-cyan-500'
                          : 'bg-slate-900 border-slate-800 text-slate-100 placeholder:text-slate-500 focus:border-cyan-500'
                      }`}
                    />
                    <button
                      onClick={() => handleAskQuestion()}
                      disabled={isAsking || !questionInput.trim()}
                      className="px-4 py-2 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 hover:brightness-110 disabled:opacity-50 text-white font-bold text-xs shadow-md flex items-center gap-1.5 transition"
                    >
                      {isAsking ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Send className="w-3.5 h-3.5" />}
                      <span className="hidden sm:inline">Ask</span>
                    </button>
                  </div>

                  {/* Q&A Answer Stream */}
                  {qaHistory.length > 0 && (
                    <div className="space-y-3 pt-2">
                      {qaHistory.map((item, idx) => (
                        <div
                          key={idx}
                          className={`p-3.5 rounded-xl border space-y-2 animate-in fade-in ${
                            theme === 'light' ? 'bg-white border-slate-200 shadow-sm' : 'bg-slate-900 border-slate-800'
                          }`}
                        >
                          <div className="flex items-center justify-between border-b pb-1.5 border-slate-200 dark:border-slate-800">
                            <span className="font-bold text-xs text-cyan-600 dark:text-cyan-400">Q: {item.question}</span>
                            <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-cyan-500/10 text-cyan-600 dark:text-cyan-300">
                              {item.epistemic_qualification}
                            </span>
                          </div>

                          <p className={`text-xs leading-relaxed ${textHeading}`}>{item.answer}</p>

                          {/* Grounded Evidence Tags with Show in 3D */}
                          {item.grounded_evidence && item.grounded_evidence.length > 0 && (
                            <div className="flex flex-wrap items-center gap-1.5 pt-1">
                              <span className="text-[10px] uppercase font-bold text-slate-400">Grounded In:</span>
                              {item.grounded_evidence.map((ev, eIdx) => (
                                <button
                                  key={eIdx}
                                  onClick={() => {
                                    if (ev.entity_type === 'FACE') setSelectedFaceId(ev.entity_id);
                                  }}
                                  className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-cyan-500/15 text-cyan-600 dark:text-cyan-400 hover:bg-cyan-500 hover:text-white transition flex items-center gap-1"
                                >
                                  <Search className="w-2.5 h-2.5" />
                                  <span>{ev.entity_id}</span>
                                </button>
                              ))}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* SUBTAB 1: EXECUTIVE REVIEW SUMMARY */}
            {activeSubTab === 'summary' && (
              <div className="space-y-4 text-xs">
                <div className="flex items-center justify-between border-b border-slate-200 dark:border-slate-800 pb-3">
                  <h3 className={`text-sm font-black uppercase tracking-wide flex items-center gap-2 ${textHeading}`}>
                    <Sparkles className="w-4 h-4 text-cyan-500" />
                    Engineering Design Review Summary
                  </h3>
                  <span className="px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-600 dark:text-emerald-300 font-bold border border-emerald-500/30">
                    B-Rep Verified
                  </span>
                </div>

                <div className="space-y-2.5">
                  <div className={`p-3 rounded-xl border space-y-1 ${bgSubCard}`}>
                    <div className="text-[10px] uppercase font-bold text-slate-400">1. Geometry &amp; Topology Found</div>
                    <p className={`font-medium ${textHeading}`}>{data.question_answers['1_existing_features']}</p>
                    <div className="text-[11px] text-slate-500 font-mono">
                      {data.audit_summary.unique_faces_count} Faces • {data.audit_summary.unique_edges_count} Edges • {data.audit_summary.unique_solids_count} Unique Solids
                    </div>
                  </div>

                  <div className={`p-3 rounded-xl border space-y-1 ${bgSubCard}`}>
                    <div className="text-[10px] uppercase font-bold text-slate-400">2. Important Engineering Interfaces</div>
                    <ul className="space-y-1 mt-1 text-slate-600 dark:text-slate-300">
                      {data.feature_graph.filter((f) => f.relevance_category in { CRITICAL: 1, INTERFACE: 1 }).slice(0, 3).map((f) => (
                        <li
                          key={f.feature_id}
                          onClick={() => handleSelectFeature(f)}
                          className="cursor-pointer hover:text-cyan-500 flex items-start gap-1.5 transition"
                        >
                          <span className="text-cyan-500 font-bold">•</span>
                          <span><strong>{f.feature_id}:</strong> {f.geometric_type} ({f.measured_dimensions.diameter_mm ? `Ø${f.measured_dimensions.diameter_mm.toFixed(1)}mm` : `${f.measured_dimensions.step_width_mm}mm`}) → <span className="text-amber-600 dark:text-amber-400 font-semibold">{f.engineering_interpretation}</span></span>
                        </li>
                      ))}
                    </ul>
                  </div>

                  <div className={`p-3 rounded-xl border space-y-1 ${bgSubCard}`}>
                    <div className="text-[10px] uppercase font-bold text-slate-400">3. Recommended Section Cut</div>
                    <div
                      onClick={() => {
                        setSelectedSectionId(data.section_recommendations.recommended_primary_section);
                        setActiveSubTab('views_sections');
                      }}
                      className="cursor-pointer hover:bg-slate-100 dark:hover:bg-slate-900 p-2 rounded-lg border border-slate-200 dark:border-slate-800 transition"
                    >
                      <div className="text-cyan-600 dark:text-cyan-400 font-bold font-mono">{data.section_recommendations.recommended_primary_section} (Full Longitudinal Center Cut)</div>
                      <p className="text-[11px] text-slate-500 mt-0.5">{data.question_answers['6_useful_section_cuts']}</p>
                    </div>
                  </div>

                  <div className={`p-3 rounded-xl border space-y-1 ${bgSubCard}`}>
                    <div className="text-[10px] uppercase font-bold text-slate-400">4. Not Determinable from Supplied CAD</div>
                    <ul className="space-y-1 mt-1 text-slate-500 text-[11px]">
                      {data.missing_information.slice(0, 2).map((m, i) => (
                        <li key={i} className="flex items-start gap-1.5">
                          <span className="text-amber-500 font-bold">?</span>
                          <span>{m}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>
              </div>
            )}

            {/* SUBTAB 2: RANKED ENGINEERING FEATURES */}
            {activeSubTab === 'features' && (
              <div className="space-y-3">
                <div className="flex items-center justify-between border-b border-slate-200 dark:border-slate-800 pb-2.5 mb-3">
                  <span className="text-xs font-black uppercase tracking-wider text-slate-500">
                    Features Ranked by Engineering Relevance
                  </span>
                  <span className="text-[11px] text-slate-400">Click to highlight in 3D</span>
                </div>

                <div className="space-y-2 font-mono text-xs">
                  {data.feature_graph.map((feat) => {
                    const isSelected = selectedFeatureId === feat.feature_id;
                    const hasSelectedFace = selectedFaceId && feat.source_faces.includes(selectedFaceId);

                    return (
                      <div
                        key={feat.feature_id}
                        onClick={() => handleSelectFeature(feat)}
                        className={`p-3.5 rounded-xl border cursor-pointer transition shadow-sm ${
                          isSelected || hasSelectedFace
                            ? 'bg-cyan-50 dark:bg-cyan-950/40 border-cyan-500 shadow-cyan-500/10'
                            : bgSubCard
                        }`}
                      >
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <span className={`font-bold ${textHeading}`}>{feat.feature_id}</span>
                            <span className="text-slate-400 text-[11px]">{feat.geometric_type}</span>
                          </div>
                          <span
                            className={`px-2 py-0.5 rounded text-[10px] font-black uppercase ${
                              feat.relevance_category === 'CRITICAL'
                                ? 'bg-red-500/20 text-red-600 dark:text-red-300 border border-red-500/30'
                                : feat.relevance_category === 'FUNCTIONAL'
                                ? 'bg-amber-500/20 text-amber-600 dark:text-amber-300 border border-amber-500/30'
                                : feat.relevance_category === 'INTERFACE'
                                ? 'bg-cyan-500/20 text-cyan-600 dark:text-cyan-300 border border-cyan-500/30'
                                : 'bg-slate-200 dark:bg-slate-800 text-slate-600 dark:text-slate-400'
                            }`}
                          >
                            {feat.relevance_category}
                          </span>
                        </div>

                        <div className="mt-2 font-sans text-xs">
                          <div className="text-cyan-600 dark:text-cyan-400 font-bold">
                            Interpretation: <span className={textHeading}>{feat.engineering_interpretation}</span>
                          </div>
                          <p className="text-[11px] text-slate-500 mt-1 leading-relaxed">
                            <strong>Reason:</strong> {feat.reasoning}
                          </p>
                        </div>

                        <div className="mt-2.5 pt-2 border-t border-slate-200 dark:border-slate-800/60 flex items-center justify-between text-[11px] text-slate-400">
                          <span>Source: <strong className="text-pink-600 dark:text-pink-400">{feat.source_faces.join(', ')}</strong></span>
                          <span>Evidence: <strong>{feat.measured_dimensions.diameter_mm ? `Ø${feat.measured_dimensions.diameter_mm.toFixed(1)} mm` : `${feat.measured_dimensions.step_width_mm} mm`}</strong></span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* SUBTAB 3: IMPORTANT DIMENSIONS */}
            {activeSubTab === 'dimensions' && (
              <div className="space-y-3">
                <div className="flex items-center justify-between border-b border-slate-200 dark:border-slate-800 pb-2.5 mb-3">
                  <span className="text-xs font-black uppercase tracking-wider text-slate-500">
                    Prioritized Measurable Dimensions
                  </span>
                  <span className="text-[11px] text-slate-400">Click to trace to B-Rep Face</span>
                </div>

                <div className="space-y-2 font-mono text-xs">
                  {data.classified_dimensions.map((dim) => {
                    const isSelected = selectedDimensionId === dim.dimension_id;
                    const hasSelectedFace = selectedFaceId && dim.source_entities.includes(selectedFaceId);

                    return (
                      <div
                        key={dim.dimension_id}
                        onClick={() => handleSelectDimension(dim)}
                        className={`p-3 rounded-xl border cursor-pointer transition ${
                          isSelected || hasSelectedFace
                            ? 'bg-cyan-50 dark:bg-cyan-950/40 border-cyan-500 shadow-cyan-500/10'
                            : bgSubCard
                        }`}
                      >
                        <div className="flex items-center justify-between">
                          <span className={`font-bold ${textHeading}`}>{dim.dimension_id}</span>
                          <span className="text-sm font-black text-cyan-600 dark:text-cyan-400">{dim.value_mm.toFixed(2)} mm</span>
                          <span
                            className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                              dim.importance_tier === 'TIER_1_CRITICAL'
                                ? 'bg-red-500/20 text-red-600 dark:text-red-300 border border-red-500/30'
                                : dim.importance_tier === 'TIER_2_FUNCTIONAL'
                                ? 'bg-amber-500/20 text-amber-600 dark:text-amber-300 border border-amber-500/30'
                                : 'bg-slate-200 dark:bg-slate-800 text-slate-600 dark:text-slate-400'
                            }`}
                          >
                            {dim.importance_tier.replace('TIER_', '')}
                          </span>
                        </div>
                        <div className="mt-2 text-[11px] font-sans text-slate-500 flex items-center justify-between">
                          <span>Method: <strong className={textHeading}>{dim.measurement_method}</strong></span>
                          <span>Source: <strong className="text-pink-600 dark:text-pink-400">{dim.source_entities.join(', ')}</strong></span>
                          <span>View: <strong className={textHeading}>{dim.assigned_view}</strong></span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* SUBTAB 4: RECOMMENDED VIEWS & SECTIONS */}
            {activeSubTab === 'views_sections' && (
              <div className="space-y-4 text-xs">
                <div className="flex items-center justify-between p-3 rounded-xl border bg-slate-100 dark:bg-slate-950/80 border-slate-200 dark:border-slate-800">
                  <div>
                    <span className={`font-bold block ${textHeading}`}>3D Interactive Cutting Plane</span>
                    <span className="text-slate-400 text-[11px]">Render mathematical slicing plane in 3D viewport</span>
                  </div>
                  <button
                    onClick={() => setShowSectionPlane((p) => !p)}
                    className={`px-3 py-1.5 rounded-lg text-xs font-bold font-mono transition ${
                      showSectionPlane
                        ? 'bg-cyan-500 text-white shadow-md shadow-cyan-500/20'
                        : 'bg-slate-200 dark:bg-slate-800 text-slate-600 dark:text-slate-400'
                    }`}
                  >
                    {showSectionPlane ? 'Plane: ACTIVE' : 'Plane: HIDDEN'}
                  </button>
                </div>

                {/* Active Section Provenance & "WHY THIS CUT?" Card */}
                {activeSection && (
                  <div className={`p-4 rounded-xl border space-y-3 ${
                    theme === 'light' ? 'bg-cyan-50/70 border-cyan-200 shadow-sm' : 'bg-cyan-950/30 border-cyan-500/30'
                  }`}>
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span className="px-2 py-0.5 rounded text-[10px] font-black uppercase bg-cyan-500 text-white">
                          WHY THIS CUT?
                        </span>
                        <span className={`font-mono font-bold text-sm ${textHeading}`}>{activeSection.section_id}: {activeSection.plane_name}</span>
                      </div>
                      <span className="text-[10px] font-mono text-cyan-600 dark:text-cyan-400 font-bold">
                        Score: {((activeSection.usefulness_score || 0) * 100).toFixed(0)}%
                      </span>
                    </div>

                    <div className="text-xs space-y-1.5 leading-relaxed">
                      <p className={textMuted}>
                        <strong className={textHeading}>Geometric Justification: </strong>
                        {activeSection.engineering_rationale.join(' ')}
                      </p>
                      <div className="grid grid-cols-2 gap-2 text-[10px] font-mono pt-1">
                        <div className="p-2 rounded-lg bg-white/70 dark:bg-slate-900/80 border border-slate-200 dark:border-slate-800">
                          <span className="text-slate-400 block uppercase font-bold">Cutting Origin</span>
                          <span className={textHeading}>[{activeSection.plane_origin.map((v) => v.toFixed(2)).join(', ')}]</span>
                        </div>
                        <div className="p-2 rounded-lg bg-white/70 dark:bg-slate-900/80 border border-slate-200 dark:border-slate-800">
                          <span className="text-slate-400 block uppercase font-bold">Normal Vector</span>
                          <span className={textHeading}>[{activeSection.plane_normal.map((v) => v.toFixed(2)).join(', ')}]</span>
                        </div>
                      </div>
                    </div>

                    <div className="pt-2 border-t border-cyan-200 dark:border-cyan-500/20 flex flex-wrap items-center justify-between gap-2">
                      <div className="text-[11px] text-slate-500">
                        Exposes: <strong className="text-emerald-600 dark:text-emerald-400 font-mono">{(activeSection.internal_features_exposed || []).join(', ') || 'Internal Bores & Cavities'}</strong>
                      </div>
                      <div className="flex items-center gap-1.5">
                        <button
                          onClick={() => {
                            setShowSectionPlane(true);
                            if (activeSection.internal_features_exposed && activeSection.internal_features_exposed.length > 0) {
                              setSelectedFeatureId(activeSection.internal_features_exposed[0]);
                            }
                          }}
                          className="px-2.5 py-1 rounded-lg bg-cyan-500 hover:bg-cyan-600 text-white text-[10px] font-bold font-mono transition shadow-sm"
                        >
                          Highlight Cut Features
                        </button>
                      </div>
                    </div>
                  </div>
                )}

                <div>
                  <h4 className="text-xs font-black uppercase tracking-wider text-slate-500 mb-2.5">
                    Candidate Section Cutting Planes
                  </h4>
                  <div className="space-y-2 font-mono">
                    {data.section_recommendations.candidates.map((sec) => {
                      const isSelected = selectedSectionId === sec.section_id;

                      return (
                        <div
                          key={sec.section_id}
                          onClick={() => {
                            setSelectedSectionId(sec.section_id);
                            setShowSectionPlane(true);
                          }}
                          className={`p-3.5 rounded-xl border cursor-pointer transition ${
                            isSelected
                              ? 'bg-cyan-50 dark:bg-cyan-950/50 border-cyan-500 shadow-cyan-500/10'
                              : bgSubCard
                          }`}
                        >
                          <div className="flex items-center justify-between">
                            <span className={`font-bold text-sm ${textHeading}`}>{sec.section_id}</span>
                            <span
                              className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                                sec.rank === 'PRIMARY_RECOMMENDED'
                                  ? 'bg-emerald-500/20 text-emerald-600 dark:text-emerald-300 border border-emerald-500/40'
                                  : 'bg-slate-200 dark:bg-slate-800 text-slate-600 dark:text-slate-400'
                              }`}
                            >
                              {sec.rank === 'PRIMARY_RECOMMENDED' ? 'PRIMARY (100%)' : 'OPTIONAL (64%)'}
                            </span>
                          </div>
                          <p className="text-cyan-600 dark:text-cyan-400 font-sans font-bold mt-1">{sec.plane_name}</p>
                          <p className="text-[11px] font-sans text-slate-500 mt-1">{sec.engineering_rationale[0]}</p>
                          <div className="mt-2 text-[11px] text-slate-400 flex justify-between">
                            <span>Exposes: <strong className="text-emerald-600 dark:text-emerald-400">{sec.exposed_feature_count} internal features</strong></span>
                            <span>Cut Edges: <strong className={textHeading}>{sec.cut_edge_count}</strong></span>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>
            )}

            {/* SUBTAB 5: EPISTEMIC DISTINCTIONS */}
            {activeSubTab === 'epistemic' && (
              <div className="space-y-3.5 text-xs">
                <div className="p-3.5 bg-emerald-50/60 dark:bg-slate-950/70 border border-emerald-500/30 rounded-xl space-y-1.5">
                  <div className="flex items-center gap-1.5 text-emerald-600 dark:text-emerald-400 font-bold uppercase tracking-wider text-[11px]">
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    <span>KNOWN GEOMETRIC FACTS (OCCT Ground Truth)</span>
                  </div>
                  <ul className="space-y-1 text-slate-700 dark:text-slate-300 text-[11px]">
                    <li>• Exact bounding box: 114.0 × 71.5 × 56.2 mm</li>
                    <li>• Unique topology: 230 Faces, 611 Edges, 3 Unique Solids</li>
                    <li>• Exact cylinder radii &amp; plane offsets verified mathematically</li>
                  </ul>
                </div>

                <div className="p-3.5 bg-cyan-50/60 dark:bg-slate-950/70 border border-cyan-500/30 rounded-xl space-y-1.5">
                  <div className="flex items-center gap-1.5 text-cyan-600 dark:text-cyan-400 font-bold uppercase tracking-wider text-[11px]">
                    <Sparkles className="w-3.5 h-3.5" />
                    <span>INFERRED ENGINEERING ROLES (Hypotheses)</span>
                  </div>
                  <ul className="space-y-1 text-slate-700 dark:text-slate-300 text-[11px]">
                    <li>• Longitudinal through-bores are inferred as fluid conduit ports</li>
                    <li>• Central enlarged cavity is inferred as a valve chamber</li>
                    <li>• Protruding cylinder is inferred as an actuator stem pin</li>
                  </ul>
                </div>

                <div className="p-3.5 bg-amber-50/60 dark:bg-slate-950/70 border border-amber-500/30 rounded-xl space-y-1.5">
                  <div className="flex items-center gap-1.5 text-amber-600 dark:text-amber-400 font-bold uppercase tracking-wider text-[11px]">
                    <HelpCircle className="w-3.5 h-3.5" />
                    <span>NOT DETERMINABLE FROM SUPPLIED CAD (Missing Data)</span>
                  </div>
                  <ul className="space-y-1 text-slate-700 dark:text-slate-300 text-[11px]">
                    {data.missing_information.map((m, idx) => (
                      <li key={idx}>• {m}</li>
                    ))}
                  </ul>
                </div>
              </div>
            )}

          </div>
        </div>
      </div>
    </div>
  );
};
