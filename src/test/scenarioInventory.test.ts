import { describe, expect, test } from 'vitest';
import inventory from './scenario-inventory.json';

describe('scenario inventory contract', () => {
  test('every scenario id is unique and has deterministic artifact path', () => {
    const ids = inventory.scenarios.map((row) => row.id);
    expect(new Set(ids).size).toBe(ids.length);
    for (const row of inventory.scenarios) {
      expect(row.id).toMatch(/^[a-z0-9-]+$/);
      expect(row.artifact.startsWith('.sisyphus/evidence/product/task-2-scenario-inventory/')).toBe(true);
    }
  });

  test('classification values stay in approved set', () => {
    const allowed = new Set([
      'route-backed',
      'automation-backed',
      'derived',
      'local-only',
      'qa-seeded',
    ]);
    for (const row of inventory.scenarios) {
      expect(allowed.has(row.classification)).toBe(true);
    }
  });
});
