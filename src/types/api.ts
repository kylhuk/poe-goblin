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
}

// ========== Stash Viewer ==========
export type PriceHealth = 'good' | 'ok' | 'bad';
export interface StashItem {
  id: string;
  name: string;
  x: number;
  y: number;
  w: number;
  h: number;
  estimatedValue: number;
  listedPrice: number | null;
  currency: string;
  priceHealth: PriceHealth;
  rarity: 'normal' | 'magic' | 'rare' | 'unique';
  iconUrl?: string;
}

export interface StashTab {
  id: string;
  name: string;
  type: 'normal' | 'quad' | 'currency' | 'map';
  items: StashItem[];
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
