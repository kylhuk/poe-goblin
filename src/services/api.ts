import type {
  ApiService,
  AppMessage,
  DashboardResponse,
  HealthResponse,
  MlAutomationHistory,
  MlAutomationObservability,
  MlAutomationStatus,
  MlContractResponse,
  MlLeagueStatusResponse,
  MlPredictOneRequest,
  MlPredictOneResponse,
  PriceCheckRequest,
  PriceCheckResponse,
  PricingOutliersQuery,
  PricingOutliersQueryPayload,
  PricingOutliersRequest,
  PricingOutliersResponse,
  ScannerRecommendationsRequest,
  ScannerRecommendationsResponse,
  ScannerSummary,
  SearchHistoryRequest,
  SearchHistoryResponse,
  SearchSuggestionsResponse,
  Service,
  StashItemHistoryResponse,
  StashScanStartResponse,
  StashScanStatus,
  StashStatus,
  StashTabsResponse,
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
  enabled?: boolean;
  accepted_count?: number;
  rejected_count?: number;
  candidate_count?: number;
  top_rejection_reason?: string | null;
}

export interface ScannerAnalyticsResponse {
  latestRunId?: string | null;
  rows: ScannerRow[];
  gateRejections?: Array<{ decision_reason: string; rejection_count: number }>;
  complexityTiers?: Array<{ complexity_tier: string; tier_count: number }>;
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
  route_decisions: unknown[];
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
    const rawMessage = err instanceof Error ? err.message : 'Network error';
    const detail = `${method} ${path}: ${rawMessage}`;
    logApiError({ method, path, errorCode: 'network_error', message: rawMessage });
    throw new Error(detail);
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
  return request<ScannerAnalyticsResponse>('/api/v1/ops/analytics/scanner');
}

export async function getAnalyticsAlerts() {
  const payload = await request<{ rows: AlertRow[] }>('/api/v1/ops/analytics/alerts');
  return payload.rows;
}

export async function getAnalyticsBacktests() {
  return request<BacktestAnalytics>('/api/v1/ops/analytics/backtests');
}

export interface OpportunitiesAnalytics {
  [key: string]: unknown;
}

export async function getAnalyticsOpportunities(): Promise<OpportunitiesAnalytics> {
  return request<OpportunitiesAnalytics>('/api/v1/ops/analytics/opportunities');
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

  const rawRouteDecisions = Array.isArray(s.route_decisions ?? s.routeDecisions)
    ? (s.route_decisions ?? s.routeDecisions) as unknown[]
    : [];

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
      route_decisions: rawRouteDecisions,
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
  const raw = await request<Record<string, unknown>>('/api/v1/ops/analytics/report');
  return normalizeReportAnalytics(raw);
}

function normalizeGoldDiagnostics(raw: unknown): GoldDiagnosticsResponse | null {
  const o = asObject(raw);
  if (Object.keys(o).length === 0) return null;
  const summary = asObject(o.summary);
  const marts = Array.isArray(o.marts) ? o.marts : [];
  return {
    league: optString(o.league) ?? '',
    summary: {
      status: optString(summary.status) ?? 'unknown',
      martCount: optNumber(summary.martCount ?? summary.mart_count) ?? 0,
      problemMarts: optNumber(summary.problemMarts ?? summary.problem_marts) ?? 0,
      goldEmptyMarts: optNumber(summary.goldEmptyMarts ?? summary.gold_empty_marts) ?? 0,
      staleMarts: optNumber(summary.staleMarts ?? summary.stale_marts) ?? 0,
      missingLeagueMarts: optNumber(summary.missingLeagueMarts ?? summary.missing_league_marts) ?? 0,
    },
    marts: marts.map((entry) => {
      const m = asObject(entry);
      return {
        martName: optString(m.martName ?? m.mart_name) ?? 'unknown',
        sourceName: optString(m.sourceName ?? m.source_name),
        diagnosticState: optString(m.diagnosticState ?? m.diagnostic_state) ?? 'unknown',
        sourceRowCount: optNumber(m.sourceRowCount ?? m.source_row_count) ?? 0,
        goldRowCount: optNumber(m.goldRowCount ?? m.gold_row_count) ?? 0,
        sourceLatestAt: optString(m.sourceLatestAt ?? m.source_latest_at),
        goldLatestAt: optString(m.goldLatestAt ?? m.gold_latest_at),
        goldFreshnessMinutes: optNumber(m.goldFreshnessMinutes ?? m.gold_freshness_minutes),
        sourceToGoldLagMinutes: optNumber(m.sourceToGoldLagMinutes ?? m.source_to_gold_lag_minutes),
        leagueVisibility: optString(m.leagueVisibility ?? m.league_visibility),
        sourceLeagueRows: optNumber(m.sourceLeagueRows ?? m.source_league_rows),
        goldLeagueRows: optNumber(m.goldLeagueRows ?? m.gold_league_rows),
      };
    }),
  };
}

function normalizeReportAnalytics(raw: unknown): ReportAnalytics {
  const o = asObject(raw);
  const report = asObject(o.report);
  return {
    status: optString(o.status) ?? 'unknown',
    report: {
      league: optString(report.league) ?? '',
      recommendations: optNumber(report.recommendations) ?? 0,
      alerts: optNumber(report.alerts) ?? 0,
      journal_events: optNumber(report.journal_events ?? report.journalEvents) ?? 0,
      journal_positions: optNumber(report.journal_positions ?? report.journalPositions) ?? 0,
      backtest_summary_rows: optNumber(report.backtest_summary_rows ?? report.backtestSummaryRows) ?? 0,
      backtest_detail_rows: optNumber(report.backtest_detail_rows ?? report.backtestDetailRows) ?? 0,
      gold_currency_ref_hour_rows: optNumber(report.gold_currency_ref_hour_rows ?? report.goldCurrencyRefHourRows) ?? 0,
      gold_listing_ref_hour_rows: optNumber(report.gold_listing_ref_hour_rows ?? report.goldListingRefHourRows) ?? 0,
      gold_liquidity_ref_hour_rows: optNumber(report.gold_liquidity_ref_hour_rows ?? report.goldLiquidityRefHourRows) ?? 0,
      gold_bulk_premium_hour_rows: optNumber(report.gold_bulk_premium_hour_rows ?? report.goldBulkPremiumHourRows) ?? 0,
      gold_set_ref_hour_rows: optNumber(report.gold_set_ref_hour_rows ?? report.goldSetRefHourRows) ?? 0,
      realized_pnl_chaos: optNumber(report.realized_pnl_chaos ?? report.realizedPnlChaos) ?? 0,
    },
    goldDiagnostics: normalizeGoldDiagnostics(o.goldDiagnostics ?? o.gold_diagnostics),
  };
}

function normalizeTrustFields(source: Record<string, unknown>) {
  return {
    mlPredicted: typeof (source.mlPredicted ?? source.ml_predicted) === 'boolean'
      ? (source.mlPredicted ?? source.ml_predicted) as boolean
      : undefined,
    predictionSource: optString(source.predictionSource ?? source.prediction_source) ?? undefined,
    estimateTrust: optString(source.estimateTrust ?? source.estimate_trust) ?? undefined,
    estimateWarning: optString(source.estimateWarning ?? source.estimate_warning) ?? null,
  };
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
    league: optString(source.league) ?? undefined,
    route: optString(source.route) ?? undefined,
    ...normalizeTrustFields(source),
  };
}

function normalizePriceCheckResponse(payload: unknown): PriceCheckResponse {
  const source = (payload && typeof payload === 'object') ? payload as Record<string, unknown> : {};
  const intervalSource = (source.interval && typeof source.interval === 'object')
    ? source.interval as Record<string, unknown>
    : {};
  const p10 = typeof intervalSource.p10 === 'number' ? intervalSource.p10 : null;
  const p90 = typeof intervalSource.p90 === 'number' ? intervalSource.p90 : null;
  const rawComparables = Array.isArray(source.comparables) ? source.comparables : [];

  return {
    predictedValue: typeof source.predictedValue === 'number' ? source.predictedValue : 0,
    currency: typeof source.currency === 'string' && source.currency.trim() ? source.currency : 'chaos',
    confidence: typeof source.confidence === 'number' ? source.confidence : 0,
    interval: { p10, p90 },
    comparables: rawComparables.map((c: unknown) => {
      const o = asObject(c);
      return {
        name: optString(o.name) ?? '',
        price: typeof o.price === 'number' ? o.price : 0,
        currency: optString(o.currency) ?? 'chaos',
        league: optString(o.league) ?? undefined,
        addedOn: optString(o.addedOn ?? o.added_on) ?? null,
      };
    }),
    saleProbabilityPercent: typeof source.saleProbabilityPercent === 'number'
      ? source.saleProbabilityPercent
      : (typeof source.sale_probability_percent === 'number' ? source.sale_probability_percent : null),
    priceRecommendationEligible: typeof source.priceRecommendationEligible === 'boolean'
      ? source.priceRecommendationEligible
      : Boolean(source.price_recommendation_eligible),
    fallbackReason: typeof source.fallbackReason === 'string'
      ? source.fallbackReason
      : (typeof source.fallback_reason === 'string' ? source.fallback_reason : ''),
    fairValueP50: optNumber(source.fairValueP50 ?? source.fair_value_p50),
    fastSale24hPrice: optNumber(source.fastSale24hPrice ?? source.fast_sale_24h_price),
    ...normalizeTrustFields(source),
  };
}

function buildQueryString(params: Record<string, string | number | undefined>): string {
  const entries = Object.entries(params).filter(([, v]) => v !== undefined && v !== '');
  if (entries.length === 0) return '';
  return '?' + entries.map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`).join('&');
}

function normalizePriceRange(source: Record<string, unknown>): { min: number; max: number } {
  return {
    min: optNumber(source.min) ?? 0,
    max: optNumber(source.max) ?? 0,
  };
}

function normalizeDatetimeRange(source: Record<string, unknown>): { min: string | null; max: string | null } {
  return {
    min: optString(source.min),
    max: optString(source.max),
  };
}

function normalizePriceBuckets(payload: unknown): SearchHistoryResponse['histograms']['price'] {
  const buckets = Array.isArray(payload) ? payload : [];
  return buckets.map((entry) => {
    const bucket = asObject(entry);
    return {
      bucketStart: optNumber(bucket.bucketStart ?? bucket.bucket_start) ?? 0,
      bucketEnd: optNumber(bucket.bucketEnd ?? bucket.bucket_end) ?? 0,
      count: optNumber(bucket.count) ?? 0,
    };
  });
}

function normalizeDatetimeBuckets(payload: unknown): SearchHistoryResponse['histograms']['datetime'] {
  const buckets = Array.isArray(payload) ? payload : [];
  return buckets.map((entry) => {
    const bucket = asObject(entry);
    return {
      bucketStart: optString(bucket.bucketStart ?? bucket.bucket_start) ?? '',
      bucketEnd: optString(bucket.bucketEnd ?? bucket.bucket_end) ?? '',
      count: optNumber(bucket.count) ?? 0,
    };
  });
}

function normalizeSearchHistoryRows(payload: unknown): SearchHistoryResponse['rows'] {
  const rows = Array.isArray(payload) ? payload : [];
  return rows.map((entry) => {
    const row = asObject(entry);
    return {
      itemName: optString(row.itemName ?? row.item_name) ?? '',
      league: optString(row.league) ?? '',
      listedPrice: optNumber(row.listedPrice ?? row.listed_price) ?? 0,
      currency: optString(row.currency) ?? 'chaos',
      addedOn: optString(row.addedOn ?? row.added_on) ?? '',
    };
  });
}

function normalizePricingOutlierRows(payload: unknown): PricingOutliersResponse['rows'] {
  const rows = Array.isArray(payload) ? payload : [];
  return rows.map((entry) => {
    const row = asObject(entry);
    return {
      itemName: optString(row.itemName ?? row.item_name) ?? '',
      affixAnalyzed: optString(row.affixAnalyzed ?? row.affix_analyzed),
      p10: optNumber(row.p10) ?? 0,
      median: optNumber(row.median) ?? 0,
      p90: optNumber(row.p90) ?? 0,
      itemsPerWeek: optNumber(row.itemsPerWeek ?? row.items_per_week) ?? 0,
      itemsTotal: optNumber(row.itemsTotal ?? row.items_total) ?? 0,
      analysisLevel: optString(row.analysisLevel ?? row.analysis_level) ?? 'item',
      entryPrice: optNumber(row.entryPrice ?? row.entry_price),
      expectedProfit: optNumber(row.expectedProfit ?? row.expected_profit),
      roi: optNumber(row.roi),
      underpricedRate: optNumber(row.underpricedRate ?? row.underpriced_rate),
    };
  });
}

function normalizePricingOutlierWeeks(payload: unknown): PricingOutliersResponse['weekly'] {
  const rows = Array.isArray(payload) ? payload : [];
  return rows.map((entry) => {
    const row = asObject(entry);
    return {
      weekStart: optString(row.weekStart ?? row.week_start) ?? '',
      tooCheapCount: optNumber(row.tooCheapCount ?? row.too_cheap_count) ?? 0,
    };
  });
}

function normalizeSearchHistoryResponse(payload: unknown): SearchHistoryResponse {
  const source = asObject(payload);
  const query = asObject(source.query);
  const filters = asObject(source.filters);
  const histograms = asObject(source.histograms);
  return {
    query: {
      text: optString(query.text ?? source.query) ?? '',
      league: optString(query.league ?? source.league) ?? '',
      sort: optString(query.sort ?? source.sort) ?? 'item_name',
      order: optString(query.order ?? source.order) === 'asc' ? 'asc' : 'desc',
    },
    filters: {
      leagueOptions: Array.isArray(filters.leagueOptions ?? filters.league_options)
        ? ((filters.leagueOptions ?? filters.league_options) as unknown[]).filter((value): value is string => typeof value === 'string')
        : [],
      price: normalizePriceRange(asObject(filters.price)),
      datetime: normalizeDatetimeRange(asObject(filters.datetime)),
    },
    histograms: {
      price: normalizePriceBuckets(histograms.price),
      datetime: normalizeDatetimeBuckets(histograms.datetime),
    },
    rows: normalizeSearchHistoryRows(source.rows),
  };
}

function normalizePricingOutliersResponse(payload: unknown): PricingOutliersResponse {
  const source = asObject(payload);
  const query = asObject(source.query) as PricingOutliersQueryPayload;
  const topLevelMaxBuyIn = optNumber(source.maxBuyIn ?? source.max_buy_in);
  const topLevelLimit = optNumber(source.limit);
  const normalizedQuery = {
    ...(optString(query.query) ? { query: optString(query.query) } : {}),
    ...(optString(query.league ?? source.league) ? { league: optString(query.league ?? source.league) } : {}),
    ...(optString(query.sort ?? source.sort) ? { sort: optString(query.sort ?? source.sort) } : {}),
    ...((query.order ?? source.order) === 'asc' || (query.order ?? source.order) === 'desc'
      ? { order: (query.order ?? source.order) as 'asc' | 'desc' }
      : {}),
    ...(optNumber(query.minTotal ?? query.min_total ?? source.minTotal ?? source.min_total) != null
      ? { minTotal: optNumber(query.minTotal ?? query.min_total ?? source.minTotal ?? source.min_total) as number }
      : {}),
    ...((optNumber(query.maxBuyIn ?? query.max_buy_in) ?? topLevelMaxBuyIn) != null
      ? { maxBuyIn: (optNumber(query.maxBuyIn ?? query.max_buy_in) ?? topLevelMaxBuyIn) as number }
      : {}),
    ...((optNumber(query.limit) ?? topLevelLimit) != null
      ? { limit: (optNumber(query.limit) ?? topLevelLimit) as number }
      : {}),
  } satisfies PricingOutliersQuery;
  return {
    query: normalizedQuery,
    rows: normalizePricingOutlierRows(source.rows),
    weekly: normalizePricingOutlierWeeks(source.weekly),
  };
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
  return normalizeSearchHistoryResponse(
    await request<unknown>(`/api/v1/ops/analytics/search-history${queryString}`)
  );
}

export async function getAnalyticsPricingOutliers(params: PricingOutliersRequest = {}) {
  const queryString = buildQueryString({
    query: params.query,
    league: params.league,
    sort: params.sort,
    order: params.order,
    min_total: params.minTotal,
    max_buy_in: params.maxBuyIn,
    limit: params.limit,
  });
  return normalizePricingOutliersResponse(
    await request<unknown>(`/api/v1/ops/analytics/pricing-outliers${queryString}`)
  );
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

function normalizeMlAutomationObservability(raw: unknown): MlAutomationObservability {
  const o = asObject(raw);
  return {
    datasetRows: optNumber(o.datasetRows ?? o.dataset_rows) ?? 0,
    latestTrainingAsOf: optString(o.latestTrainingAsOf ?? o.latest_training_as_of),
    promotedModels: optNumber(o.promotedModels ?? o.promoted_models) ?? 0,
    latestPromotionAt: optString(o.latestPromotionAt ?? o.latest_promotion_at),
    evalRuns: optNumber(o.evalRuns ?? o.eval_runs) ?? 0,
    evalSampleRows: optNumber(o.evalSampleRows ?? o.eval_sample_rows) ?? 0,
    latestEvalAt: optString(o.latestEvalAt ?? o.latest_eval_at),
    evaluationAvailable: typeof (o.evaluationAvailable ?? o.evaluation_available) === 'boolean'
      ? (o.evaluationAvailable ?? o.evaluation_available) as boolean
      : false,
  };
}

function normalizeMlAutomationStatus(payload: unknown): MlAutomationStatus {
  const source = asObject(payload);
  const latest = asObject(source.latestRun ?? source.latest_run);
  const hasLatest = Object.keys(latest).length > 0;
  const rawTrainerRuntime = source.trainerRuntime ?? source.trainer_runtime;
  let trainerRuntime: MlAutomationStatus['trainerRuntime'] = null;
  if (rawTrainerRuntime && typeof rawTrainerRuntime === 'object') {
    const tr = rawTrainerRuntime as Record<string, unknown>;
    trainerRuntime = {
      stage: optString(tr.stage),
      status: optString(tr.status),
      updatedAt: optString(tr.updatedAt ?? tr.updated_at),
      details: (tr.details && typeof tr.details === 'object') ? tr.details as Record<string, unknown> : {},
    };
  }
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
    observability: normalizeMlAutomationObservability(source.observability),
    trainerRuntime,
  };
}

function normalizeMlAutomationHistory(payload: unknown): MlAutomationHistory {
  const source = asObject(payload);
  const historyRows = Array.isArray(source.history) ? source.history : [];
  const summary = asObject(source.summary);
  const qualityTrend = Array.isArray(source.qualityTrend ?? source.quality_trend) ? (source.qualityTrend ?? source.quality_trend) as unknown[] : [];
  const trainingCadence = Array.isArray(source.trainingCadence ?? source.training_cadence) ? (source.trainingCadence ?? source.training_cadence) as unknown[] : [];
  const routeMetrics = Array.isArray(source.routeMetrics ?? source.route_metrics) ? (source.routeMetrics ?? source.route_metrics) as unknown[] : [];
  const datasetCoverage = asObject(source.datasetCoverage ?? source.dataset_coverage);
  const promotions = Array.isArray(source.promotions) ? source.promotions : [];
  return {
    league: optString(source.league) ?? 'Mirage',
    mode: optString(source.mode),
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
    observability: normalizeMlAutomationObservability(source.observability),
    charts: (() => {
      const rawCharts = source.charts;
      if (!rawCharts || typeof rawCharts !== 'object') return undefined;
      const c = rawCharts as Record<string, unknown>;
      return {
        mdapeHistory: Array.isArray(c.mdapeHistory ?? c.mdape_history)
          ? (c.mdapeHistory ?? c.mdape_history) as Record<string, unknown>[]
          : [],
        coverageHistory: Array.isArray(c.coverageHistory ?? c.coverage_history)
          ? (c.coverageHistory ?? c.coverage_history) as Record<string, unknown>[]
          : [],
      };
    })(),
  };
}


export const api: ApiService = {
  async getHealthz() {
    return request<HealthResponse>('/healthz');
  },

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

  async startStashScan() {
    const league = await primaryLeague();
    return request<StashScanStartResponse>(`/api/v1/stash/scan?league=${encodeURIComponent(league)}&realm=pc`, {
      method: 'POST',
    });
  },

  async getStashScanStatus() {
    const league = await primaryLeague();
    return request<StashScanStatus>(`/api/v1/stash/scan/status?league=${encodeURIComponent(league)}&realm=pc`);
  },

  async getStashItemHistory(fingerprint: string) {
    const league = await primaryLeague();
    return request<StashItemHistoryResponse>(
      `/api/v1/stash/items/${encodeURIComponent(fingerprint)}/history?league=${encodeURIComponent(league)}&realm=pc`
    );
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
  async getMlContract() {
    return request<MlContractResponse>('/api/v1/ml/contract');
  },

  async getMlLeagueStatus() {
    const league = await primaryLeague();
    return request<MlLeagueStatusResponse>(`/api/v1/ml/leagues/${encodeURIComponent(league)}/status`);
  },

  async priceCheck(req) {
    const league = await primaryLeague();
    const payload = await request<Record<string, unknown>>(`/api/v1/ops/leagues/${encodeURIComponent(league)}/price-check`, {
      method: 'POST',
      body: JSON.stringify({ itemText: req.itemText.trim() }),
    });
    return normalizePriceCheckResponse(payload);
  },

  async mlPredictOne(req) {
    const league = await primaryLeague();
    const payload = await request<Record<string, unknown>>(`/api/v1/ml/leagues/${encodeURIComponent(league)}/predict-one`, {
      method: 'POST',
      body: JSON.stringify({ itemText: req.itemText.trim() }),
    });
    return normalizeMlPredictOneResponse(payload);
  },

  async getStashTabs() {
    const league = await primaryLeague();
    const payload = await request<StashTabsResponse>(
      `/api/v1/stash/tabs?league=${encodeURIComponent(league)}&realm=pc`
    );
    return payload;
  },

  async getMessages() {
    const payload = await request<{ messages: AppMessage[] }>('/api/v1/ops/messages');
    return payload.messages;
  },
};
