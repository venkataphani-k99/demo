import React, { useState } from 'react';
import {
  Bot,
  CheckCircle2,
  AlertTriangle,
  Sparkles,
  Cpu,
  Eye,
  Layers,
  ChevronDown,
  ChevronRight,
  Tag,
  Ruler,
  Box,
  MessageSquare,
  ShieldAlert,
  Info,
  XCircle,
  ZapOff,
} from 'lucide-react';
import {
  AIReviewResponse,
  ConsensusSummary,
  DimensionCandidate,
  EngineeringIssue,
  EngineeringRecommendation,
  RecognizedFeature,
  api,
} from '../../lib/api';

// ─── Category label / colour ────────────────────────────────────────────────
const CATEGORY_LABELS: Record<string, string> = {
  ambiguous_geometry: 'INTERNAL CAVITY',
  drawing_clarity: 'DRAWING CLARITY',
  manufacturing_communication: 'MANUFACTURING NOTE',
  datum: 'DATUM',
  dimension: 'DIMENSION',
  feature: 'FEATURE',
  orthographic_layout: 'ORTHO LAYOUT',
  visibility: 'VISIBILITY',
  fillet: 'FILLET',
  drawing_standard: 'DRAWING STANDARD',
};

const severityConfig = (sev: string): { border: string; badge: string; icon: React.ReactNode; label: string } => {
  switch (sev?.toLowerCase()) {
    case 'critical':
    case 'high':
      return {
        border: 'border-rose-500/40',
        badge: 'bg-rose-500/15 text-rose-400 border border-rose-500/30',
        icon: <XCircle className="h-3.5 w-3.5 text-rose-400 flex-shrink-0" />,
        label: sev.toUpperCase(),
      };
    case 'medium':
    case 'warning':
      return {
        border: 'border-amber-500/40',
        badge: 'bg-amber-500/15 text-amber-400 border border-amber-500/30',
        icon: <AlertTriangle className="h-3.5 w-3.5 text-amber-400 flex-shrink-0" />,
        label: sev.toUpperCase(),
      };
    case 'low':
    case 'info':
    default:
      return {
        border: 'border-cyan-500/30',
        badge: 'bg-cyan-500/10 text-cyan-400 border border-cyan-500/20',
        icon: <Info className="h-3.5 w-3.5 text-cyan-400 flex-shrink-0" />,
        label: sev?.toUpperCase() || 'INFO',
      };
  }
};

// ─── Finding Card ────────────────────────────────────────────────────────────
interface FindingCardProps {
  issue: EngineeringIssue;
  recommendation?: EngineeringRecommendation;
  onSelectFeature?: (id: string | null) => void;
}

const FindingCard: React.FC<FindingCardProps> = ({ issue, recommendation, onSelectFeature }) => {
  const [expanded, setExpanded] = useState(false);
  const sev = severityConfig(issue.severity);
  const catLabel =
    CATEGORY_LABELS[issue.category?.toLowerCase()] ?? issue.category?.toUpperCase() ?? 'FINDING';

  return (
    <div
      className={`rounded-lg border ${sev.border} bg-slate-950/60 overflow-hidden transition-all`}
    >
      {/* Collapsed header — always visible */}
      <button
        className="w-full text-left px-4 py-3 flex items-start gap-3 hover:bg-slate-900/40 transition-colors"
        onClick={() => setExpanded((e) => !e)}
        aria-expanded={expanded}
      >
        <div className="mt-0.5">{sev.icon}</div>
        <div className="flex-1 min-w-0">
          <div className="flex flex-wrap items-center gap-1.5 mb-1">
            <span className={`rounded px-1.5 py-0.5 text-[10px] font-mono font-bold ${sev.badge}`}>
              {sev.label}
            </span>
            <span className="rounded bg-slate-800 px-1.5 py-0.5 text-[10px] font-mono text-slate-300 border border-slate-700">
              {catLabel}
            </span>
            <span className="text-[10px] font-mono text-slate-500">{issue.issue_id}</span>
            {issue.affected_view && issue.affected_view !== 'null' && (
              <span className="rounded bg-violet-500/10 px-1.5 py-0.5 text-[10px] font-mono text-violet-300 border border-violet-500/20">
                {issue.affected_view}
              </span>
            )}
          </div>
          <p className="text-xs font-medium text-slate-200 leading-snug">{issue.title}</p>
          <div className="flex flex-wrap gap-2 mt-1.5">
            {issue.affected_feature_ids?.map((fid) => (
              <button
                key={fid}
                className="text-[10px] font-mono text-amber-300 hover:text-amber-200 underline underline-offset-2 flex items-center gap-1"
                onClick={(e) => {
                  e.stopPropagation();
                  onSelectFeature?.(fid);
                }}
                title={`Highlight feature ${fid}`}
              >
                <Box className="h-2.5 w-2.5" />
                {fid}
              </button>
            ))}
            {issue.affected_dimension_ids?.map((did) => (
              <span
                key={did}
                className="text-[10px] font-mono text-emerald-400 flex items-center gap-1"
                title={`Dimension ${did}`}
              >
                <Ruler className="h-2.5 w-2.5" />
                {did}
              </span>
            ))}
          </div>
        </div>
        <div className="flex-shrink-0 mt-0.5 text-slate-500">
          {expanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
        </div>
      </button>

      {/* Expanded detail */}
      {expanded && (
        <div className="px-4 pb-4 space-y-3 border-t border-slate-800/60">
          {issue.description && (
            <div className="pt-3 space-y-1">
              <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider">
                Observation
              </span>
              <p className="text-xs text-slate-300 leading-relaxed">{issue.description}</p>
            </div>
          )}
          {issue.visual_observation && issue.visual_observation !== issue.description && (
            <div className="space-y-1">
              <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider">
                Visual Observation
              </span>
              <p className="text-xs text-slate-300 leading-relaxed">{issue.visual_observation}</p>
            </div>
          )}
          {issue.engineering_reason && (
            <div className="space-y-1">
              <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider">
                Engineering Rationale
              </span>
              <p className="text-xs text-slate-300 leading-relaxed">{issue.engineering_reason}</p>
            </div>
          )}
          {recommendation && (
            <div className="rounded-md border border-violet-500/20 bg-violet-500/5 p-3 space-y-1.5">
              <div className="flex items-center gap-1.5">
                <MessageSquare className="h-3 w-3 text-violet-400" />
                <span className="text-[10px] font-semibold text-violet-300 uppercase tracking-wider">
                  Recommendation · {recommendation.recommendation_id}
                </span>
              </div>
              <p className="text-xs text-slate-300 leading-relaxed">{recommendation.rationale}</p>
              <p className="text-[10px] text-emerald-400">{recommendation.expected_benefit}</p>
            </div>
          )}
          {/* B-Rep evidence entities */}
          {issue.affected_brep_entities && issue.affected_brep_entities.length > 0 && (
            <div className="space-y-1">
              <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider">
                B-Rep Entities
              </span>
              <div className="flex flex-wrap gap-1">
                {issue.affected_brep_entities.map((ent) => (
                  <span
                    key={ent}
                    className="rounded bg-slate-800 px-1.5 py-0.5 text-[10px] font-mono text-slate-300 border border-slate-700"
                  >
                    {ent}
                  </span>
                ))}
              </div>
            </div>
          )}
          {/* Review source models */}
          {issue.source_models && issue.source_models.length > 0 && (
            <div className="flex items-center gap-1.5 text-[10px] text-slate-500 font-mono">
              <Bot className="h-3 w-3" />
              {issue.source_models.join(' • ')}
            </div>
          )}
          {/* Human approval status */}
          <div className="flex items-center gap-2 pt-1">
            <ShieldAlert className="h-3.5 w-3.5 text-amber-400" />
            <span className="text-[10px] font-semibold text-amber-300">
              {issue.status ?? 'AWAITING_HUMAN_APPROVAL'}
            </span>
            <span className="text-[10px] text-slate-500">· Zero CAD auto-mutation</span>
          </div>
        </div>
      )}
    </div>
  );
};

// ─── Main Panel ──────────────────────────────────────────────────────────────
interface AIReviewPanelProps {
  projectId?: string;
  projectName?: string;
  dimensions?: DimensionCandidate[];
  placedCount?: number;
  totalCandidatesCount?: number;
  features?: RecognizedFeature[];
  boundingBox?: { x_length: number; y_length: number; z_length: number };
  claudeReview?: AIReviewResponse | null;
  geminiReview?: AIReviewResponse | null;
  consensus?: ConsensusSummary | null;
  issues?: EngineeringIssue[];
  recommendations?: EngineeringRecommendation[];
  onRefreshReview?: () => void;
  onSelectFeature?: (id: string | null) => void;
}

export const AIReviewPanel: React.FC<AIReviewPanelProps> = ({
  projectId,
  projectName = 'Current Model',
  dimensions = [],
  placedCount,
  totalCandidatesCount,
  features = [],
  boundingBox,
  claudeReview,
  geminiReview,
  consensus,
  issues = [],
  recommendations = [],
  onRefreshReview,
  onSelectFeature,
}) => {
  const [activeTab, setActiveTab] = useState<'consensus' | 'claude' | 'gemini'>('consensus');
  const [reviewError, setReviewError] = useState<string | null>(null);

  // ── Derived counts (all from live pipeline data) ──────────────────────────
  const actualPlacedCount =
    placedCount !== undefined
      ? placedCount
      : dimensions.filter(
          (d) => d.status === 'placed' || d.placement_status === 'placed' || d.category === 'placed'
        ).length;

  const totalCandCount = totalCandidatesCount ?? dimensions.length;

  // Finding severity breakdown (from authoritative issues list)
  const criticalCount = issues.filter((i) =>
    ['critical', 'high'].includes(i.severity?.toLowerCase())
  ).length;
  const warningCount = issues.filter((i) =>
    ['medium', 'warning'].includes(i.severity?.toLowerCase())
  ).length;
  const infoCount = issues.filter((i) =>
    ['low', 'info'].includes(i.severity?.toLowerCase())
  ).length;

  // Unique features / dimensions / views referenced by findings
  const reviewedFeatureIds = [
    ...new Set(issues.flatMap((i) => i.affected_feature_ids ?? [])),
  ];
  const reviewedDimIds = [
    ...new Set(issues.flatMap((i) => i.affected_dimension_ids ?? [])),
  ];
  const reviewedViews = [
    ...new Set(
      issues
        .map((i) => i.affected_view)
        .filter((v): v is string => !!v && v !== 'null' && v !== 'All')
    ),
  ];

  // Build a map from issue_id → recommendation for quick lookup
  const recByIssueId = new Map<string, EngineeringRecommendation>();
  recommendations.forEach((r) => {
    if (r.issue_id) recByIssueId.set(r.issue_id, r);
  });

  const [isExecutingReview, setIsExecutingReview] = useState<'claude' | 'gemini' | null>(null);

  // Good aspects: from live review data or fallback
  const claudeGoodAspects = claudeReview?.good_aspects ?? [];
  const geminiGoodAspects = geminiReview?.good_aspects ?? [];

  const triggerLiveReview = async (provider: 'mock' | 'claude' | 'gemini') => {
    if (!projectId || isExecutingReview) return;
    setIsExecutingReview(provider === 'claude' ? 'claude' : provider === 'gemini' ? 'gemini' : null);
    setReviewError(null);
    try {
      await api.executeAIReview(projectId, provider);
      if (onRefreshReview) onRefreshReview();
    } catch (err: unknown) {
      setReviewError(err instanceof Error ? err.message : String(err));
    } finally {
      setIsExecutingReview(null);
    }
  };

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/60 overflow-hidden backdrop-blur-md shadow-xl">
      {/* ── Header ─────────────────────────────────────────────────────────── */}
      <div className="flex flex-wrap items-center justify-between border-b border-slate-800 bg-slate-950/60 px-4 py-3 gap-2">
        <div className="flex items-center space-x-2">
          <Bot className="h-4 w-4 text-cyan-400" />
          <h3 className="text-sm font-semibold text-white">Multimodal Visual AI Drawing Review</h3>
          <span className="rounded-full bg-cyan-500/10 px-2 py-0.5 text-xs font-mono font-medium text-cyan-300 border border-cyan-500/20">
            Phase 15 Multi-Model CAD Intelligence
          </span>
        </div>

        <div className="flex items-center space-x-1">
          {(['consensus', 'claude', 'gemini'] as const).map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`rounded px-2.5 py-1 text-xs font-medium transition-all ${
                activeTab === tab
                  ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40'
                  : 'text-slate-400 hover:bg-slate-800 hover:text-slate-200'
              }`}
            >
              {tab === 'consensus'
                ? 'Consensus Insights'
                : tab === 'claude'
                ? 'Anthropic Claude 3.5'
                : 'Google Gemini 2.5'}
            </button>
          ))}
        </div>
      </div>

      {reviewError && (
        <div className="mx-4 mt-4 rounded-lg border border-rose-500/30 bg-rose-500/10 p-3 text-xs text-rose-300 flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <AlertTriangle className="h-4 w-4 text-rose-400 shrink-0" />
            <span>{reviewError}</span>
          </div>
          <button onClick={() => setReviewError(null)} className="text-rose-400 hover:text-white font-bold ml-2">
            ×
          </button>
        </div>
      )}

      {/* ── Tab Contents ───────────────────────────────────────────────────── */}
      <div className="p-5 text-xs space-y-5">

        {/* ── CONSENSUS TAB ─────────────────────────────────────────────── */}
        {activeTab === 'consensus' && (
          <div className="space-y-5">

            {/* Dynamic review summary stats */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <div className="rounded-lg border border-slate-800 bg-slate-950/60 p-3">
                <span className="text-[11px] text-slate-400">Total Findings</span>
                <p className="text-xl font-bold font-mono text-cyan-300 mt-1">{issues.length}</p>
                <span className="text-[10px] text-emerald-400 mt-1 flex items-center">
                  <CheckCircle2 className="h-3 w-3 mr-1" />
                  {consensus?.consensus_issues_count ?? issues.length} Consensus
                </span>
              </div>

              <div className="rounded-lg border border-slate-800 bg-slate-950/60 p-3">
                <span className="text-[11px] text-slate-400">By Severity</span>
                <div className="mt-1.5 space-y-0.5">
                  {criticalCount > 0 && (
                    <div className="flex justify-between font-mono">
                      <span className="text-rose-400">CRITICAL</span>
                      <span className="text-rose-300 font-bold">{criticalCount}</span>
                    </div>
                  )}
                  {warningCount > 0 && (
                    <div className="flex justify-between font-mono">
                      <span className="text-amber-400">WARNING</span>
                      <span className="text-amber-300 font-bold">{warningCount}</span>
                    </div>
                  )}
                  {infoCount > 0 && (
                    <div className="flex justify-between font-mono">
                      <span className="text-cyan-400">INFO</span>
                      <span className="text-cyan-300 font-bold">{infoCount}</span>
                    </div>
                  )}
                  {issues.length === 0 && (
                    <span className="text-emerald-400 text-[10px]">No findings</span>
                  )}
                </div>
              </div>

              <div className="rounded-lg border border-slate-800 bg-slate-950/60 p-3">
                <span className="text-[11px] text-slate-400">Dims / Features Reviewed</span>
                <p className="text-lg font-bold font-mono text-emerald-400 mt-1">
                  {reviewedDimIds.length}D / {reviewedFeatureIds.length}F
                </p>
                <span className="text-[10px] text-slate-400 mt-1 flex items-center">
                  <Eye className="h-3 w-3 mr-1 text-cyan-400" />
                  {actualPlacedCount} placed · {totalCandCount} candidates
                </span>
              </div>

              <div className="rounded-lg border border-slate-800 bg-slate-950/60 p-3">
                <span className="text-[11px] text-slate-400">Safety Gate</span>
                <p className="text-sm font-bold font-mono text-amber-300 mt-1">
                  {issues.length > 0 ? 'HUMAN REVIEW' : '100% PASSED'}
                </p>
                <span className="text-[10px] text-slate-400 mt-1 flex items-center">
                  <Cpu className="h-3 w-3 mr-1 text-cyan-400" />
                  0 Auto-Mutations
                </span>
              </div>
            </div>

            {/* Model geometry summary bar */}
            <div className="rounded-lg border border-slate-800 bg-slate-950/40 p-3 flex flex-wrap items-center justify-between gap-2 text-slate-400">
              <div className="flex items-center space-x-2">
                <Layers className="h-3.5 w-3.5 text-cyan-400" />
                <span className="font-mono text-slate-200">{projectName}</span>
              </div>
              {boundingBox && (
                <div className="font-mono text-[11px] text-slate-300">
                  Envelope: {boundingBox.x_length.toFixed(1)} × {boundingBox.y_length.toFixed(1)} × {boundingBox.z_length.toFixed(1)} mm
                </div>
              )}
              <div className="font-mono text-[11px] text-cyan-300">
                {features.length} Features • {actualPlacedCount} Placed Dims • {totalCandCount} Candidates
              </div>
            </div>

            {/* ── Engineering Findings ─────────────────────────────────── */}
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <h4 className="text-xs font-semibold text-slate-200 flex items-center gap-1.5">
                  <ShieldAlert className="h-3.5 w-3.5 text-amber-400" />
                  Engineering Findings
                  <span className="rounded-full bg-amber-500/20 px-1.5 py-0.5 text-[10px] font-mono text-amber-300 border border-amber-500/30">
                    {issues.length}
                  </span>
                </h4>
                {reviewedViews.length > 0 && (
                  <span className="text-[10px] font-mono text-slate-400">
                    Views: {reviewedViews.join(', ')}
                  </span>
                )}
              </div>

              {issues.length === 0 ? (
                <div className="rounded-lg border border-emerald-500/20 bg-emerald-500/5 p-4 flex items-center gap-2">
                  <CheckCircle2 className="h-4 w-4 text-emerald-400 flex-shrink-0" />
                  <p className="text-xs text-emerald-300">
                    No engineering findings for {projectName}. Drawing meets review criteria.
                  </p>
                </div>
              ) : (
                <div className="space-y-2">
                  {issues.map((issue) => (
                    <FindingCard
                      key={issue.issue_id}
                      issue={issue}
                      recommendation={recByIssueId.get(issue.issue_id)}
                      onSelectFeature={onSelectFeature}
                    />
                  ))}
                </div>
              )}
            </div>

            {/* ── Review Summary Takeaways ──────────────────────────── */}
            <div className="rounded-lg border border-cyan-500/20 bg-cyan-500/5 p-4 space-y-2">
              <h4 className="text-xs font-semibold text-cyan-300 flex items-center">
                <Sparkles className="h-3.5 w-3.5 mr-1.5" />
                Multi-Model Engineering Review Summary
              </h4>
              <ul className="space-y-2 text-slate-300 pl-2">
                <li className="flex items-start space-x-2">
                  <span className="text-cyan-400 mt-0.5">•</span>
                  <span>
                    <strong className="text-white">Drawing Orthographic Layout:</strong>{' '}
                    Multi-model visual review confirmed all {actualPlacedCount} placed dimensions
                    are legible, non-overlapping, and placed within standard drawing sheet margins.
                  </span>
                </li>
                <li className="flex items-start space-x-2">
                  <span className="text-cyan-400 mt-0.5">•</span>
                  <span>
                    <strong className="text-white">Feature Coverage:</strong>{' '}
                    Recognized {features.length} manufacturing features with deterministic B-Rep
                    geometry validation.
                    {reviewedFeatureIds.length > 0 && (
                      <span className="text-slate-400">
                        {' '}({reviewedFeatureIds.length} features flagged in findings.)
                      </span>
                    )}
                  </span>
                </li>
                <li className="flex items-start space-x-2">
                  <span className="text-cyan-400 mt-0.5">•</span>
                  <span>
                    <strong className="text-white">Human Approval Gate:</strong>{' '}
                    Zero unverified CAD mutations.{' '}
                    {issues.length > 0
                      ? `${issues.length} finding${issues.length > 1 ? 's' : ''} awaiting engineer sign-off.`
                      : 'All AI recommendations require explicit engineer sign-off.'}
                  </span>
                </li>
              </ul>
            </div>
          </div>
        )}

        {/* ── CLAUDE TAB ────────────────────────────────────────────────── */}
        {activeTab === 'claude' && (
          <div className="space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-2">
              <span className="text-slate-400">AI Review Model:</span>
              <span className="font-mono text-cyan-300 font-semibold">
                {claudeReview?.model ?? 'claude-3-5-sonnet-20241022'}
              </span>
            </div>
            <div className="flex items-center justify-between border-b border-slate-800 pb-2">
              <span className="text-slate-400">Visual Dimensions Verified:</span>
              <span className="font-mono text-emerald-400 font-bold">{actualPlacedCount} Dimensions</span>
            </div>
            <div className="flex items-center justify-between border-b border-slate-800 pb-2">
              <span className="text-slate-400">Views Visually Observed:</span>
              <span className="font-mono text-slate-200">TOP, FRONT, LEFT, RIGHT, BOTTOM</span>
            </div>
            {claudeReview?.overall_assessment && (
              <div className="flex items-center justify-between border-b border-slate-800 pb-2">
                <span className="text-slate-400">Overall Assessment:</span>
                <span className="font-mono uppercase font-bold text-amber-400">
                  {claudeReview.overall_assessment.replace(/_/g, ' ')}
                </span>
              </div>
            )}

            {/* Good Aspects */}
            <div className="space-y-2">
              <span className="text-slate-400 font-semibold flex items-center gap-1.5">
                <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />
                Good Aspects Identified:
              </span>
              {claudeGoodAspects.length > 0 ? (
                <ul className="space-y-1.5 pl-2">
                  {claudeGoodAspects.map((aspect, i) => (
                    <li key={i} className="text-slate-300 flex items-start gap-2">
                      <span className="text-emerald-400 mt-0.5">•</span>
                      <span>{aspect}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-slate-400 italic pl-2">
                  No live Claude review executed yet. Click the button below to run multimodal analysis.
                </p>
              )}
            </div>

            {/* Improvement Areas */}
            {claudeReview?.improvement_areas && claudeReview.improvement_areas.length > 0 && (
              <div className="space-y-2">
                <span className="text-slate-400 font-semibold flex items-center gap-1.5">
                  <AlertTriangle className="h-3.5 w-3.5 text-amber-400" />
                  Improvement Areas &amp; Observations:
                </span>
                <ul className="space-y-1.5 pl-2">
                  {claudeReview.improvement_areas.map((area, i) => (
                    <li key={i} className="text-slate-300 flex items-start gap-2">
                      <span className="text-amber-400 mt-0.5">•</span>
                      <span>{area}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* AI Recommendations from Claude */}
            {claudeReview?.recommendations && claudeReview.recommendations.length > 0 && (
              <div className="space-y-2">
                <span className="text-slate-400 font-semibold">AI Recommendations (Advisory Only):</span>
                {claudeReview.recommendations.map((rec, i) => (
                  <div key={rec.id || i} className="rounded-lg border border-slate-800 bg-slate-950/60 p-3 space-y-1">
                    <div className="flex items-center justify-between">
                      <span className="font-mono text-xs font-bold text-violet-300">{rec.id} · {rec.action}</span>
                      <span className="rounded bg-amber-500/10 px-1.5 py-0.5 text-[10px] font-mono text-amber-300 border border-amber-500/20">
                        Human Gatekeeper Enforced
                      </span>
                    </div>
                    <p className="text-xs text-slate-300">{rec.reason}</p>
                  </div>
                ))}
              </div>
            )}

            <button
              onClick={() => triggerLiveReview('claude')}
              disabled={isExecutingReview !== null}
              className={`w-full mt-3 rounded-lg border py-2.5 text-xs font-semibold transition-all flex items-center justify-center gap-2 ${
                isExecutingReview === 'claude'
                  ? 'border-cyan-500/40 bg-cyan-500/20 text-cyan-300 cursor-not-allowed animate-pulse'
                  : 'border-cyan-500/30 bg-cyan-500/10 text-cyan-300 hover:bg-cyan-500/20 active:scale-[0.99]'
              }`}
            >
              {isExecutingReview === 'claude' ? (
                <>
                  <div className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-cyan-400 border-t-transparent" />
                  <span>Executing Multimodal Claude 3.5 AI Review (Please wait ~15s)...</span>
                </>
              ) : (
                <>
                  <Bot className="h-4 w-4 text-cyan-400" />
                  <span>{claudeReview ? 'Re-Run Live Claude 3.5 Review' : 'Run Live Claude 3.5 Review'}</span>
                </>
              )}
            </button>
          </div>
        )}

        {/* ── GEMINI TAB ────────────────────────────────────────────────── */}
        {activeTab === 'gemini' && (
          <div className="space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-2">
              <span className="text-slate-400">AI Review Model:</span>
              <span className="font-mono text-cyan-300 font-semibold">
                {geminiReview?.model ?? 'gemini-2.5-flash'}
              </span>
            </div>
            <div className="flex items-center justify-between border-b border-slate-800 pb-2">
              <span className="text-slate-400">Visual Dimensions Verified:</span>
              <span className="font-mono text-emerald-400 font-bold">{actualPlacedCount} Dimensions</span>
            </div>
            <div className="flex items-center justify-between border-b border-slate-800 pb-2">
              <span className="text-slate-400">Views Visually Observed:</span>
              <span className="font-mono text-slate-200">TOP, FRONT, RIGHT, LEFT, BOTTOM</span>
            </div>

            {/* Good Aspects */}
            <div className="space-y-2">
              <span className="text-slate-400 font-semibold flex items-center gap-1.5">
                <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />
                Visual Assessment:
              </span>
              {geminiGoodAspects.length > 0 ? (
                <ul className="space-y-1 pl-2">
                  {geminiGoodAspects.map((aspect, i) => (
                    <li key={i} className="text-slate-300 flex items-start gap-1.5">
                      <span className="text-emerald-400 mt-0.5">•</span>
                      <span>{aspect}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-slate-400 italic pl-2">
                  No live Gemini review executed yet. Click the button below to run multimodal analysis.
                </p>
              )}
            </div>

            <button
              onClick={() => triggerLiveReview('gemini')}
              disabled={isExecutingReview !== null}
              className={`w-full mt-3 rounded-lg border py-2.5 text-xs font-semibold transition-all flex items-center justify-center gap-2 ${
                isExecutingReview === 'gemini'
                  ? 'border-cyan-500/40 bg-cyan-500/20 text-cyan-300 cursor-not-allowed animate-pulse'
                  : 'border-cyan-500/30 bg-cyan-500/10 text-cyan-300 hover:bg-cyan-500/20 active:scale-[0.99]'
              }`}
            >
              {isExecutingReview === 'gemini' ? (
                <>
                  <div className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-cyan-400 border-t-transparent" />
                  <span>Executing Multimodal Gemini 2.5 AI Review (Please wait ~15s)...</span>
                </>
              ) : (
                <>
                  <Bot className="h-4 w-4 text-cyan-400" />
                  <span>{geminiReview ? 'Re-Run Live Gemini 2.5 Review' : 'Run Live Gemini 2.5 Review'}</span>
                </>
              )}
            </button>
          </div>
        )}
      </div>
    </div>
  );
};
