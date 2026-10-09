// Shared headless-Chromium launcher for the tools and tests in web/.
// The container ships Chromium at /opt/pw-browsers/chromium; elsewhere set
// CHROMIUM_PATH or let playwright-core find its own install.
import { chromium } from "playwright-core";
import { existsSync } from "node:fs";

const CANDIDATES = [
  "/opt/pw-browsers/chromium",
  "/usr/bin/chromium",
  "/usr/bin/chromium-browser",
  "/usr/bin/google-chrome",
];
const DEFAULT = CANDIDATES.find(p => existsSync(p));

export async function launch(options = {}) {
  const executablePath = process.env.CHROMIUM_PATH || DEFAULT || undefined;
  const args = options.args || ["--enable-unsafe-swiftshader", "--use-gl=swiftshader"];
  return chromium.launch({ executablePath, ...options, args });
}

export const VIEWPORTS = {
  mobile: { width: 390, height: 844, deviceScaleFactor: 2, isMobile: true, hasTouch: true },
  desktop: { width: 1280, height: 860, deviceScaleFactor: 1 },
};
