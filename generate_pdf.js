const puppeteer = require('puppeteer');
const path = require('path');

(async () => {
  console.log('🚀 Launching headless Chrome...');
  const browser = await puppeteer.launch({
    headless: 'new',
    args: ['--no-sandbox', '--font-render-hinting=none']
  });
  const page = await browser.newPage();

  // A4 at 96 DPI = 794 x 1123 pixels
  await page.setViewport({ width: 794, height: 1123, deviceScaleFactor: 2 });

  const htmlPath = path.resolve(__dirname, 'AgentFlow_Brochure.html');
  console.log(`📄 Loading: ${htmlPath}`);

  await page.goto(`file://${htmlPath}`, { waitUntil: 'networkidle0', timeout: 30000 });

  // Wait for Google Fonts
  await page.evaluateHandle('document.fonts.ready');
  await new Promise(r => setTimeout(r, 3000));

  const outputPath = path.resolve(__dirname, 'AgentFlow_Brochure.pdf');

  await page.pdf({
    path: outputPath,
    width: '210mm',
    height: '297mm',
    printBackground: true,
    margin: { top: '0', right: '0', bottom: '0', left: '0' },
    preferCSSPageSize: true,
    scale: 1,
  });

  console.log(`✅ PDF saved: ${outputPath}`);
  console.log(`📐 Format: A4 (210mm × 297mm)`);

  // Verify page count
  const pdfBuffer = require('fs').readFileSync(outputPath);
  const pageCount = (pdfBuffer.toString().match(/\/Type\s*\/Page[^s]/g) || []).length;
  console.log(`📄 Pages: ${pageCount}`);

  await browser.close();
  console.log('🎉 Done!');
})();
