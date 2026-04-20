import { execSync } from 'child_process'
import { existsSync, mkdirSync, readdirSync, renameSync, rmSync, unlinkSync } from 'fs'
import os from 'os'
import path from 'path'

const JRE_VERSION = '21'
export const JRE_DEST = path.resolve('src-python', 'jre')

const PLATFORM_MAP: Record<string, string> = {
  win32: 'windows',
  darwin: 'mac',
  linux: 'linux',
}
const ARCH_MAP: Record<string, string> = {
  x64: 'x64',
  arm64: 'aarch64',
}

/** Downloads an Adoptium JRE to src-python/jre/. Returns true if a new JRE was installed. */
export function ensureJre(): boolean {
  if (existsSync(JRE_DEST)) return false

  const platform = os.platform()
  const arch = os.arch()
  const adoptOs = PLATFORM_MAP[platform]
  const adoptArch = ARCH_MAP[arch]

  if (!adoptOs) throw new Error(`Unsupported platform: ${platform}`)
  if (!adoptArch) throw new Error(`Unsupported arch: ${arch}`)

  const url = [
    `https://api.adoptium.net/v3/binary/latest/${JRE_VERSION}/ga`,
    adoptOs,
    adoptArch,
    'jre/hotspot/normal/eclipse',
  ].join('/')

  const tmpDir = os.tmpdir()
  const isWindows = platform === 'win32'
  const archivePath = path.join(tmpDir, isWindows ? 'adoptium-jre.zip' : 'adoptium-jre.tar.gz')
  const extractDir = path.join(tmpDir, 'adoptium-jre-extract')

  console.log(`Downloading JRE ${JRE_VERSION} for ${adoptOs}/${adoptArch}…`)

  if (isWindows) {
    execSync(
      `powershell -Command "& { $ProgressPreference = 'SilentlyContinue'; Invoke-WebRequest -Uri '${url}' -OutFile '${archivePath}' }"`,
      { stdio: 'inherit' },
    )
  } else {
    execSync(`curl -fsSL "${url}" -o "${archivePath}"`, { stdio: 'inherit' })
  }

  console.log('Extracting JRE…')
  mkdirSync(extractDir, { recursive: true })

  if (isWindows) {
    execSync(
      `powershell -Command "Expand-Archive -Path '${archivePath}' -DestinationPath '${extractDir}' -Force"`,
      { stdio: 'inherit' },
    )
  } else {
    execSync(`tar -xzf "${archivePath}" -C "${extractDir}"`, { stdio: 'inherit' })
  }

  const entries = readdirSync(extractDir)
  if (entries.length !== 1) throw new Error(`Unexpected archive layout: ${entries.join(', ')}`)
  let jrePath = path.join(extractDir, entries[0])

  // macOS JDK archives wrap the JRE under Contents/Home
  if (platform === 'darwin') {
    const macHome = path.join(jrePath, 'Contents', 'Home')
    if (existsSync(macHome)) jrePath = macHome
  }

  renameSync(jrePath, JRE_DEST)
  rmSync(extractDir, { recursive: true, force: true })
  unlinkSync(archivePath)

  console.log(`JRE installed at: ${JRE_DEST}`)
  return true
}

// Allow running directly: pnpm jre:download
if (process.argv[1] === import.meta.filename) {
  ensureJre()
}
