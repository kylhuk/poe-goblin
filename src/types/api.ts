// ========== Service Management ==========
export type ServiceStatus = 'running' | 'stopped' | 'error' | 'starting' | 'stopping';

export interface Service {
  id: string;
  name: string;
  description: string;
  status: ServiceStatus;
  uptime: number | null; // seconds
  lastCrawl: string | null; // ISO timestamp
  rowsInDb: number | null;
  containerInfo: string | null;
  type: 'crawler' | 'analytics' | 'docker' | 'worker';
  allowedActions?: Array<'start' | 'stop' | 'restart'>;
}

// ========== Analytics: FairValueEngine ==========
export interface SparklinePoint {
  time: string;
  value: number;
}

export interface FairValueItem {
  id: string;
  itemName: string;
  fairValue: number;
  publicStashFloor: number;
  exchangeImpliedMid: number;
  sparkline: SparklinePoint[];
  spread: number;
  liquidity: 'high' | 'medium' | 'low';
  confidence: number; // 0-100
  updatedAt: string;
}

// ========== Analytics: StaleListingArb ==========
export interface StaleListingOpp {
  id: string;
  itemName: string;
  askPrice: number;
  fairValue: number;
  discountPct: number;
  firstSeen: string;
  repricingCount: number;
  sellerDormancyScore: number; // 0-100
  expectedNetMargin: number;
  expectedSaleTime: string; // e.g. "~12 min"
  route: 'exchange unwind' | 'public relist';
  grade: 'green' | 'yellow' | 'red';
}

// ========== Analytics: GemValueModel ==========
export interface GemState {
  id: string;
  gemName: string;
  level: number;
  quality: number;
  corrupted: boolean;
  vaalState: string | null;
  imbuedOutcome: string | null;
  supportPoolSize: number;
  currentAsk: number;
  modelFairValue: number;
  anomalyScore: number; // 0-100
  comparables: { state: string; price: number }[];
  updatedAt: string;
}

// ========== Analytics: HeistRouter ==========
export type HeistBin = 'sell fast' | 'premium bin' | 'run' | 'ignore';
export interface HeistDrop {
  id: string;
  itemName: string;
  itemClass: string;
  bin: HeistBin;
  estimatedValueBand: string;
  reason: string;
}

// ========== Analytics: ShipmentOptimizer ==========
export interface ShipmentRecommendation {
  chosenPort: string;
  resourceMix: Record<string, number>;
  dustToAdd: number;
  expectedValue: number;
  expectedValuePerHour: number;
  expectedRiskLoss: number;
  whyThisWon: string;
  updatedAt: string;
}

// ========== Analytics: GoldShadowPrice ==========
export interface GoldShadowData {
  chaosPerGold: number;
  feeInChaos: number;
  denominationHint: string;
  updatedAt: string;
}

// ========== Analytics: SessionController ==========
export type ActivityType = 'map' | 'delve' | 'trade batch' | 'shipment prep';
export interface SessionRecommendation {
  recommended: ActivityType;
  triggerReason: string;
  updatedAt: string;
}

// ========== Analytics: GearSwapSimulator ==========
export interface CharacterStats {
  fireRes: number;
  coldRes: number;
  lightningRes: number;
  chaosRes: number;
  spellSuppression: number;
  life: number;
  str: number;
  dex: number;
  int: number;
  evasionMasteryActive: boolean;
  auraFit: boolean;
}

export interface GearSwapResult {
  current: CharacterStats;
  simulated: CharacterStats;
  failStates: string[];
  passStates: string[];
}

// ========== Price Check ==========
export interface PriceCheckRequest {
  itemText: string;
}

export interface PriceCheckResponse {
  predictedValue: number;
  currency: string;
  confidence: number;
  comparables: { name: string; price: number; currency: string }[];
  interval?: { p10: number | null; p90: number | null };
  saleProbabilityPercent?: number | null;
  priceRecommendationEligible?: boolean;
  fallbackReason?: string;
}

// ========== Stash Viewer ==========
export type PriceEvaluation = 'well_priced' | 'could_be_better' | 'mispriced';
export interface StashItem {
  id: string;
  name: string;
  x: number;
  y: number;
  w: number;
  h: number;
  itemClass?: string;
  rarity: 'normal' | 'magic' | 'rare' | 'unique';
  listedPrice: number | null;
  estimatedPrice: number;
  estimatedPriceConfidence: number; // 0-100
  priceDeltaChaos: number;
  priceDeltaPercent: number;
  priceEvaluation: PriceEvaluation;
  currency: string;
  iconUrl?: string;
}

export interface StashTab {
  id: string;
  name: string;
  type: 'normal' | 'quad' | 'currency' | 'map';
  items: StashItem[];
}

export interface StashStatus {
  status: 'connected_populated' | 'connected_empty' | 'disconnected' | 'session_expired' | 'feature_unavailable';
  connected: boolean;
  tabCount: number;
  itemCount: number;
  session: { accountName: string; expiresAt: string } | null;
}

export interface ScannerSummary {
  status: 'ok' | 'empty';
  lastRunAt: string | null;
  recommendationCount: number;
}

export interface ScannerRecommendation {
  scannerRunId: string;
  strategyId: string;
  league: string;
  itemOrMarketKey: string;
  whyItFired: string;
  buyPlan: string;
  maxBuy: number | null;
  transformPlan: string;
  exitPlan: string;
  executionVenue: string;
  expectedProfitChaos: number | null;
  expectedRoi: number | null;
  expectedHoldTime: string;
  confidence: number | null;
  recordedAt: string | null;
}

// ========== Messages ==========
export type MessageSeverity = 'info' | 'warning' | 'critical';
export interface AppMessage {
  id: string;
  timestamp: string;
  severity: MessageSeverity;
  sourceModule: string;
  message: string;
  suggestedAction: string;
}

// ========== API Service Interface ==========
export interface ApiService {
  getScannerSummary(): Promise<ScannerSummary>;
  getScannerRecommendations(): Promise<ScannerRecommendation[]>;
  ackAlert(alertId: string): Promise<void>;
  getStashStatus(): Promise<StashStatus>;
  getMlAutomationStatus(): Promise<Record<string, unknown>>;
  getMlAutomationHistory(): Promise<Record<string, unknown>>;

  getServices(): Promise<Service[]>;
  startService(id: string): Promise<void>;
  stopService(id: string): Promise<void>;
  restartService(id: string): Promise<void>;

  getFairValueItems(): Promise<FairValueItem[]>;
  getStaleListings(): Promise<StaleListingOpp[]>;
  getGemStates(): Promise<GemState[]>;
  getHeistDrops(): Promise<HeistDrop[]>;
  getShipmentRecommendation(): Promise<ShipmentRecommendation>;
  getGoldShadowPrice(): Promise<GoldShadowData>;
  getSessionRecommendation(): Promise<SessionRecommendation>;
  simulateGearSwap(candidateItem: string): Promise<GearSwapResult>;

  priceCheck(req: PriceCheckRequest): Promise<PriceCheckResponse>;

  getStashTabs(): Promise<StashTab[]>;
  getMessages(): Promise<AppMessage[]>;
}
