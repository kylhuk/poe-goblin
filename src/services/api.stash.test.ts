import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest';
import { clearApiErrors, getApiErrors } from './apiErrorLog';

const { getSessionMock } = vi.hoisted(() => ({
  getSessionMock: vi.fn(),
}));

const { getSelectedLeagueMock } = vi.hoisted(() => ({
  getSelectedLeagueMock: vi.fn(),
}));

vi.mock('@/lib/supabaseClient', () => ({
  supabase: {
    auth: {
      getSession: getSessionMock,
    },
  },
  SUPABASE_PROJECT_ID: 'project-id',
}));

vi.mock('@/services/league', () => ({
  getSelectedLeague: getSelectedLeagueMock,
}));

async function loadApi() {
  const { api } = await import('./api');
  return api;
}

describe('stash api methods', () => {
  beforeEach(() => {
    vi.resetModules();
    vi.stubEnv('VITE_SUPABASE_PROJECT_ID', 'project-id');
    getSessionMock.mockResolvedValue({ data: { session: { access_token: 'token-123' } } });
    getSelectedLeagueMock.mockReturnValue('Hardcore Mirage');
    clearApiErrors();
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllEnvs();
  });

  test('starts a stash scan and returns scan metadata', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        status: 202,
        json: async () => ({
          scanId: 'scan-2',
          status: 'running',
          startedAt: '2026-03-21T12:01:00Z',
          accountName: 'qa-exile',
          league: 'Mirage',
          realm: 'pc',
        }),
      } as Response);
    vi.stubGlobal('fetch', fetchMock);

    const api = await loadApi();
    const result = await api.startStashScan();

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(result.scanId).toBe('scan-2');
    expect(result.accountName).toBe('qa-exile');
    expect(fetchMock.mock.calls[0][1]).toMatchObject({
      headers: expect.objectContaining({
        'x-proxy-path': '/api/v1/stash/scan/start?league=Hardcore%20Mirage&realm=pc',
      }),
    });
  });

  test('scoped stash lifecycle requests include the selected league and realm', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        status: 202,
        json: async () => ({
          scanId: 'scan-2',
          status: 'running',
          startedAt: '2026-03-21T12:01:00Z',
          accountName: 'qa-exile',
          league: 'Hardcore Mirage',
          realm: 'pc',
        }),
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({
          status: 'running',
          activeScanId: 'scan-2',
          publishedScanId: 'scan-1',
          startedAt: '2026-03-21T12:01:00Z',
          updatedAt: '2026-03-21T12:02:00Z',
          publishedAt: null,
          progress: {
            tabsTotal: 8,
            tabsProcessed: 3,
            itemsTotal: 120,
            itemsProcessed: 44,
          },
          error: null,
        }),
      } as Response);
    const startValuationsResponse = {
      ok: true,
      status: 202,
      json: async () => ({}),
    } as Response;
    const valuationsStatusResponse = {
      ok: true,
      status: 200,
      json: async () => ({
        status: 'published',
      }),
    } as Response;
    const valuationsResultResponse = {
      ok: true,
      status: 200,
      json: async () => ({
        scanId: 'scan-2',
        stashId: 'scan-2',
        structuredMode: true,
        items: [],
      }),
    } as Response;
    fetchMock
      .mockResolvedValueOnce(startValuationsResponse)
      .mockResolvedValueOnce(valuationsStatusResponse)
      .mockResolvedValueOnce(valuationsResultResponse)
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({
          fingerprint: 'sig:item-1',
          item: {
            name: 'Grim Bane',
            itemClass: 'Helmet',
            rarity: 'rare',
            iconUrl: 'https://web.poecdn.com/item.png',
          },
          history: [
            {
              scanId: 'scan-2',
              pricedAt: '2026-03-21T12:00:00Z',
              predictedValue: 45,
              listedPrice: 40,
              currency: 'chaos',
              confidence: 82,
              interval: { p10: 39, p90: 51 },
              priceRecommendationEligible: true,
              estimateTrust: 'normal',
              estimateWarning: '',
              fallbackReason: '',
            },
          ],
        }),
      } as Response);
    vi.stubGlobal('fetch', fetchMock);

    const api = await loadApi();
    await api.startStashScan();
    const status = await api.getStashScanStatus();
    await api.startStashValuations();
    await api.getStashValuationsStatus();
    await api.getStashValuationsResult();
    const history = await api.getStashItemHistory('sig:item-1');

    expect(status.activeScanId).toBe('scan-2');
    expect(status.progress.itemsProcessed).toBe(44);
    expect(history.item.name).toBe('Grim Bane');
    expect(history.history[0].interval.p10).toBe(39);
    expect(fetchMock).toHaveBeenCalledTimes(6);

    const requestedPaths = fetchMock.mock.calls.map(([, init]) => {
      const headers = (init?.headers ?? {}) as Record<string, string>;
      return headers['x-proxy-path'];
    });

    expect(requestedPaths).toEqual([
      '/api/v1/stash/scan/start?league=Hardcore%20Mirage&realm=pc',
      '/api/v1/stash/scan/status?league=Hardcore%20Mirage&realm=pc',
      '/api/v1/stash/scan/valuations/start?league=Hardcore%20Mirage&realm=pc',
      '/api/v1/stash/scan/valuations/status?league=Hardcore%20Mirage&realm=pc',
      '/api/v1/stash/scan/valuations/result?league=Hardcore%20Mirage&realm=pc',
      '/api/v1/stash/items/sig%3Aitem-1/history?league=Hardcore%20Mirage&realm=pc',
    ]);
  });

  test('preserves backend price judgments from stash scan results', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({
          scanId: 'scan-1',
          publishedAt: '2026-03-21T12:00:00Z',
          isStale: false,
          scanStatus: null,
          stashTabs: [
            {
              id: 'tab-1',
              name: 'Currency',
              type: 'currency',
              items: [
                {
                  id: 'item-1',
                  fingerprint: 'sig:item-1',
                  name: 'Grim Bane',
                  typeLine: 'Hubris Circlet',
                  iconUrl: 'https://web.poecdn.com/item.png',
                  x: 0,
                  y: 0,
                  w: 1,
                  h: 1,
                  frameType: 2,
                  itemClass: 'Helmet',
                  rarity: 'rare',
                  listedPrice: 100,
                  estimatedPrice: 50,
                  estimatedPriceConfidence: 82,
                  priceDeltaChaos: 50,
                  priceDeltaPercent: 100,
                  priceEvaluation: 'well_priced',
                  currency: 'chaos',
                },
              ],
            },
          ],
          tabsMeta: [
            { id: 'tab-1', tabIndex: 0, name: 'Currency', type: 'CurrencyStash' },
          ],
          numTabs: 1,
        }),
      } as Response);
    vi.stubGlobal('fetch', fetchMock);

    const api = await loadApi();
    const result = await api.getStashScanResult();

    expect(result.stashTabs[0].items[0].estimatedPrice).toBe(50);
    expect(result.stashTabs[0].items[0].priceDeltaChaos).toBe(50);
    expect(result.stashTabs[0].items[0].priceDeltaPercent).toBe(100);
    expect(result.stashTabs[0].items[0].priceEvaluation).toBe('well_priced');
  });

  test('derives tabsMeta from stashTabs when backend omits tab metadata (via scan/result)', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({
          scanId: 'scan-2',
          publishedAt: '2026-03-21T12:03:00Z',
          isStale: false,
          scanStatus: null,
          stashTabs: [
            { id: 'tab-1', name: 'Empty', type: 'normal', items: [] },
            { id: 'tab-2', name: 'Gear', type: 'normal', items: [] },
          ],
        }),
      } as Response);
    vi.stubGlobal('fetch', fetchMock);

    const api = await loadApi();
    const result = await api.getStashScanResult();

    expect(result.tabsMeta).toEqual([
      { id: 'tab-1', tabIndex: 0, name: 'Empty', type: 'normal' },
      { id: 'tab-2', tabIndex: 1, name: 'Gear', type: 'normal' },
    ]);
    expect(result.stashTabs[1].returnedIndex).toBe(1);
  });
});
