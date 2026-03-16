// @vitest-environment jsdom

import '@testing-library/jest-dom/vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import DashboardTab from './DashboardTab';
import type {
  AppMessage,
  ScannerRecommendation,
  ScannerRecommendationsResponse,
  Service,
} from '../../types/api';

const { apiMock } = vi.hoisted(() => ({
  apiMock: {
    getServices: vi.fn(),
    getMessages: vi.fn(),
    getScannerRecommendations: vi.fn(),
  },
}));

vi.mock('../ui/card', () => ({
  Card: ({ children, ...props }: React.HTMLAttributes<HTMLDivElement>) => (
    <div {...props}>{children}</div>
  ),
  CardContent: ({ children, ...props }: React.HTMLAttributes<HTMLDivElement>) => (
    <div {...props}>{children}</div>
  ),
  CardHeader: ({ children, ...props }: React.HTMLAttributes<HTMLDivElement>) => (
    <div {...props}>{children}</div>
  ),
  CardTitle: ({ children, ...props }: React.HTMLAttributes<HTMLHeadingElement>) => (
    <h2 {...props}>{children}</h2>
  ),
}));

vi.mock('../shared/StatusIndicators', () => ({
  StatusDot: ({ status }: { status: string }) => <span>{status}</span>,
  Freshness: ({ iso }: { iso: string | null }) => <span>{iso ?? 'N/A'}</span>,
}));

vi.mock('../shared/RenderState', () => ({
  RenderState: ({ kind, message }: { kind: string; message?: string }) => (
    <div data-testid={`state-${kind}`}>{message ?? kind}</div>
  ),
}));

vi.mock('../../services/api', () => ({
  api: apiMock,
}));

vi.mock('../../hooks/useMouseGlow', () => ({
  useMouseGlow: () => vi.fn(),
}));

const servicesMock = apiMock.getServices;
const messagesMock = apiMock.getMessages;
const recommendationsMock = apiMock.getScannerRecommendations;

const sampleServices: Service[] = [
  {
    id: 'api',
    name: 'API',
    description: 'Operator API',
    status: 'running',
    uptime: 3600,
    lastCrawl: '2026-03-15T12:00:00Z',
    rowsInDb: 10,
    containerInfo: 'api',
    type: 'docker',
    allowedActions: ['restart'],
  },
];

const sampleMessages: AppMessage[] = [
  {
    id: 'alert-1',
    timestamp: '2026-03-15T12:00:00Z',
    severity: 'critical',
    sourceModule: 'scanner_alerts',
    message: 'Scanner alert',
    suggestedAction: 'Inspect strategy alert',
  },
];

const sampleRecommendations: ScannerRecommendation[] = [
  {
    scannerRunId: 'scan-1',
    strategyId: 'bulk_essence',
    league: 'Mirage',
    itemOrMarketKey: 'Deafening Essence of Greed',
    whyItFired: 'Spread supports a fast flip',
    buyPlan: 'buy <= 1c',
    maxBuy: 1,
    transformPlan: 'none',
    exitPlan: 'list @ 11c',
    executionVenue: 'manual_trade',
    expectedProfitChaos: 11,
    expectedProfitPerMinuteChaos: 1.1,
    expectedRoi: 1.1,
    expectedHoldTime: '~10m',
    expectedHoldMinutes: 10,
    confidence: 0.9,
    recordedAt: '2026-03-15T12:00:00Z',
  },
];

const sampleResponse: ScannerRecommendationsResponse = {
  recommendations: sampleRecommendations,
  meta: {
    hasMore: false,
    nextCursor: null,
  },
};

describe('DashboardTab', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    servicesMock.mockResolvedValue(sampleServices);
    messagesMock.mockResolvedValue(sampleMessages);
  });

  it('requests dashboard recommendations with the per-minute sort and shared response contract', async () => {
    recommendationsMock.mockResolvedValue(sampleResponse);

    render(<DashboardTab />);

    await waitFor(() => {
      expect(recommendationsMock).toHaveBeenCalledWith({
        sort: 'expected_profit_per_minute_chaos',
        limit: 3,
      });
    });
    expect(await screen.findByText('Spread supports a fast flip')).toBeInTheDocument();
    expect(screen.getByText('bulk_essence: Deafening Essence of Greed')).toBeInTheDocument();
  });

  it('renders the degraded dashboard state when recommendations fail to load', async () => {
    recommendationsMock.mockRejectedValue(new Error('Recommendations offline'));

    render(<DashboardTab />);

    expect(await screen.findByTestId('state-degraded')).toHaveTextContent(
      'Recommendations offline'
    );
    expect(screen.getByText('No opportunities right now')).toBeInTheDocument();
  });
});
