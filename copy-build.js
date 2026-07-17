// copy-build.js – move Vite output to Vercel's expected directory
const fs = require('fs');
const path = require('path');

const src = path.resolve(__dirname, 'frontend/dist');
const dest = path.resolve(__dirname, 'public');

// Ensure destination exists
fs.mkdirSync(dest, { recursive: true });

function copyRecursive(srcDir, dstDir) {
  const entries = fs.readdirSync(srcDir, { withFileTypes: true });
  for (const entry of entries) {
    const srcPath = path.join(srcDir, entry.name);
    const dstPath = path.join(dstDir, entry.name);
    if (entry.isDirectory()) {
      fs.mkdirSync(dstPath, { recursive: true });
      copyRecursive(srcPath, dstPath);
    } else {
      fs.copyFileSync(srcPath, dstPath);
    }
  }
}

copyRecursive(src, dest);
console.log('✅ Vite build copied to /public');
