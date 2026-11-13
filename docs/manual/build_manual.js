// Seacrest Racer - Copyright 2026 Fernand G. / PlayableFX.com
// Licensed under the PolyForm Noncommercial License 1.0.0 (see LICENSE.md and NOTICE).
//
// Prints docs/manual/manual.html to seacrest_game-manual.pdf with headless Chromium.
//   npm i playwright @fontsource/racing-sans-one @fontsource/russo-one @fontsource/ibm-plex-sans @fontsource/ibm-plex-mono
//   node docs/manual/build_manual.js
const { chromium } = require('playwright');
const fs = require('fs'), path = require('path');
const here = __dirname, root = path.resolve(here, '../..');
const fontsrc = path.join(process.env.FONTSOURCE || path.join(root, 'node_modules', '@fontsource'));
const need = ['racing-sans-one/files/racing-sans-one-latin-400-normal.woff2', 'russo-one/files/russo-one-latin-400-normal.woff2',
  'ibm-plex-sans/files/ibm-plex-sans-latin-400-normal.woff2', 'ibm-plex-sans/files/ibm-plex-sans-latin-600-normal.woff2',
  'ibm-plex-sans/files/ibm-plex-sans-latin-400-italic.woff2', 'ibm-plex-mono/files/ibm-plex-mono-latin-500-normal.woff2'];
fs.mkdirSync(path.join(here, 'fonts'), { recursive: true });
for (const f of need) fs.copyFileSync(path.join(fontsrc, f), path.join(here, 'fonts', path.basename(f)));
(async () => {
  const maps = JSON.parse(fs.readFileSync(path.join(here, 'maps.json'), 'utf8'));
  const b = await chromium.launch();
  const p = await b.newPage();
  await p.addInitScript(m => { window.MAPS = m; }, maps);
  await p.goto('file://' + path.join(here, 'manual.html'));
  await p.evaluate(() => document.fonts.ready);
  await p.waitForTimeout(300);
  const out = path.join(root, 'seacrest_game-manual.pdf');
  await p.pdf({ path: out, preferCSSPageSize: true, printBackground: true });
  console.log('wrote', out);
  await b.close();
})();
