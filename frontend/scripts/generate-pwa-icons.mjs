import { readFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import { chromium } from '@playwright/test';

const root = resolve(import.meta.dirname, '..');
const svg = await readFile(resolve(root, 'public/icons/vinance-app-icon.svg'));
const dataUrl = `data:image/svg+xml;base64,${svg.toString('base64')}`;
const outputs = [
  [192, 'icon-192.png'],
  [512, 'icon-512.png'],
  [512, 'icon-maskable-512.png'],
  [180, 'apple-touch-icon.png'],
];

const browser = await chromium.launch({ headless: true });
for (const [size, filename] of outputs) {
  const page = await browser.newPage({ viewport: { width: size, height: size }, deviceScaleFactor: 1 });
  await page.setContent(`<style>html,body{margin:0;width:${size}px;height:${size}px;overflow:hidden}img{display:block;width:100%;height:100%}</style><img alt="" src="${dataUrl}">`);
  await page.screenshot({ path: resolve(root, `public/icons/${filename}`), type: 'png' });
  await page.close();
}
await browser.close();
