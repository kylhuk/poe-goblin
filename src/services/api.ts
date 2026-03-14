import type {
  ApiService,
  AppMessage,
  FairValueItem,
  GearSwapResult,
  GemState,
  GoldShadowData,
  HeistDrop,
  PriceCheckRequest,
  PriceCheckResponse,
  Service,
  SessionRecommendation,
  ShipmentRecommendation,
  StaleListingOpp,
  StashTab,
} from '@/types/api';
import { getStoredToken } from '@/services/auth';

type ApiErrorPayload = {
  error?: {
    code?: string;
    message?: string;
  };
};

type ContractPayload = {
  primary_league?: string;
};

const API_BASE = 'https://api.poe.lama-lan.ch';
const API_KEY = import.meta.env.VITE_API_KEY as string | undefined;

let cachedPrimaryLeague: string | null = null;

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const url = API_BASE ? `${API_BASE}${path}` : path;
  const userToken = getStoredToken();
  const authToken = userToken || API_KEY;
  const response = await fetch(url, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(authToken ? { Authorization: `Bearer ${authToken}` } : {}),
      ...(init?.headers || {}),
    },
  });
  if (!response.ok) {
    let payload: ApiErrorPayload = {};
    try {
      payload = (await response.json()) as ApiErrorPayload;
    } catch {
      payload = {};
    }
    const code = payload.error?.code || 'request_failed';
    const message = payload.error?.message || `Request failed (${response.status})`;
    throw new Error(`${code}: ${message}`);
  }
  if (response.status === 204) {
    return {} as T;
  }
  return (await response.json()) as T;
}

async function primaryLeague(): Promise<string> {
  if (cachedPrimaryLeague) {
    return cachedPrimaryLeague;
  }
  const payload = await request<ContractPayload>('/api/v1/ops/contract');
  cachedPrimaryLeague = payload.primary_league || 'Mirage';
  return cachedPrimaryLeague;
}

export const api: ApiService = {
  async getServices() {
    const payload = await request<{ services: Service[] }>('/api/v1/ops/services');
    return payload.services;
  },

  async startService(id) {
    await request<{ service: Service }>(`/api/v1/actions/services/${id}/start`, {
      method: 'POST',
    });
  },

  async stopService(id) {
    await request<{ service: Service }>(`/api/v1/actions/services/${id}/stop`, {
      method: 'POST',
    });
  },

  async restartService(id) {
    await request<{ service: Service }>(`/api/v1/actions/services/${id}/restart`, {
      method: 'POST',
    });
  },

  async getFairValueItems() {
    const payload = await request<{ rows: Array<Record<string, unknown>> }>(
      '/api/v1/ops/analytics/ingestion'
    );
    return payload.rows.map((row, index) => ({
      id: String(row.queue_key || `queue-${index}`),
      itemName: String(row.queue_key || 'Queue'),
      fairValue: 0,
      publicStashFloor: 0,
      exchangeImpliedMid: 0,
      sparkline: [],
      spread: 0,
      liquidity: 'low',
      confidence: 0,
      updatedAt: String(row.last_ingest_at || new Date().toISOString()),
    })) as FairValueItem[];
  },

  async getStaleListings() {
    const payload = await request<{ rows: Array<Record<string, unknown>> }>(
      '/api/v1/ops/analytics/scanner'
    );
    return payload.rows.map((row, index) => ({
      id: `scanner-${index}`,
      itemName: String(row.status || 'scanner'),
      askPrice: Number(row.count || 0),
      fairValue: Number(row.count || 0),
      discountPct: 0,
      firstSeen: new Date().toISOString(),
      repricingCount: 0,
      sellerDormancyScore: 0,
      expectedNetMargin: 0,
      expectedSaleTime: 'n/a',
      route: 'public relist',
      grade: 'yellow',
    })) as StaleListingOpp[];
  },

  async getGemStates() {
    const payload = await request<{ rows: Array<Record<string, unknown>> }>(
      '/api/v1/ops/analytics/alerts'
    );
    return payload.rows.map((row, index) => ({
      id: String(row.alert_id || `alert-${index}`),
      gemName: String(row.item_or_market_key || 'Alert'),
      level: 0,
      quality: 0,
      corrupted: false,
      vaalState: null,
      imbuedOutcome: null,
      supportPoolSize: 0,
      currentAsk: 0,
      modelFairValue: 0,
      anomalyScore: 0,
      comparables: [],
      updatedAt: String(row.recorded_at || new Date().toISOString()),
    })) as GemState[];
  },

  async getHeistDrops() {
    const payload = await request<{ rows: Array<Record<string, unknown>> }>(
      '/api/v1/ops/analytics/backtests'
    );
    return payload.rows.map((row, index) => ({
      id: `backtest-${index}`,
      itemName: String(row.status || 'backtest'),
      itemClass: 'Backtest',
      bin: 'ignore',
      estimatedValueBand: String(row.count || 0),
      reason: 'Backtest status distribution',
    })) as HeistDrop[];
  },

  async getShipmentRecommendation() {
    const payload = await request<{ status?: Record<string, unknown> }>(
      '/api/v1/ops/analytics/ml'
    );
    return {
      chosenPort: 'ML status',
      resourceMix: { hotspots: Number((payload.status?.route_hotspots as unknown[])?.length || 0) },
      dustToAdd: 0,
      expectedValue: 0,
      expectedValuePerHour: 0,
      expectedRiskLoss: 0,
      whyThisWon: String(payload.status?.status || 'no_status'),
      updatedAt: new Date().toISOString(),
    } satisfies ShipmentRecommendation;
  },

  async getGoldShadowPrice() {
    const payload = await request<{ report?: Record<string, unknown> }>(
      '/api/v1/ops/analytics/report'
    );
    return {
      chaosPerGold: Number(payload.report?.realized_pnl_chaos || 0),
      feeInChaos: 0,
      denominationHint: 'daily_report',
      updatedAt: new Date().toISOString(),
    } satisfies GoldShadowData;
  },

  async getSessionRecommendation() {
    const messages = await this.getMessages();
    const critical = messages.find((m) => m.severity === 'critical');
    return {
      recommended: critical ? 'trade batch' : 'map',
      triggerReason: critical?.message || 'No critical alerts',
      updatedAt: new Date().toISOString(),
    } satisfies SessionRecommendation;
  },

  async simulateGearSwap(_candidateItem) {
    return {
      current: {
        fireRes: 0,
        coldRes: 0,
        lightningRes: 0,
        chaosRes: 0,
        spellSuppression: 0,
        life: 0,
        str: 0,
        dex: 0,
        int: 0,
        evasionMasteryActive: false,
        auraFit: false,
      },
      simulated: {
        fireRes: 0,
        coldRes: 0,
        lightningRes: 0,
        chaosRes: 0,
        spellSuppression: 0,
        life: 0,
        str: 0,
        dex: 0,
        int: 0,
        evasionMasteryActive: false,
        auraFit: false,
      },
      failStates: ['Live simulation unavailable in phase 1'],
      passStates: [],
    } satisfies GearSwapResult;
  },

  async priceCheck(req) {
    const league = await primaryLeague();
    return request<PriceCheckResponse>(`/api/v1/ops/leagues/${league}/price-check`, {
      method: 'POST',
      body: JSON.stringify(req),
    });
  },

  async getStashTabs() {
    const league = await primaryLeague();
    const payload = await request<{ stashTabs: StashTab[] }>(
      `/api/v1/stash/tabs?league=${encodeURIComponent(league)}&realm=pc`
    );
    return payload.stashTabs;
  },

  async getMessages() {
    const payload = await request<{ messages: AppMessage[] }>('/api/v1/ops/messages');
    return payload.messages;
  },
};
