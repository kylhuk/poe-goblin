import type {
  Service, FairValueItem, StaleListingOpp, GemState, HeistDrop,
  ShipmentRecommendation, GoldShadowData, SessionRecommendation,
  GearSwapResult, PriceCheckRequest, PriceCheckResponse, StashTab, AppMessage, ApiService
} from '@/types/api';
import {
  mockServices, mockFairValues, mockStaleListings, mockGemStates, mockHeistDrops,
  mockShipment, mockGoldShadow, mockSessionRec, mockGearSwapResult,
  mockPriceCheck, mockStashTabs, mockMessages
} from './mockData';

const delay = (ms = 300) => new Promise(r => setTimeout(r, ms));

// Replace this implementation with real API calls when backend is ready.
// Every method signature matches the ApiService interface.
export const api: ApiService = {
  async getServices() { await delay(); return [...mockServices]; },
  async startService(id) { await delay(500); },
  async stopService(id) { await delay(500); },
  async restartService(id) { await delay(800); },

  async getFairValueItems() { await delay(); return mockFairValues; },
  async getStaleListings() { await delay(); return mockStaleListings; },
  async getGemStates() { await delay(); return mockGemStates; },
  async getHeistDrops() { await delay(); return mockHeistDrops; },
  async getShipmentRecommendation() { await delay(); return mockShipment; },
  async getGoldShadowPrice() { await delay(); return mockGoldShadow; },
  async getSessionRecommendation() { await delay(); return mockSessionRec; },
  async simulateGearSwap(_candidateItem) { await delay(600); return mockGearSwapResult; },

  async priceCheck(_req) { await delay(800); return mockPriceCheck; },

  async getStashTabs() { await delay(); return mockStashTabs; },
  async getMessages() { await delay(); return mockMessages; },
};
