const { chromium } = require('playwright');
(async () => {
  const dir = process.argv[2], out = process.argv[3];
  const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: 1080, height: 1350 }, deviceScaleFactor: 1 });
  await p.goto('file://' + dir + '/intro.html'); await p.evaluate(() => document.fonts.ready);
  for (const id of ['s1','s2','s3']) await (await p.$('#'+id)).screenshot({ path: `${out}/intro-${id}.png` });
  await b.close();
})();
