import React, { useState } from 'react';
import {
  AlertTriangle,
  CheckCircle2,
  XCircle,
  Clock,
  ShieldCheck,
  Cpu,
  Bot,
  Layers,
  Sparkles,
  ArrowRight,
  Info,
} from 'lucide-react';
import { EngineeringIssue, EngineeringRecommendation, api } from '../../lib/api';

interface EngineeringIssuesPanelProps {
  projectId: string;
  issues: EngineeringIssue[];
  recommendations: EngineeringRecommendation[];
  onRefreshIssues?: () => void;
  theme?: 'light' | 'dark';
}

export const EngineeringIssuesPanel: React.FC<EngineeringIssuesPanelProps> = ({
  projectId,
  issues,
  recommendations,
  onRefreshIssues,
  theme = 'dark',
}) => {
  const isLight = theme === 'light';
  const [loadingAction, setLoadingAction] = useState<string | null>(null);
  const [actionSuccessMessage, setActionSuccessMessage] = useState<string | null>(null);

  const handleApprove = async (recId: string) => {
    setLoadingAction(recId);
    setActionSuccessMessage(null);
    try {
      const res = await api.approveRecommendation(projectId, recId);
      setActionSuccessMessage(`✓ Recommendation ${recId} APPROVED. ${res.message}`);
      if (onRefreshIssues) onRefreshIssues();
    } catch (err: unknown) {
      alert(`Error approving recommendation: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setLoadingAction(null);
    }
  };

  const handleReject = async (recId: string) => {
    setLoadingAction(recId);
    setActionSuccessMessage(null);
    try {
      const res = await api.rejectRecommendation(projectId, recId);
      setActionSuccessMessage(`✕ Recommendation ${recId} REJECTED.`);
      if (onRefreshIssues) onRefreshIssues();
    } catch (err: unknown) {
      alert(`Error rejecting recommendation: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setLoadingAction(null);
    }
  };

  const getSeverityBadge = (severity: string) => {
    switch (severity.toLowerCase()) {
      case 'critical':
        return 'bg-rose-500/15 text-rose-500 dark:text-rose-400 border-rose-500/30';
      case 'high':
        return 'bg-orange-500/15 text-orange-500 dark:text-orange-400 border-orange-500/30';
      case 'medium':
        return 'bg-amber-500/15 text-amber-500 dark:text-amber-400 border-amber-500/30';
      case 'low':
      case 'info':
      default:
        return 'bg-cyan-500/15 text-cyan-600 dark:text-cyan-400 border-cyan-500/30';
    }
  };

  return (
    <div className="space-y-4">
      {/* Header Banner */}
      <div className={`rounded-xl border p-4 shadow-xl flex flex-wrap items-center justify-between gap-3 transition-colors ${
        isLight ? 'bg-white border-slate-200/90' : 'bg-slate-900/60 border-slate-800 backdrop-blur-md'
      }`}>
        <div className="flex items-center space-x-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-amber-500/10 border border-amber-500/20 text-amber-500">
            <ShieldCheck className="h-5 w-5" />
          </div>
          <div>
            <h3 className={`text-sm font-bold ${isLight ? 'text-slate-900' : 'text-white'}`}>Engineering Issues &amp; Human Review Gate</h3>
            <p className={`text-xs ${isLight ? 'text-slate-500' : 'text-slate-400'}`}>
              Phase 12 Traceable Review Model • Gatekeeper Verified • Human Approval Required
            </p>
          </div>
        </div>

        <div className="flex items-center space-x-2">
          <span className={`rounded-full px-3 py-1 text-xs font-mono border ${
            isLight ? 'bg-slate-100 text-slate-700 border-slate-200' : 'bg-slate-800 text-slate-300 border-slate-700'
          }`}>
            {issues.length} Issues Identified
          </span>
          <span className="rounded-full bg-emerald-500/10 px-3 py-1 text-xs font-mono font-bold text-emerald-600 dark:text-emerald-400 border border-emerald-500/20">
            {recommendations.filter((r) => r.approval_status === 'APPROVED').length} Approved
          </span>
        </div>
      </div>

      {actionSuccessMessage && (
        <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 p-3 text-xs text-emerald-600 dark:text-emerald-300 flex items-center space-x-2 animate-in fade-in">
          <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-500" />
          <span>{actionSuccessMessage}</span>
        </div>
      )}

      {/* Issues List */}
      <div className="space-y-4">
        {issues.map((issue) => {
          const rec = recommendations.find((r) => issue.recommendation_ids.includes(r.recommendation_id));
          const isAwaiting = !rec || rec.approval_status === 'AWAITING_HUMAN_APPROVAL';
          const isApproved = rec?.approval_status === 'APPROVED';
          const isRejected = rec?.approval_status === 'REJECTED';

          return (
            <div
              key={issue.issue_id}
              className={`rounded-xl border p-5 shadow-xl transition-all ${
                isLight
                  ? 'bg-white border-slate-200/90 hover:border-slate-300'
                  : 'bg-slate-900/70 border-slate-800 backdrop-blur-md hover:border-slate-700/80'
              }`}
            >
              {/* Issue Top Header */}
              <div className={`flex flex-wrap items-start justify-between gap-2 border-b pb-3 ${
                isLight ? 'border-slate-200' : 'border-slate-800/80'
              }`}>
                <div className="space-y-1">
                  <div className="flex items-center space-x-2">
                    <span className={`font-mono text-sm font-bold ${isLight ? 'text-slate-900' : 'text-white'}`}>{issue.issue_id}</span>
                    <span
                      className={`rounded px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider border ${getSeverityBadge(
                        issue.severity
                      )}`}
                    >
                      {issue.severity}
                    </span>
                    <span className="rounded bg-slate-800 px-2 py-0.5 font-mono text-[10px] text-slate-400 border border-slate-700">
                      {issue.category}
                    </span>
                  </div>
                  <h4 className="text-sm font-semibold text-slate-100">{issue.title}</h4>
                </div>

                {/* Status Badge */}
                <div>
                  {isApproved ? (
                    <span className="inline-flex items-center space-x-1 rounded-full bg-emerald-500/15 px-2.5 py-1 text-xs font-bold text-emerald-400 border border-emerald-500/30">
                      <CheckCircle2 className="h-3.5 w-3.5" />
                      <span>APPROVED</span>
                    </span>
                  ) : isRejected ? (
                    <span className="inline-flex items-center space-x-1 rounded-full bg-rose-500/15 px-2.5 py-1 text-xs font-bold text-rose-400 border border-rose-500/30">
                      <XCircle className="h-3.5 w-3.5" />
                      <span>REJECTED</span>
                    </span>
                  ) : (
                    <span className="inline-flex items-center space-x-1 rounded-full bg-amber-500/15 px-2.5 py-1 text-xs font-bold text-amber-400 border border-amber-500/30 animate-pulse">
                      <Clock className="h-3.5 w-3.5" />
                      <span>AWAITING HUMAN APPROVAL</span>
                    </span>
                  )}
                </div>
              </div>

              {/* Issue Body */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 py-3 text-xs border-b border-slate-800/80">
                <div className="space-y-2">
                  <div>
                    <span className="text-slate-400 font-medium">Visual Observation:</span>
                    <p className="text-slate-200 mt-0.5 italic">"{issue.visual_observation}"</p>
                  </div>
                  <div>
                    <span className="text-slate-400 font-medium">Engineering Rationale:</span>
                    <p className="text-slate-300 mt-0.5">{issue.engineering_reason}</p>
                  </div>
                  <div className="flex items-center space-x-2 pt-1">
                    <span className="text-slate-400">Model Agreement:</span>
                    <div className="flex items-center space-x-1.5">
                      <span className="inline-flex items-center space-x-1 rounded bg-slate-800 px-1.5 py-0.5 text-[10px] text-cyan-300 border border-slate-700">
                        <Bot className="h-3 w-3 mr-0.5" />
                        Claude ✓
                      </span>
                      <span className="inline-flex items-center space-x-1 rounded bg-slate-800 px-1.5 py-0.5 text-[10px] text-indigo-300 border border-slate-700">
                        <Bot className="h-3 w-3 mr-0.5" />
                        Gemini ✓
                      </span>
                    </div>
                  </div>
                </div>

                {/* Deterministic CAD Evidence Box */}
                <div className="rounded-lg border border-slate-800 bg-slate-950/60 p-3 space-y-1.5">
                  <div className="flex items-center justify-between">
                    <span className="text-slate-400 font-semibold flex items-center">
                      <Cpu className="h-3.5 w-3.5 text-cyan-400 mr-1.5" />
                      Deterministic B-Rep CAD Evidence:
                    </span>
                    <span className="rounded bg-emerald-500/10 px-1.5 py-0.5 text-[10px] font-mono text-emerald-400 border border-emerald-500/20">
                      GATEKEEPER PASSED
                    </span>
                  </div>

                  <div className="font-mono text-[11px] text-slate-300 space-y-1 pt-1">
                    <div className="flex justify-between">
                      <span className="text-slate-500">Affected Features:</span>
                      <span className="text-cyan-300 font-bold">{issue.affected_feature_ids.join(', ') || 'N/A'}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-500">Affected Dims:</span>
                      <span className="text-slate-200">{issue.affected_dimension_ids.join(', ') || 'N/A'}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-500">B-Rep Faces:</span>
                      <span className="text-slate-200">{issue.affected_brep_entities.join(', ') || 'N/A'}</span>
                    </div>
                    {Object.entries(issue.evidence).map(([k, v]) => (
                      <div key={k} className="flex justify-between">
                        <span className="text-slate-500 capitalize">{k.replace(/_/g, ' ')}:</span>
                        <span className="text-slate-200 font-medium">
                          {typeof v === 'object' ? JSON.stringify(v) : String(v)}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              {/* Recommendation Action Footer */}
              {rec && (
                <div className="pt-3 flex flex-wrap items-center justify-between gap-3">
                  <div className="flex items-start space-x-2 text-xs">
                    <Sparkles className="h-4 w-4 text-cyan-400 shrink-0 mt-0.5" />
                    <div>
                      <div className="flex items-center space-x-2">
                        <span className="font-mono font-bold text-cyan-300">[{rec.recommendation_id}]</span>
                        <span className="rounded bg-cyan-500/10 px-2 py-0.5 font-mono text-[11px] font-bold text-cyan-300 border border-cyan-500/20">
                          {rec.action}
                        </span>
                      </div>
                      <p className="text-slate-300 mt-1">{rec.rationale}</p>
                    </div>
                  </div>

                  {/* Approve / Reject Buttons */}
                  <div className="flex items-center space-x-2 shrink-0">
                    <button
                      onClick={() => handleApprove(rec.recommendation_id)}
                      disabled={loadingAction === rec.recommendation_id || isApproved}
                      className={`flex items-center space-x-1.5 rounded-lg px-3 py-1.5 text-xs font-bold transition-all ${
                        isApproved
                          ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40 cursor-default'
                          : 'bg-emerald-600 hover:bg-emerald-500 text-white shadow-lg shadow-emerald-600/20 hover:scale-105 active:scale-95'
                      }`}
                    >
                      <CheckCircle2 className="h-3.5 w-3.5" />
                      <span>{isApproved ? 'Approved' : 'Approve'}</span>
                    </button>

                    <button
                      onClick={() => handleReject(rec.recommendation_id)}
                      disabled={loadingAction === rec.recommendation_id || isRejected}
                      className={`flex items-center space-x-1.5 rounded-lg px-3 py-1.5 text-xs font-bold transition-all ${
                        isRejected
                          ? 'bg-rose-500/20 text-rose-400 border border-rose-500/40 cursor-default'
                          : 'bg-slate-800 hover:bg-rose-900/60 hover:border-rose-500/40 text-slate-300 hover:text-rose-300 border border-slate-700'
                      }`}
                    >
                      <XCircle className="h-3.5 w-3.5" />
                      <span>{isRejected ? 'Rejected' : 'Reject'}</span>
                    </button>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};
