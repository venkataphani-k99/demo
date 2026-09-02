import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import React from 'react';
import { Navigation } from '../src/components/Navigation';
import { FeaturesTable } from '../src/components/FeaturesTable';
import { DimensionsTable } from '../src/components/DimensionsTable';
import { AIReviewPanel } from '../src/components/AIReviewPanel';
import { EngineeringIssuesPanel } from '../src/components/EngineeringIssuesPanel';
import { RecognizedFeature, DimensionCandidate, EngineeringIssue, EngineeringRecommendation, api } from '../lib/api';

describe('Frontend Component Tests (Phase 13)', () => {
  const mockFeatures: RecognizedFeature[] = [
    {
      feature_id: 'CBORE_001',
      type: 'counterbored_hole',
      faces: ['Face4', 'Face5', 'Face23'],
      parameters: { bore_diameter: 5.5, counterbore_diameter: 11.0, depth: 3.3 },
      status: 'fully_dimensioned',
      confidence: 1.0,
      dimension_ids: ['D001', 'D002', 'D015'],
    },
    {
      feature_id: 'BORE_003',
      type: 'internal_bore',
      faces: ['Face8', 'Face9'],
      parameters: { diameter: 30.0, sweep_angle_deg: 61.32 },
      status: 'ambiguous',
      confidence: 1.0,
      dimension_ids: ['D004', 'D013'],
    },
  ];

  const mockDimensions: DimensionCandidate[] = [
    {
      id: 'D001',
      type: 'diameter',
      value: 5.5,
      formatted_text: 'Ø5.50 mm',
      status: 'placed',
      feature_id: 'CBORE_001',
      view: 'Top',
      source_entities: ['Face4'],
    },
    {
      id: 'D004',
      type: 'diameter',
      value: 30.0,
      formatted_text: 'Ø30.00 mm',
      status: 'placed',
      feature_id: 'BORE_003',
      view: 'Right',
      source_entities: ['Face8', 'Face9'],
    },
  ];

  const mockIssues: EngineeringIssue[] = [
    {
      issue_id: 'ISSUE_001',
      title: 'Internal vaulted cavity insufficiently communicated in standard orthographic views',
      category: 'ambiguous_geometry',
      severity: 'medium',
      description: 'The internal cylindrical cavity feature BORE_003 has a partial arc sweep (61.32°).',
      visual_observation: 'Cylindrical cavity visible without internal depth cross-section.',
      engineering_reason: 'Partial sweeps require explicit section views per ASME Y14.3.',
      source_providers: ['claude', 'gemini'],
      source_models: ['claude-3-5-sonnet', 'gemini-2.5-flash'],
      affected_view: 'Right',
      affected_feature_ids: ['BORE_003'],
      affected_dimension_ids: ['D004', 'D013'],
      affected_brep_entities: ['Face8', 'Face9'],
      evidence: { diameter_mm: 30.0, sweep_angle_deg: 61.32 },
      deterministic_validation_status: 'validated',
      validation_errors: [],
      recommendation_ids: ['REC_001'],
      human_review_required: true,
      status: 'AWAITING_HUMAN_APPROVAL',
    },
  ];

  const mockRecommendations: EngineeringRecommendation[] = [
    {
      recommendation_id: 'REC_001',
      issue_id: 'ISSUE_001',
      action: 'ADD_SECTION_VIEW',
      rationale: 'Add Section View A-A through the centerline of BORE_003.',
      affected_entities: ['Face8', 'Face9'],
      affected_dimensions: ['D004', 'D013'],
      affected_views: ['Right'],
      expected_benefit: 'Eliminates manufacturing ambiguity.',
      validation_status: 'validated',
      validation_errors: [],
      requires_human_approval: true,
      approval_status: 'AWAITING_HUMAN_APPROVAL',
    },
  ];

  it('1. Renders Navigation bar with kernel metadata and project name', () => {
    render(<Navigation projectName="Pieza18_1.STEP" />);
    expect(screen.getByText('CAD Intelligence')).toBeInTheDocument();
    expect(screen.getByText('FreeCAD / OCCT')).toBeInTheDocument();
    expect(screen.getByText('Pieza18_1.STEP')).toBeInTheDocument();
  });

  it('2. Renders Features Table and formats parameters accurately', () => {
    const handleSelect = vi.fn();
    render(
      <FeaturesTable
        features={mockFeatures}
        selectedFeatureId={null}
        onSelectFeature={handleSelect}
      />
    );
    expect(screen.getByText('CBORE_001')).toBeInTheDocument();
    expect(screen.getByText('BORE_003')).toBeInTheDocument();
    expect(screen.getByText('Ø5.5 / Ø11.0 mm')).toBeInTheDocument();
    expect(screen.getByText('Ø30.0 mm')).toBeInTheDocument();

    fireEvent.click(screen.getByText('CBORE_001'));
    expect(handleSelect).toHaveBeenCalledWith('CBORE_001');
  });

  it('3. Renders Dimensions Table with placed status and views', () => {
    render(<DimensionsTable dimensions={mockDimensions} />);
    expect(screen.getByText('D001')).toBeInTheDocument();
    expect(screen.getByText('Ø5.50 mm')).toBeInTheDocument();
    expect(screen.getByText('D004')).toBeInTheDocument();
    expect(screen.getByText('Ø30.00 mm')).toBeInTheDocument();
    expect(screen.getAllByText('Placed in TechDraw').length).toBe(2);
  });

  it('4. Renders AI Review Panel and switches between Claude, Gemini, and Consensus tabs', () => {
    render(
      <AIReviewPanel
        placedCount={14}
        consensus={{
          total_issues_identified: 4,
          consensus_issues_count: 4,
          consensus_issue_ids: ['ISSUE_001', 'ISSUE_002', 'ISSUE_003', 'ISSUE_004'],
          claude_only_issue_ids: [],
          gemini_only_issue_ids: [],
          conflicting_issues_count: 0,
          total_validated_recommendations: 4,
          total_rejected_recommendations: 0,
          human_approval_state: 'AWAITING_HUMAN_APPROVAL',
        }}
      />
    );
    expect(screen.getByText('Multimodal Visual AI Drawing Review')).toBeInTheDocument();
    // New UI: shows 'Phase 15 Multi-Model CAD Intelligence' badge
    expect(screen.getByText('Phase 15 Multi-Model CAD Intelligence')).toBeInTheDocument();
    // Summary stats: total findings comes from issues array (empty here → 0)
    expect(screen.getByText('Total Findings')).toBeInTheDocument();
    // Engineering Findings section header is present
    expect(screen.getByText('Engineering Findings')).toBeInTheDocument();

    // Click Claude Tab
    fireEvent.click(screen.getByText('Anthropic Claude 3.5'));
    expect(screen.getByText('claude-3-5-sonnet-20241022')).toBeInTheDocument();

    // Click Gemini Tab
    fireEvent.click(screen.getByText('Google Gemini 2.5'));
    expect(screen.getByText('gemini-2.5-flash')).toBeInTheDocument();
  });

  it('5. Renders Engineering Issues with B-Rep evidence and triggers human approval', async () => {
    vi.spyOn(api, 'approveRecommendation').mockResolvedValueOnce({
      recommendation_id: 'REC_001',
      issue_id: 'ISSUE_001',
      action: 'ADD_SECTION_VIEW',
      approval_status: 'APPROVED',
      message: 'Approved with zero CAD modification.',
    });

    const handleRefresh = vi.fn();

    render(
      <EngineeringIssuesPanel
        projectId="test-proj"
        issues={mockIssues}
        recommendations={mockRecommendations}
        onRefreshIssues={handleRefresh}
      />
    );

    expect(screen.getByText('ISSUE_001')).toBeInTheDocument();
    expect(screen.getByText('GATEKEEPER PASSED')).toBeInTheDocument();
    expect(screen.getByText('AWAITING HUMAN APPROVAL')).toBeInTheDocument();
    expect(screen.getByText('ADD_SECTION_VIEW')).toBeInTheDocument();

    // Click Approve button
    const approveBtn = screen.getByText('Approve');
    fireEvent.click(approveBtn);

    await waitFor(() => {
      expect(api.approveRecommendation).toHaveBeenCalledWith('test-proj', 'REC_001');
      expect(handleRefresh).toHaveBeenCalled();
    });
  });

  it('6. Triggers human rejection cleanly with zero CAD modification', async () => {
    vi.spyOn(api, 'rejectRecommendation').mockResolvedValueOnce({
      recommendation_id: 'REC_001',
      issue_id: 'ISSUE_001',
      action: 'ADD_SECTION_VIEW',
      approval_status: 'REJECTED',
      message: 'Rejected by engineer.',
    });

    const handleRefresh = vi.fn();

    render(
      <EngineeringIssuesPanel
        projectId="test-proj"
        issues={mockIssues}
        recommendations={mockRecommendations}
        onRefreshIssues={handleRefresh}
      />
    );

    const rejectBtn = screen.getByText('Reject');
    fireEvent.click(rejectBtn);

    await waitFor(() => {
      expect(api.rejectRecommendation).toHaveBeenCalledWith('test-proj', 'REC_001');
      expect(handleRefresh).toHaveBeenCalled();
    });
  });

  it('7. api.getDimensions properly parses response containing .dimensions list', async () => {
    const mockApiResponse = {
      project_id: 'test-proj',
      total_candidates: 20,
      placed_count: 14,
      excluded_count: 6,
      dimensions: [
        { id: 'D001', type: 'diameter', value: 5.5, display_value: 'Ø5.50 mm', status: 'placed', selected_view: 'Top' },
        { id: 'D002', type: 'diameter', value: 11.0, display_value: 'Ø11.00 mm', status: 'placed', selected_view: 'Top' },
        { id: 'D003', type: 'diameter', value: 10.0, display_value: 'Ø10.00 mm', status: 'placed', selected_view: 'Left' },
      ],
      feature_coverages: [],
    };

    // Mock global fetch
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      json: async () => mockApiResponse,
    } as unknown as Response);

    const dims = await api.getDimensions('test-proj');
    expect(dims).toHaveLength(3);
    expect(dims[0].id).toBe('D001');
    expect(dims[0].display_value).toBe('Ø5.50 mm');
    expect(dims[0].status).toBe('placed');

    fetchSpy.mockRestore();
  });

  it('8. DimensionsTable renders full placed dimension set with consistent placement count', () => {
    const fullDims: DimensionCandidate[] = [
      { id: 'D001', type: 'diameter', value: 5.5, display_value: 'Ø5.50 mm', placement_status: 'placed', selected_view: 'Top' },
      { id: 'D002', type: 'diameter', value: 11.0, display_value: 'Ø11.00 mm', placement_status: 'placed', selected_view: 'Top' },
      { id: 'D003', type: 'diameter', value: 10.0, display_value: 'Ø10.00 mm', placement_status: 'placed', selected_view: 'Left' },
      { id: 'D008', type: 'depth', value: 4.75, display_value: '4.75 mm', placement_status: 'excluded', selected_view: 'Front' },
    ];

    render(<DimensionsTable dimensions={fullDims} />);
    expect(screen.getByText('3 / 4 Placed')).toBeInTheDocument();
    expect(screen.getByText('D001')).toBeInTheDocument();
    expect(screen.getByText('D002')).toBeInTheDocument();
    expect(screen.getByText('D003')).toBeInTheDocument();
    expect(screen.getByText('D008')).toBeInTheDocument();
  });
});
