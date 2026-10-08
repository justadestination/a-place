// Copy the few third-party browser files we ship into web/vendor/.
// Only the 3D page loads them (lazily, after WebGL is detected).
//   npm install && node tools/vendor.mjs
import { cpSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";

const three = new URL("../node_modules/three/", import.meta.url).pathname;
const version = JSON.parse(readFileSync(join(three, "package.json"), "utf8")).version;
const out = new URL("../vendor/three/", import.meta.url).pathname;
mkdirSync(join(out, "addons/controls"), { recursive: true });
cpSync(join(three, "build/three.module.min.js"), join(out, "three.module.min.js"));
cpSync(join(three, "examples/jsm/controls/OrbitControls.js"), join(out, "addons/controls/OrbitControls.js"));
cpSync(join(three, "LICENSE"), join(out, "LICENSE"));
writeFileSync(join(out, "VERSION"), `three ${version}\n`);
console.log(`vendored three ${version} -> ${out}`);
