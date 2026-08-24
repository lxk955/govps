import puppeteer from 'puppeteer-core';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const CHROME_PATH = '/home/kk/.agent-browser/browsers/chrome-151.0.7922.138/chrome';
const BASE_URL = process.env.BASE_URL || 'http://localhost:3000';
const OUTPUT_DIR = path.resolve(__dirname, '../docs/qa/p8/screenshots');

if (!fs.existsSync(OUTPUT_DIR)) {
  fs.mkdirSync(OUTPUT_DIR, { recursive: true });
}

const VIEWPORTS = [
  { name: 'mobile-375', width: 375, height: 667, isMobile: true },
  { name: 'mobile-390', width: 390, height: 844, isMobile: true },
  { name: 'mobile-430', width: 430, height: 932, isMobile: true },
  { name: 'tablet-768', width: 768, height: 1024, isMobile: false },
  { name: 'desktop-1024', width: 1024, height: 768, isMobile: false },
  { name: 'widescreen-1440', width: 1440, height: 900, isMobile: false },
];

const ROUTES = [
  { name: 'home', path: '/' },
  { name: 'vps-list', path: '/vps' },
  { name: 'vps-detail', path: '/vps/1' },
  { name: 'compare', path: '/compare?ids=1,2,3' },
  { name: 'deals', path: '/deals' },
  { name: 'providers', path: '/providers' },
  { name: 'login', path: '/login' },
  { name: 'ip', path: '/ip' },
];

async function run() {
  console.log(`Starting headless browser capture...`);
  console.log(`Base URL: ${BASE_URL}`);
  console.log(`Output Directory: ${OUTPUT_DIR}`);

  const browser = await puppeteer.launch({
    executablePath: CHROME_PATH,
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage', '--disable-gpu'],
  });

  const results = [];

  try {
    const page = await browser.newPage();

    for (const route of ROUTES) {
      console.log(`\nTesting Route: ${route.name} (${route.path})`);

      for (const vp of VIEWPORTS) {
        await page.setViewport({
          width: vp.width,
          height: vp.height,
          deviceScaleFactor: 1,
          isMobile: vp.isMobile,
        });

        const targetUrl = `${BASE_URL}${route.path}`;
        const filename = `${route.name}_${vp.width}px.png`;
        const filepath = path.join(OUTPUT_DIR, filename);

        try {
          const resp = await page.goto(targetUrl, {
            waitUntil: 'networkidle2',
            timeout: 15000,
          });

          // Measure overflow
          const metrics = await page.evaluate(() => {
            return {
              scrollWidth: document.documentElement.scrollWidth,
              clientWidth: document.documentElement.clientWidth,
              innerWidth: window.innerWidth,
              bodyScrollWidth: document.body.scrollWidth,
            };
          });

          const hasOverflow = metrics.scrollWidth > metrics.clientWidth + 1; // 1px tolerance for subpixel rounding

          await page.screenshot({
            path: filepath,
            fullPage: true,
          });

          const status = resp ? resp.status() : 'OK';
          console.log(
            `  [${vp.width}px] status=${status} width=${metrics.scrollWidth}/${metrics.clientWidth} overflow=${hasOverflow ? 'FAIL' : 'OK'} -> ${filename}`
          );

          results.push({
            route: route.name,
            path: route.path,
            viewport: `${vp.width}px (${vp.name})`,
            width: vp.width,
            status,
            overflow: hasOverflow,
            scrollWidth: metrics.scrollWidth,
            clientWidth: metrics.clientWidth,
            screenshot: filename,
          });
        } catch (err) {
          console.error(`  [${vp.width}px] Error loading ${targetUrl}:`, err.message);
          results.push({
            route: route.name,
            path: route.path,
            viewport: `${vp.width}px (${vp.name})`,
            width: vp.width,
            status: 'ERROR: ' + err.message,
            overflow: true,
            screenshot: null,
          });
        }
      }
    }
  } finally {
    await browser.close();
  }

  // Summary Report
  console.log('\n=== SUMMARY OF VIEWPORT AUDIT ===');
  const overflowFails = results.filter((r) => r.overflow);
  console.log(`Total Captures: ${results.length}`);
  console.log(`Overflow Failures: ${overflowFails.length}`);

  if (overflowFails.length > 0) {
    console.error('FAILED OVERFLOW CHECKS:');
    overflowFails.forEach((f) => console.error(`  - ${f.route} @ ${f.viewport}: ${f.scrollWidth}px > ${f.clientWidth}px`));
  } else {
    console.log('ALL 48 VIEWPORT COMBINATIONS PASSED ZERO-OVERFLOW AUDIT!');
  }

  fs.writeFileSync(
    path.join(OUTPUT_DIR, 'audit-results.json'),
    JSON.stringify({ timestamp: new Date().toISOString(), total: results.length, overflowFails: overflowFails.length, results }, null, 2)
  );
}

run().catch((err) => {
  console.error('Fatal error in screenshot runner:', err);
  process.exit(1);
});
