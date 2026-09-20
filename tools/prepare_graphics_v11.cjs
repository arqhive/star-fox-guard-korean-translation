/* Package the ImageGen edits for the existing Wii U texture layout.
 * Requires sharp (npm install sharp, or set NODE_PATH to a bundled installation).
 * Source art and v1.0 inputs live in translation/images_source (not committed).
 * This performs size conversion and a localized composite, not text generation.
 */
const sharp = require('sharp');
const fs = require('node:fs/promises');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
const inputs = path.join(root, 'translation', 'images_source');

async function main() {
  const source = sharp(path.join(inputs, 'signature_generated.png'));
  const { data, info } = await source.ensureAlpha().raw().toBuffer({ resolveWithObject: true });
  let left = info.width, top = info.height, right = -1, bottom = -1;
  for (let y = 0; y < info.height; y++) {
    for (let x = 0; x < info.width; x++) {
      if (data[(y * info.width + x) * 4 + 3] > 16) {
        left = Math.min(left, x); top = Math.min(top, y);
        right = Math.max(right, x); bottom = Math.max(bottom, y);
      }
    }
  }
  if (right < left) throw new Error('Signature has no visible pixels');
  // Match the original occupied area; unused right-side atlas space stays empty.
  const signature = await source.extract({ left, top, width: right-left+1, height: bottom-top+1 })
    .resize(305, 106, { fit: 'fill', kernel: 'lanczos3' }).png().toBuffer();
  const credit = path.join(root, 'translation/images_ko/ui_credit.dat/credit_003.png');
  await fs.mkdir(path.dirname(credit), { recursive: true });
  await sharp({ create: { width: 512, height: 128, channels: 4, background: '#00000000' } })
    .composite([{ input: signature, left: 5, top: 7 }]).png().toFile(credit);

  // Keep the existing Korean title/body and all pixels outside the signature area.
  const box = { left: 180, top: 650, width: 410, height: 106 };
  const resized = await sharp(path.join(inputs, 'contract_generated.png'))
    .resize(1024, 1024, { fit: 'fill', kernel: 'lanczos3' }).png().toBuffer();
  const patch = await sharp(resized).extract(box).ensureAlpha().raw().toBuffer();
  for (let y = 0; y < box.height; y++) {
    for (let x = 0; x < box.width; x++) {
      const edge = Math.min(x, y, box.width-1-x, box.height-1-y);
      const t = Math.min(1, edge / 8);
      patch[(y*box.width+x)*4+3] = Math.round(255*t*t*(3-2*t));
    }
  }
  const contract = path.join(root, 'translation/images_ko/ui_msg_firsttime.dat/msg_firsttime_000.png');
  await fs.mkdir(path.dirname(contract), { recursive: true });
  await sharp(path.join(inputs, 'contract_v10.png'))
    .composite([{ input: patch, raw: { width: box.width, height: box.height, channels: 4 }, left: box.left, top: box.top }])
    .removeAlpha().png().toFile(contract);
  console.log('Prepared credit 512x128 RGBA and contract 1024x1024 RGB.');
}
main().catch(e => { console.error(e); process.exitCode = 1; });
