import { mkdir, writeFile } from 'node:fs/promises';
import { dirname } from 'node:path';
import type { Page } from '@playwright/test';

export async function writeEvidence(page: Page, basePath: string): Promise<void> {
  await mkdir(dirname(basePath), { recursive: true });
  const html = await page.content();
  await writeFile(`${basePath}.html`, html, 'utf-8');
  await page.screenshot({ path: `${basePath}.png`, fullPage: true });
}
