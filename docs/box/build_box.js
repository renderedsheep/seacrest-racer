// Seacrest Racer - Copyright 2026 Fernand G. / PlayableFX.com
// Licensed under the PolyForm Noncommercial License 1.0.0 (see LICENSE.md and NOTICE).
//
// Prints the box cover (docs/box/box.html) to:
//   seacrest_box-cover.pdf   print-ready sheet with crop and fold marks
//   seacrest_box-cover.png   the insert alone with bleed, 300 dpi
// Measure the paper insert slot of your case and pass the sizes in millimetres:
//   node docs/box/build_box.js --height 211 --front 147 --spine 27
// Needs the fonts copied by docs/manual/build_manual.js (run that once first).
const { chromium } = require('playwright');
const path = require('path');
const here = __dirname, root = path.resolve(here, '../..');
const arg = (name, def) => { const i = process.argv.indexOf('--' + name); return i > 0 ? parseFloat(process.argv[i + 1]) : def; };
const H = arg('height', 211), F = arg('front', 147), S = arg('spine', 27), B = arg('bleed', 1.6);
const W = 2 * F + S;
// smallest common sheet (landscape) that holds the insert, bleed and room for marks
const sheets = [['Letter', 279.4, 215.9], ['Legal', 355.6, 215.9], ['Tabloid', 431.8, 279.4], ['Super B / 13x19', 482.6, 330.2]];
const need = [W + 2 * B + 24, H + 2 * B];   // marks go in the side margins; top/bottom marks only if there's room
const fit = sheets.find(([, w, h]) => w >= need[0] && h >= need[1]) || sheets[sheets.length - 1];
(async () => {
  const b = await chromium.launch();
  const p = await b.newPage({ deviceScaleFactor: 300 / 96 });
  await p.goto('file://' + path.join(here, 'box.html'));
  await p.evaluate(([H, F, S, B, PW, PH]) => {
    const r = document.documentElement.style;
    r.setProperty('--H', H + 'mm'); r.setProperty('--F', F + 'mm'); r.setProperty('--S', S + 'mm'); r.setProperty('--B', B + 'mm');
    r.setProperty('--PW', PW + 'mm'); r.setProperty('--PH', PH + 'mm');
  }, [H, F, S, B, fit[1], fit[2]]);
  await p.evaluate(() => document.fonts.ready);
  await p.evaluate(() => drawMarks());
  await p.waitForTimeout(300);
  await p.pdf({ path: path.join(root, 'seacrest_box-cover.pdf'), width: fit[1] + 'mm', height: fit[2] + 'mm', printBackground: true, pageRanges: '1' });
  const ins = await p.$('#insert');
  await ins.screenshot({ path: path.join(root, 'seacrest_box-cover.png') });
  console.log(`trim ${W.toFixed(1)} x ${H} mm (${(W / 25.4).toFixed(2)} x ${(H / 25.4).toFixed(2)} in), bleed ${B} mm, sheet: ${fit[0]}`);
  if (fit[2] > 216) console.log('note: this needs paper bigger than 8.5" tall; most photo printers top out at Letter/Legal.');
  await b.close();
})();
