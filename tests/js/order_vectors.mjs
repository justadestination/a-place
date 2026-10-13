// Checks web/components/worldsum/pennant.js hearOrder against tests/data/order_vectors.json.
// The Python side is tests/test_order_parity.py. Exit code 1 on any mismatch.
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

const root = new URL("../../", import.meta.url);
const { hearOrder } = await import(new URL("web/components/worldsum/pennant.js", root));
const vectors = JSON.parse(readFileSync(fileURLToPath(new URL("tests/data/order_vectors.json", root)), "utf8"));

let failed = 0;
for (const row of vectors) {
  let got;
  try {
    const heard = hearOrder(row.order, row.base);
    const profile = heard.profile || {};
    got = {
      expect: {
        field: heard.appearance.field,
        charge: heard.appearance.charge,
        motto: heard.appearance.motto,
        line: heard.appearance.line,
        ribbon: heard.appearance.ribbon,
        fly: heard.appearance.fly,
        listed: heard.listed,
        place_id: heard.placeId,
        intents: profile.intents || [],
        good_at: profile.good_at ?? null,
        enjoy: profile.enjoy ?? null,
        refuse: profile.refuse ?? null,
      },
    };
  } catch (err) {
    got = { error: err.message };
  }
  const want = row.error !== undefined ? { error: row.error } : { expect: row.expect };
  if (JSON.stringify(got) !== JSON.stringify(want)) {
    failed += 1;
    console.log(`MISMATCH ${JSON.stringify(row.order)}\n  want ${JSON.stringify(want)}\n  got  ${JSON.stringify(got)}`);
  }
}
console.log(`${vectors.length - failed}/${vectors.length} order vectors agree`);
process.exit(failed ? 1 : 0);
