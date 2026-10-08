// Shared headless-Chromium launcher for the tools and tests in web/.
// The container ships Chromium at /opt/pw-browsers/chromium; elsewhere set
// CHROMIUM_PATH or let playwright-core find its own install.
import { chromium } from "playwright-core";
import { existsSync } from "node:fs";

const DEFAULT = "/opt/pw-browsers/chromium";

export async function launch() {
  const executablePath = process.env.CHROMIUM_PATH || (existsSync(DEFAULT) ? DEFAULT : undefined);
  return chromium.launch({ executablePath, args: ["--enable-unsafe-swiftshader", "--use-gl=swiftshader"] });
}

export const VIEWPORTS = {
  mobile: { width: 390, height: 844, deviceScaleFactor: 2, isMobile: true, hasTouch: true },
  desktop: { width: 1280, height: 860, deviceScaleFactor: 1 },
};
