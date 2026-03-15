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
  StashStatus,
  ScannerRecommendation,
  ScannerSummary,
  StaleListingOpp,
  StashTab,
} from '@/types/api';

export interface IngestionRow {
  queue_key: string;
  feed_kind: string;
  status: string;
  last_ingest_at: string;
}

export interface ScannerRow {
  strategy_id: string;
  recommendation_count: number;
}

export interface AlertRow {
  alert_id: string;
  recorded_at: string;
  status: string;
  item_or_market_key: string;
}

export interface BacktestRow {
  status: string;
  count: number;
}

export interface BacktestAnalytics {
  rows: BacktestRow[];
  summaryRows: BacktestRow[];
  detailRows: BacktestRow[];
  totals: { summary: number; detail: number };
}

export interface MlAnalytics {
  status: Record<string, unknown>;
}

export interface ReportAnalytics {
  status: string;
  report: Record<string, unknown>;
}

type ApiErrorPayload = {
  error?: {
    code?: string;
    message?: string;
    details?: unknown;
  };
};

type ContractPayload = {
  primary_league?: string;
};

import { API_BASE } from './config';
import { logApiError } from './apiErrorLog';
const API_KEY = import.meta.env.VITE_API_KEY as string | undefined;

let cachedPrimaryLeague: string | null = null;

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const url = API_BASE ? `${API_BASE}${path}` : path;
  const method = init?.method || 'GET';
  let response: Response;
  try {
    response = await fetch(url, {
      ...init,
      credentials: 'include',
      headers: {
        'Content-Type': 'application/json',
        ...(API_KEY ? { Authorization: `Bearer ${API_KEY}` } : {}),
        ...(init?.headers || {}),
      },
    });
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Network error';
    logApiError({ method, path, errorCode: 'network_error', message });
    throw err;
  }
  if (!response.ok) {
    let payload: ApiErrorPayload = {};
    try {
      payload = (await response.json()) as ApiErrorPayload;
    } catch {
      payload = {};
    }
    const code = payload.error?.code || 'request_failed';
    const baseMessage = payload.error?.message || `Request failed (${response.status})`;
    const detail = formatApiErrorDetail(payload.error?.details);
    const message = detail ? `${baseMessage} (${detail})` : baseMessage;
    logApiError({ method, path, statusCode: response.status, errorCode: code, message });
    throw new Error(`${code}: ${message}`);
  }
  if (response.status === 204) {
    return {} as T;
  }
  return (await response.json()) as T;
}

function formatApiErrorDetail(details: unknown): string | null {
  if (typeof details === 'string' && details.trim()) {
    return details.trim();
  }
  if (
    details &&
    typeof details === 'object' &&
    'reason' in details &&
    typeof details.reason === 'string' &&
    details.reason.trim()
  ) {
    return details.reason.trim();
  }
  return null;
}

async function primaryLeague(): Promise<string> {
  if (cachedPrimaryLeague) {
    return cachedPrimaryLeague;
  }
  const payload = await request<ContractPayload>('/api/v1/ops/contract');
  cachedPrimaryLeague = payload.primary_league || 'Mirage';
  return cachedPrimaryLeague;
}

export async function getAnalyticsIngestion() {
  const payload = await request<{ rows: IngestionRow[] }>('/api/v1/ops/analytics/ingestion');
  return payload.rows;
}

export async function getAnalyticsScanner() {
  const payload = await request<{ rows: ScannerRow[] }>('/api/v1/ops/analytics/scanner');
  return payload.rows;
}

export async function getAnalyticsAlerts() {
  const payload = await request<{ rows: AlertRow[] }>('/api/v1/ops/analytics/alerts');
  return payload.rows;
}

export async function getAnalyticsBacktests() {
  return request<BacktestAnalytics>('/api/v1/ops/analytics/backtests');
}

export async function getAnalyticsMl() {
  return request<MlAnalytics>('/api/v1/ops/analytics/ml');
}

export async function getAnalyticsReport() {
  return request<ReportAnalytics>('/api/v1/ops/analytics/report');
}

export const api: ApiService = {
  async getScannerSummary() {
    return request<ScannerSummary>('/api/v1/ops/scanner/summary');
  },

  async getScannerRecommendations() {
    const payload = await request<{ recommendations: ScannerRecommendation[] }>('/api/v1/ops/scanner/recommendations');
    return payload.recommendations;
  },

  async ackAlert(alertId: string) {
    await request<{ alertId: string; status: string }>(`/api/v1/ops/alerts/${encodeURIComponent(alertId)}/ack`, {
      method: 'POST',
    });
  },

  async getStashStatus() {
    const league = await primaryLeague();
    return request<StashStatus>(`/api/v1/stash/status?league=${encodeURIComponent(league)}&realm=pc`);
  },

  async getMlAutomationStatus() {
    const league = await primaryLeague();
    return request<Record<string, unknown>>(`/api/v1/ml/leagues/${encodeURIComponent(league)}/automation/status`);
  },

  async getMlAutomationHistory() {
    const league = await primaryLeague();
    return request<Record<string, unknown>>(`/api/v1/ml/leagues/${encodeURIComponent(league)}/automation/history`);
  },

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
    return [];
  },

  async getStaleListings() {
    return [];
  },

  async getGemStates() {
    return [];
  },

  async getHeistDrops() {
    return [];
  },

  async getShipmentRecommendation() {
    return {
      chosenPort: 'n/a',
      resourceMix: {},
      dustToAdd: 0,
      expectedValue: 0,
      expectedValuePerHour: 0,
      expectedRiskLoss: 0,
      whyThisWon: 'n/a',
      updatedAt: new Date().toISOString(),
    };
  },

  async getGoldShadowPrice() {
    return {
      chaosPerGold: 0,
      feeInChaos: 0,
      denominationHint: 'n/a',
      updatedAt: new Date().toISOString(),
    };
  },

  async getSessionRecommendation() {
    return {
      recommended: 'map',
      triggerReason: 'n/a',
      updatedAt: new Date().toISOString(),
    };
  },

  async simulateGearSwap(_candidateItem) {
    return {
      current: {
        fireRes: 0, coldRes: 0, lightningRes: 0, chaosRes: 0, spellSuppression: 0,
        life: 0, str: 0, dex: 0, int: 0, evasionMasteryActive: false, auraFit: false,
      },
      simulated: {
        fireRes: 0, coldRes: 0, lightningRes: 0, chaosRes: 0, spellSuppression: 0,
        life: 0, str: 0, dex: 0, int: 0, evasionMasteryActive: false, auraFit: false,
      },
      failStates: ['Not supported'],
      passStates: [],
    };
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
