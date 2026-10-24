// Prints the chrome-headless-shell that Puppeteer installed, so Remotion renders with the same pinned browser.
import os from 'node:os'
import path from 'node:path'
import { Browser, computeExecutablePath, detectBrowserPlatform } from '@puppeteer/browsers'
import { PUPPETEER_REVISIONS } from 'puppeteer-core/internal/revisions.js'

console.log(computeExecutablePath({
  browser: Browser.CHROMEHEADLESSSHELL,
  buildId: PUPPETEER_REVISIONS['chrome-headless-shell'],
  platform: detectBrowserPlatform(),
  cacheDir: process.env.PUPPETEER_CACHE_DIR || path.join(os.homedir(), '.cache', 'puppeteer'),
}))
