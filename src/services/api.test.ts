import { afterEach, describe, expect, test, vi } from 'vitest';
import { api } from './api';
import type { ScannerRecommendation } from '@/types/api';

const sampleRecommendation: ScannerRecommendation = {
  scannerRunId: 'scan-1',
  strategyId: 'strategy-1',
  league: 'Mirage',
  itemOrMarketKey: 'Unique Item',
  whyItFired: 'opportunity',
  buyPlan: 'buy',
  maxBuy: 1,
  transformPlan: 'keep',
  exitPlan: 'sell',
  executionVenue: 'exchange',
  expectedProfitChaos: 50,
  expectedProfitPerMinuteChaos: 5,
  expectedRoi: 0.12,
  expectedHoldTime: '~5m',
  expectedHoldMinutes: 5,
  confidence: 0.85,
  recordedAt: '2026-03-15T00:00:00Z',
};

const createResponse = (payload: unknown) =>
  Promise.resolve({
    ok: true,
    status: 200,
    json: async () => payload,
  } as Response);

describe('api.getScannerRecommendations', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  test('serializes filters into backend query params and returns metadata', async () => {
    const responsePayload = {
      recommendations: [sampleRecommendation],
      meta: {
        nextCursor: 'cursor-123',
        hasMore: true,
      },
    };
    const fetchMock = vi.fn(() => createResponse(responsePayload));
    vi.stubGlobal('fetch', fetchMock);

    const result = await api.getScannerRecommendations({
      sort: 'liquidity_score',
      limit: 5,
      cursor: 'cursor-123',
      league: 'Mirage',
      strategyId: 'strategy-1',
      minConfidence: 0.75,
    });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [calledUrl] = fetchMock.mock.calls[0];
    const parsedUrl = new URL(String(calledUrl));
    expect(parsedUrl.pathname).toBe('/api/v1/ops/scanner/recommendations');
    expect(parsedUrl.searchParams.get('sort')).toBe('liquidity_score');
    expect(parsedUrl.searchParams.get('limit')).toBe('5');
    expect(parsedUrl.searchParams.get('cursor')).toBe('cursor-123');
    expect(parsedUrl.searchParams.get('league')).toBe('Mirage');
    expect(parsedUrl.searchParams.get('strategy_id')).toBe('strategy-1');
    expect(parsedUrl.searchParams.get('min_confidence')).toBe('0.75');
    expect(result).toEqual(responsePayload);
  });

  test('propagates invalid cursor metadata errors instead of swallowing them', async () => {
    const fetchMock = vi.fn(() =>
      Promise.resolve({
        ok: false,
        status: 400,
        json: async () => ({
          error: {
            code: 'invalid_input',
            message: 'cursor invalid',
            details: { reason: 'cursor malformed' },
          },
        }),
      } as Response)
    );
    vi.stubGlobal('fetch', fetchMock);

    await expect(api.getScannerRecommendations()).rejects.toThrow(/invalid_input/);
  });
});
