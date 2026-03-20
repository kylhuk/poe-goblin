import type {
  ApiService,
  AppMessage,
  DashboardResponse,
  FairValueItem,
  GearSwapResult,
  GemState,
  GoldShadowData,
  HeistDrop,
  MlAutomationHistory,
  MlAutomationStatus,
  MlPredictOneRequest,
  MlPredictOneResponse,
  PriceCheckRequest,
  PriceCheckResponse,
  PricingOutliersRequest,
  PricingOutliersResponse,
  ScannerRecommendationsRequest,
  ScannerRecommendationsResponse,
  ScannerSummary,
  SearchHistoryRequest,
  SearchHistoryResponse,
  SearchSuggestionsResponse,
  Service,
  SessionRecommendation,
  ShipmentRecommendation,
  StashStatus,
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

export interface MlCandidateComparison {
  candidate_run_id: string;
  incumbent_run_id: string;
  candidate_avg_mdape: number;
  incumbent_avg_mdape: number;
  candidate_avg_interval_coverage: number;
  incumbent_avg_interval_coverage: number;
  mdape_improvement: number;
  coverage_delta: number;
  coverage_floor_ok: boolean;
}

export interface MlPromotionPolicy {
  mdape_ceiling: number | null;
  coverage_floor: number | null;
  min_rows: number | null;
  [key: string]: unknown;
}

export interface MlWarmup {
  status: string;
  message: string | null;
  runs_needed: number | null;
  runs_completed: number | null;
  [key: string]: unknown;
}

export interface MlRouteHotspot {
  route: string | null;
  avg_mdape: number | null;
  avg_interval_coverage: number | null;
  sample_count: number | null;
  anomaly: boolean | null;
  [key: string]: unknown;
}

export interface MlStatus {
  league: string;
  run: string;
  status: string;
  promotion_verdict: string;
  stop_reason: string;
  active_model_version: string | null;
  latest_avg_mdape: number;
  latest_avg_interval_coverage: number;
  candidate_vs_incumbent: MlCandidateComparison | null;
  route_hotspots: MlRouteHotspot[];
  promotion_policy: MlPromotionPolicy | null;
  warmup: MlWarmup | null;
}

export interface MlAnalytics {
  status: MlStatus;
}

export interface ReportData {
  league: string;
  recommendations: number;
  alerts: number;
  journal_events: number;
  journal_positions: number;
  backtest_summary_rows: number;
  backtest_detail_rows: number;
  gold_currency_ref_hour_rows: number;
  gold_listing_ref_hour_rows: number;
  gold_liquidity_ref_hour_rows: number;
  gold_bulk_premium_hour_rows: number;
  gold_set_ref_hour_rows: number;
  realized_pnl_chaos: number;
}

// ========== Gold Diagnostics ==========
export interface GoldDiagnosticsMart {
  martName: string;
  sourceName: string | null;
  diagnosticState: string;
  sourceRowCount: number;
  goldRowCount: number;
  sourceLatestAt: string | null;
  goldLatestAt: string | null;
  goldFreshnessMinutes: number | null;
  sourceToGoldLagMinutes: number | null;
  leagueVisibility: string | null;
  sourceLeagueRows: number | null;
  goldLeagueRows: number | null;
}

export interface GoldDiagnosticsSummary {
  status: string;
  martCount: number;
  problemMarts: number;
  goldEmptyMarts: number;
  staleMarts: number;
  missingLeagueMarts: number;
}

export interface GoldDiagnosticsResponse {
  league: string;
  summary: GoldDiagnosticsSummary;
  marts: GoldDiagnosticsMart[];
}

// ========== ML Rollout Controls ==========
export interface RolloutControls {
  league: string;
  shadowMode: boolean;
  cutoverEnabled: boolean;
  candidateModelVersion: string | null;
  incumbentModelVersion: string | null;
  effectiveServingModelVersion: string | null;
  updatedAt: string | null;
  lastAction: string | null;
}

export interface ReportAnalytics {
  status: string;
  report: ReportData;
  goldDiagnostics?: GoldDiagnosticsResponse | null;
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

import { logApiError } from './apiErrorLog';
import { supabase } from '@/integrations/supabase/client';

let cachedPrimaryLeague: string | null = null;

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const method = init?.method || 'GET';
  let response: Response;
  try {
    const { data: { session } } = await supabase.auth.getSession();
    const token = session?.access_token;
    if (!token) {
      throw new Error('Not authenticated');
    }

    const projectId = import.meta.env.VITE_SUPABASE_PROJECT_ID;
    const url = `https://${projectId}.supabase.co/functions/v1/api-proxy`;

    response = await fetch(url, {
      ...init,
      credentials: 'include',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
        'x-proxy-path': path,
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

function normalizeMlCandidateComparison(raw: unknown): MlCandidateComparison | null {
  const o = asObject(raw);
  if (Object.keys(o).length === 0) return null;
  const hasAnyRunId = optString(o.candidate_run_id ?? o.candidateRunId);
  if (!hasAnyRunId) return null;
  return {
    candidate_run_id: optString(o.candidate_run_id ?? o.candidateRunId) ?? '',
    incumbent_run_id: optString(o.incumbent_run_id ?? o.incumbentRunId) ?? '',
    candidate_avg_mdape: optNumber(o.candidate_avg_mdape ?? o.candidateAvgMdape) ?? 0,
    incumbent_avg_mdape: optNumber(o.incumbent_avg_mdape ?? o.incumbentAvgMdape) ?? 0,
    candidate_avg_interval_coverage: optNumber(o.candidate_avg_interval_coverage ?? o.candidateAvgIntervalCoverage) ?? 0,
    incumbent_avg_interval_coverage: optNumber(o.incumbent_avg_interval_coverage ?? o.incumbentAvgIntervalCoverage) ?? 0,
    mdape_improvement: optNumber(o.mdape_improvement ?? o.mdapeImprovement) ?? 0,
    coverage_delta: optNumber(o.coverage_delta ?? o.coverageDelta) ?? 0,
    coverage_floor_ok: typeof (o.coverage_floor_ok ?? o.coverageFloorOk) === 'boolean'
      ? (o.coverage_floor_ok ?? o.coverageFloorOk) as boolean
      : false,
  };
}

function normalizeMlRouteHotspot(raw: unknown): MlRouteHotspot {
  const o = asObject(raw);
  return {
    route: optString(o.route),
    avg_mdape: optNumber(o.avg_mdape ?? o.avgMdape),
    avg_interval_coverage: optNumber(o.avg_interval_coverage ?? o.avgIntervalCoverage),
    sample_count: optNumber(o.sample_count ?? o.sampleCount),
    anomaly: typeof (o.anomaly) === 'boolean' ? o.anomaly as boolean : null,
    ...o,
  };
}

function normalizeMlAnalytics(payload: unknown): MlAnalytics {
  const root = asObject(payload);
  const s = asObject(root.status);
  const rawHotspots = Array.isArray(s.route_hotspots ?? s.routeHotspots)
    ? (s.route_hotspots ?? s.routeHotspots) as unknown[]
    : [];
  const rawPolicy = s.promotion_policy ?? s.promotionPolicy;
  const rawWarmup = s.warmup;

  return {
    status: {
      league: optString(s.league) ?? '',
      run: optString(s.run ?? s.runId ?? s.run_id) ?? '',
      status: optString(s.status) ?? 'unknown',
      promotion_verdict: optString(s.promotion_verdict ?? s.promotionVerdict) ?? '',
      stop_reason: optString(s.stop_reason ?? s.stopReason) ?? '',
      active_model_version: optString(s.active_model_version ?? s.activeModelVersion),
      latest_avg_mdape: optNumber(s.latest_avg_mdape ?? s.latestAvgMdape) ?? 0,
      latest_avg_interval_coverage: optNumber(s.latest_avg_interval_coverage ?? s.latestAvgIntervalCoverage) ?? 0,
      candidate_vs_incumbent: normalizeMlCandidateComparison(s.candidate_vs_incumbent ?? s.candidateVsIncumbent),
      route_hotspots: rawHotspots.map(normalizeMlRouteHotspot),
      promotion_policy: rawPolicy && typeof rawPolicy === 'object' ? {
        mdape_ceiling: optNumber((rawPolicy as Record<string, unknown>).mdape_ceiling ?? (rawPolicy as Record<string, unknown>).mdapeCeiling),
        coverage_floor: optNumber((rawPolicy as Record<string, unknown>).coverage_floor ?? (rawPolicy as Record<string, unknown>).coverageFloor),
        min_rows: optNumber((rawPolicy as Record<string, unknown>).min_rows ?? (rawPolicy as Record<string, unknown>).minRows),
        ...(rawPolicy as Record<string, unknown>),
      } : null,
      warmup: rawWarmup && typeof rawWarmup === 'object' ? {
        status: optString((rawWarmup as Record<string, unknown>).status) ?? '',
        message: optString((rawWarmup as Record<string, unknown>).message),
        runs_needed: optNumber((rawWarmup as Record<string, unknown>).runs_needed ?? (rawWarmup as Record<string, unknown>).runsNeeded),
        runs_completed: optNumber((rawWarmup as Record<string, unknown>).runs_completed ?? (rawWarmup as Record<string, unknown>).runsCompleted),
        ...(rawWarmup as Record<string, unknown>),
      } : null,
    },
  };
}

export async function getAnalyticsMl() {
  const raw = await request<unknown>('/api/v1/ops/analytics/ml');
  return normalizeMlAnalytics(raw);
}

export async function getAnalyticsReport() {
  return request<ReportAnalytics>('/api/v1/ops/analytics/report');
}


function normalizeMlPredictOneResponse(payload: unknown): MlPredictOneResponse {
  const source = (payload && typeof payload === 'object') ? payload as Record<string, unknown> : {};
  const intervalSource = (source.interval && typeof source.interval === 'object')
    ? source.interval as Record<string, unknown>
    : {};
  const p10 = typeof intervalSource.p10 === 'number'
    ? intervalSource.p10
    : (typeof source.price_p10 === 'number' ? source.price_p10 : null);
  const p90 = typeof intervalSource.p90 === 'number'
    ? intervalSource.p90
    : (typeof source.price_p90 === 'number' ? source.price_p90 : null);
  return {
    predictedValue: typeof source.predictedValue === 'number'
      ? source.predictedValue
      : (typeof source.price_p50 === 'number' ? source.price_p50 : 0),
    currency: typeof source.currency === 'string' && source.currency.trim() ? source.currency : 'chaos',
    confidence: typeof source.confidence === 'number'
      ? source.confidence
      : (typeof source.confidence_percent === 'number' ? source.confidence_percent : 0),
    interval: { p10, p90 },
    saleProbabilityPercent: typeof source.saleProbabilityPercent === 'number'
      ? source.saleProbabilityPercent
      : (typeof source.sale_probability_percent === 'number' ? source.sale_probability_percent : null),
    priceRecommendationEligible: typeof source.priceRecommendationEligible === 'boolean'
      ? source.priceRecommendationEligible
      : Boolean(source.price_recommendation_eligible),
    fallbackReason: typeof source.fallbackReason === 'string'
      ? source.fallbackReason
      : (typeof source.fallback_reason === 'string' ? source.fallback_reason : ''),
  };
}

function buildQueryString(params: Record<string, string | number | undefined>): string {
  const entries = Object.entries(params).filter(([, v]) => v !== undefined && v !== '');
  if (entries.length === 0) return '';
  return '?' + entries.map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`).join('&');
}

export async function getAnalyticsSearchSuggestions(query: string) {
  const queryString = buildQueryString({ query });
  return request<SearchSuggestionsResponse>(`/api/v1/ops/analytics/search-suggestions${queryString}`);
}

export async function getAnalyticsSearchHistory(params: SearchHistoryRequest) {
  const queryString = buildQueryString({
    query: params.query,
    league: params.league,
    sort: params.sort,
    order: params.order,
    price_min: params.priceMin,
    price_max: params.priceMax,
    time_from: params.timeFrom,
    time_to: params.timeTo,
    limit: params.limit,
  });
  return request<SearchHistoryResponse>(`/api/v1/ops/analytics/search-history${queryString}`);
}

export async function getAnalyticsPricingOutliers(params: PricingOutliersRequest = {}) {
  const queryString = buildQueryString({
    query: params.query,
    league: params.league,
    sort: params.sort,
    order: params.order,
    min_total: params.minTotal,
    limit: params.limit,
  });
  return request<PricingOutliersResponse>(`/api/v1/ops/analytics/pricing-outliers${queryString}`);
}


function asObject(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' ? value as Record<string, unknown> : {};
}

function optString(value: unknown): string | null {
  return typeof value === 'string' && value.trim() ? value : null;
}

function optNumber(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

function normalizeMlAutomationStatus(payload: unknown): MlAutomationStatus {
  const source = asObject(payload);
  const latest = asObject(source.latestRun);
  const hasLatest = Object.keys(latest).length > 0;
  return {
    league: optString(source.league) ?? 'Mirage',
    status: optString(source.status),
    activeModelVersion: optString(source.activeModelVersion ?? source.active_model_version),
    latestRun: hasLatest ? {
      runId: optString(latest.runId ?? latest.run_id),
      status: optString(latest.status),
      stopReason: optString(latest.stopReason ?? latest.stop_reason),
      updatedAt: optString(latest.updatedAt ?? latest.updated_at),
    } : null,
    promotionVerdict: optString(source.promotionVerdict ?? source.promotion_verdict),
    routeHotspots: Array.isArray(source.routeHotspots ?? source.route_hotspots)
      ? (source.routeHotspots ?? source.route_hotspots) as unknown[]
      : [],
  };
}

function normalizeMlAutomationHistory(payload: unknown): MlAutomationHistory {
  const source = asObject(payload);
  const historyRows = Array.isArray(source.history) ? source.history : [];
  const summary = asObject(source.summary);
  const qualityTrend = Array.isArray(source.qualityTrend) ? source.qualityTrend : [];
  const trainingCadence = Array.isArray(source.trainingCadence) ? source.trainingCadence : [];
  const routeMetrics = Array.isArray(source.routeMetrics) ? source.routeMetrics : [];
  const datasetCoverage = asObject(source.datasetCoverage);
  const promotions = Array.isArray(source.promotions) ? source.promotions : [];
  return {
    league: optString(source.league) ?? 'Mirage',
    history: historyRows.map((entry) => {
      const row = asObject(entry);
      return {
        runId: optString(row.runId ?? row.run_id),
        status: optString(row.status),
        stopReason: optString(row.stopReason ?? row.stop_reason),
        activeModelVersion: optString(row.activeModelVersion ?? row.active_model_version),
        tuningConfigId: optString(row.tuningConfigId ?? row.tuning_config_id),
        evalRunId: optString(row.evalRunId ?? row.eval_run_id),
        updatedAt: optString(row.updatedAt ?? row.updated_at),
        rowsProcessed: optNumber(row.rowsProcessed ?? row.rows_processed),
        avgMdape: optNumber(row.avgMdape ?? row.avg_mdape),
        avgIntervalCoverage: optNumber(row.avgIntervalCoverage ?? row.avg_interval_coverage),
        verdict: optString(row.verdict),
      };
    }),
    summary: {
      activeModelVersion: optString(summary.activeModelVersion ?? summary.active_model_version),
      lastRunAt: optString(summary.lastRunAt ?? summary.last_run_at),
      lastPromotedAt: optString(summary.lastPromotedAt ?? summary.last_promoted_at),
      runsLast7d: optNumber(summary.runsLast7d ?? summary.runs_last_7d) ?? 0,
      runsLast30d: optNumber(summary.runsLast30d ?? summary.runs_last_30d) ?? 0,
      medianHoursBetweenRuns: optNumber(summary.medianHoursBetweenRuns ?? summary.median_hours_between_runs),
      latestAvgMdape: optNumber(summary.latestAvgMdape ?? summary.latest_avg_mdape),
      latestAvgIntervalCoverage: optNumber(summary.latestAvgIntervalCoverage ?? summary.latest_avg_interval_coverage),
      bestAvgMdape: optNumber(summary.bestAvgMdape ?? summary.best_avg_mdape),
      mdapeDeltaVsPrevious: optNumber(summary.mdapeDeltaVsPrevious ?? summary.mdape_delta_vs_previous),
      trendDirection: optString(summary.trendDirection ?? summary.trend_direction) ?? 'unknown',
    },
    qualityTrend: qualityTrend.map((entry) => {
      const row = asObject(entry);
      return {
        runId: optString(row.runId ?? row.run_id),
        updatedAt: optString(row.updatedAt ?? row.updated_at),
        avgMdape: optNumber(row.avgMdape ?? row.avg_mdape),
        avgIntervalCoverage: optNumber(row.avgIntervalCoverage ?? row.avg_interval_coverage),
        verdict: optString(row.verdict),
        activeModelVersion: optString(row.activeModelVersion ?? row.active_model_version),
      };
    }),
    trainingCadence: trainingCadence.map((entry) => {
      const row = asObject(entry);
      return {
        date: optString(row.date) ?? '',
        runs: optNumber(row.runs) ?? 0,
      };
    }),
    routeMetrics: routeMetrics.map((entry) => {
      const row = asObject(entry);
      return {
        route: optString(row.route),
        sampleCount: optNumber(row.sampleCount ?? row.sample_count),
        avgMdape: optNumber(row.avgMdape ?? row.avg_mdape),
        avgIntervalCoverage: optNumber(row.avgIntervalCoverage ?? row.avg_interval_coverage),
        avgAbstainRate: optNumber(row.avgAbstainRate ?? row.avg_abstain_rate),
        recordedAt: optString(row.recordedAt ?? row.recorded_at),
      };
    }),
    datasetCoverage: {
      totalRows: optNumber(datasetCoverage.totalRows ?? datasetCoverage.total_rows) ?? 0,
      supportedRows: optNumber(datasetCoverage.supportedRows ?? datasetCoverage.supported_rows) ?? 0,
      coverageRatio: optNumber(datasetCoverage.coverageRatio ?? datasetCoverage.coverage_ratio) ?? 0,
      baseTypeCount: optNumber(datasetCoverage.baseTypeCount ?? datasetCoverage.base_type_count),
      routes: Array.isArray(datasetCoverage.routes) ? datasetCoverage.routes.map((entry) => {
        const row = asObject(entry);
        return {
          route: optString(row.route),
          rows: optNumber(row.rows) ?? 0,
          share: optNumber(row.share) ?? 0,
        };
      }) : [],
    },
    promotions: promotions.map((entry) => {
      const row = asObject(entry);
      return {
        modelVersion: optString(row.modelVersion ?? row.model_version),
        promotedAt: optString(row.promotedAt ?? row.promoted_at),
      };
    }),
  };
}


export const api: ApiService = {
  async getDashboard() {
    return request<DashboardResponse>('/api/v1/ops/dashboard');
  },

  async getScannerSummary() {
    return request<ScannerSummary>('/api/v1/ops/scanner/summary');
  },

  async getScannerRecommendations(requestParams?: ScannerRecommendationsRequest) {
    const query = new URLSearchParams();
    if (requestParams?.sort) {
      query.set('sort', requestParams.sort);
    }
    if (requestParams?.limit !== undefined) {
      query.set('limit', String(requestParams.limit));
    }
    if (requestParams?.cursor !== undefined) {
      query.set('cursor', requestParams.cursor);
    }
    if (requestParams?.league) {
      query.set('league', requestParams.league);
    }
    if (requestParams?.strategyId !== undefined) {
      query.set('strategy_id', requestParams.strategyId);
    }
    if (requestParams?.minConfidence !== undefined) {
      const normalizedConfidence = requestParams.minConfidence > 1
        ? requestParams.minConfidence / 100
        : requestParams.minConfidence;
      query.set('min_confidence', String(normalizedConfidence));
    }
    const queryString = query.toString();
    const path = queryString
      ? `/api/v1/ops/scanner/recommendations?${queryString}`
      : '/api/v1/ops/scanner/recommendations';
    return request<ScannerRecommendationsResponse>(path);
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
    const payload = await request<Record<string, unknown>>(`/api/v1/ml/leagues/${encodeURIComponent(league)}/automation/status`);
    return normalizeMlAutomationStatus(payload);
  },

  async getMlAutomationHistory() {
    const league = await primaryLeague();
    const payload = await request<Record<string, unknown>>(`/api/v1/ml/leagues/${encodeURIComponent(league)}/automation/history`);
    return normalizeMlAutomationHistory(payload);
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

  async mlPredictOne(req) {
    const league = await primaryLeague();
    const payload = await request<Record<string, unknown>>(`/api/v1/ml/leagues/${encodeURIComponent(league)}/predict-one`, {
      method: 'POST',
      body: JSON.stringify({
        input_format: 'poe-clipboard',
        payload: req.clipboard,
        output_mode: 'json',
      }),
    });
    return normalizeMlPredictOneResponse(payload);
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
