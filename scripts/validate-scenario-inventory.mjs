import { mkdir, readFile, writeFile } from 'node:fs/promises';

const inputPath = new URL('../src/test/scenario-inventory.json', import.meta.url);
const outPath = new URL('../../.sisyphus/evidence/product/task-2-scenario-inventory/inventory-validation.json', import.meta.url);

const raw = await readFile(inputPath, 'utf-8');
const inventory = JSON.parse(raw);
const scenarios = Array.isArray(inventory.scenarios) ? inventory.scenarios : [];
const ids = scenarios.map((row) => row.id);
const uniqueIds = new Set(ids);
const valid = ids.length > 0 && uniqueIds.size === ids.length;

await mkdir(new URL('../../.sisyphus/evidence/product/task-2-scenario-inventory/', import.meta.url), { recursive: true });
await writeFile(outPath, JSON.stringify({
  status: valid ? 'ok' : 'failed',
  total: ids.length,
  unique: uniqueIds.size,
}, null, 2));

if (!valid) {
  process.exit(1);
}
