import { execSync } from 'child_process';
import { existsSync, readdirSync, statSync } from 'fs';
import os from 'os';
import path from 'path';

type Mode = 'dev' | 'build';

const modeArg = process.argv[2];
const mode: Mode = modeArg === 'build' ? 'build' : 'dev';

const bundles: Partial<Record<NodeJS.Platform, string>> = {
  linux: 'deb,appimage,rpm',
  darwin: 'dmg',
  win32: 'nsis,msi',
};

const sidecarSourceRoot = path.resolve('src-python');
const sidecarSourceExt = new Set(['.py', '.spec', '.toml']);
const ignoredDirs = new Set([
  '.venv',
  '__pycache__',
  'build',
  'dist',
  '.mypy_cache',
  '.pytest_cache',
]);

function getTargetTriple(): string {
  const out = execSync('rustc -vV', { encoding: 'utf8' });
  for (const line of out.split('\n')) {
    if (line.startsWith('host:')) return line.split(':', 2)[1].trim();
  }
  throw new Error('could not determine rustc host triple');
}

function getLatestSidecarSourceMtimeMs(dir: string): number {
  let latest = 0;
  const entries = readdirSync(dir, { withFileTypes: true });

  for (const entry of entries) {
    if (entry.isDirectory()) {
      if (!ignoredDirs.has(entry.name)) {
        const nested = getLatestSidecarSourceMtimeMs(path.join(dir, entry.name));
        if (nested > latest) latest = nested;
      }
      continue;
    }

    if (!entry.isFile()) continue;

    const fullPath = path.join(dir, entry.name);
    if (!sidecarSourceExt.has(path.extname(entry.name))) continue;

    const mtimeMs = statSync(fullPath).mtimeMs;
    if (mtimeMs > latest) latest = mtimeMs;
  }

  return latest;
}

function ensureSidecarBuilt(forceBuild: boolean): void {
  const triple = getTargetTriple();
  const sidecarPath = path.resolve('src-tauri/binaries', `pratapan-sidecar-${triple}`);
  const binaryExists = existsSync(sidecarPath);
  const sourceChanged =
    binaryExists &&
    getLatestSidecarSourceMtimeMs(sidecarSourceRoot) > statSync(sidecarPath).mtimeMs;

  const shouldBuild = forceBuild || !binaryExists || sourceChanged;

  if (shouldBuild) {
    if (!forceBuild && !binaryExists) {
      console.log('Sidecar binary not found, building...');
    } else if (!forceBuild && sourceChanged) {
      console.log('Sidecar source changed, rebuilding...');
    }
    execSync('pnpm run sidecar:build', { stdio: 'inherit' });
  }
}

function runTauriDev(): void {
  ensureSidecarBuilt(false);
  execSync('tauri dev', { stdio: 'inherit' });
}

function runTauriBuild(): void {
  ensureSidecarBuilt(true);

  const platform = os.platform();
  const platformBundles = bundles[platform];
  const cmd = platformBundles
    ? `tauri build --bundles ${platformBundles}`
    : 'tauri build';

  execSync(cmd, { stdio: 'inherit' });
}

if (mode === 'build') {
  runTauriBuild();
} else {
  runTauriDev();
}