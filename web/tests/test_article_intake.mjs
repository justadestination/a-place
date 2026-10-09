import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { existsSync, readFileSync, unlinkSync } from "node:fs";
import { resolve } from "node:path";
import {
  submitArticleDraft,
  rejectArticleDraft,
  approveArticleDraft,
  getIntakeItems,
} from "../components/article-intake/article-intake.js";

const ROOT = resolve(new URL("../..", import.meta.url).pathname);
const VAULT = resolve(ROOT, "shadenet/horizon/vault");
const ZINE_JSON = resolve(ROOT, "web/data/zine.json");
const ZINE_FEED = resolve(ROOT, "web/zine/feed.xml");

console.log("--- 1. Client Unit Tests: Article Intake ---");

// Test 1: Submit normal draft
const draft = submitArticleDraft({
  title: "Acoustic Nights at Moonlight",
  body: "A deep dive into weekly folk music and community sets at [[moonlight]].",
  type: "review",
  author: "a2a://agent/steward_99",
  venues: ["moonlight"],
});
assert.equal(draft.status, "pending");
assert.equal(draft.rejectionReason, null);
console.log("✓ Normal draft submitted with status 'pending'");

// Test 2: Spam moderation filter
const spam = submitArticleDraft({
  title: "Online casino free crypto pump",
  body: "Join now telegram @spammer click here to win free crypto pump prizes!",
  type: "article",
});
assert.equal(spam.status, "rejected");
assert.ok(spam.rejectionReason.includes("Automated moderation"));
console.log(`✓ Spam submission rejected with reason: "${spam.rejectionReason}"`);

// Test 3: Reject draft with reason
const draftToReject = submitArticleDraft({
  title: "Draft for Rejection",
  body: "This draft will be rejected with an editorial explanation.",
  type: "letter",
});
const rejected = rejectArticleDraft(draftToReject.id, "Piece is out of scope for the zine circulation.");
assert.equal(rejected.status, "rejected");
assert.equal(rejected.rejectionReason, "Piece is out of scope for the zine circulation.");
console.log(`✓ Rejection carries plain-language reason: "${rejected.rejectionReason}"`);

// Test 4: Rejection without reason fails
assert.throws(() => {
  rejectArticleDraft(draft.id, "");
}, /Rejections must carry a plain-language reason/);
console.log("✓ Rejection without reason is strictly rejected");

// Test 5: Approve and instantiate client model
const approved = approveArticleDraft(draft.id);
assert.equal(approved.status, "instantiated");
assert.equal(approved.nodeId, "note:acoustic-nights-at-moonlight");
console.log("✓ Approved draft marked instantiated with target nodeId");

console.log("\n--- 2. End-to-End Pipeline & Graph Instantiation ---");

const testSlug = "intake-e2e-test-piece";
const testTitle = "Intake E2E Test Piece";
const testVaultFile = resolve(VAULT, `${testSlug}.md`);

try {
  // Run python pipeline: submit -> approve -> instantiate
  const submitOut = execFileSync(
    "python3",
    [
      "-m", "shadenet.intake",
      "submit",
      "--title", testTitle,
      "--body", "Testing full intake cycle connecting to [[royal]] and [[Late Show, Every Night]].",
      "--type", "review",
      "--author", "E2E Tester",
      "--venues", "royal",
    ],
    { cwd: ROOT, encoding: "utf-8" }
  );

  const idMatch = submitOut.match(/Draft submitted: (sub-\w+)/);
  assert.ok(idMatch, `Could not parse submission ID from: ${submitOut}`);
  const subId = idMatch[1];
  console.log(`✓ Submitted CLI draft: ${subId}`);

  // Approve and instantiate
  const approveOut = execFileSync(
    "python3",
    ["-m", "shadenet.intake", "approve", "--id", subId],
    { cwd: ROOT, encoding: "utf-8" }
  );
  assert.ok(approveOut.includes("instantiated successfully"), `Instantiation output: ${approveOut}`);
  console.log("✓ Submission approved and instantiated via pipeline");

  // Verify vault markdown file created
  assert.ok(existsSync(testVaultFile), `Vault file was not created: ${testVaultFile}`);
  const mdContent = readFileSync(testVaultFile, "utf-8");
  assert.ok(mdContent.includes(`title: "${testTitle}"`));
  assert.ok(mdContent.includes("status: published"));
  console.log("✓ Vault markdown file verified with YAML frontmatter");

  // Verify node in zine.json
  const graph = JSON.parse(readFileSync(ZINE_JSON, "utf-8"));
  const expectedNodeId = `note:${testSlug}`;
  const node = graph.nodes.find(n => n.id === expectedNodeId);
  assert.ok(node, `Node ${expectedNodeId} not found in zine.json`);
  assert.equal(node.title, testTitle);
  assert.equal(node.type, "review");
  console.log(`✓ Instantiated node ${node.id} verified in web/data/zine.json`);

  // Verify edges to royal venue and linked notes
  const edges = graph.edges.filter(e => e.source === expectedNodeId || e.target === expectedNodeId);
  assert.ok(edges.length >= 1, `Expected edges for ${expectedNodeId}, found ${edges.length}`);
  console.log(`✓ Graph edges verified (${edges.length} edges connected to node)`);

  // Verify inclusion in RSS feed
  const rssXml = readFileSync(ZINE_FEED, "utf-8");
  assert.ok(rssXml.includes(testTitle), "Instantiated article missing from zine RSS feed");
  console.log("✓ Instantiated article verified in web/zine/feed.xml");

} finally {
  // Clean up test file and re-build
  if (existsSync(testVaultFile)) {
    unlinkSync(testVaultFile);
  }
  execFileSync("python3", ["web/tools/build_zine.py"], { cwd: ROOT, encoding: "utf-8" });
  console.log("✓ Test fixture cleaned up and zine rebuilt");
}

console.log("\nALL ARTICLE INTAKE & INSTANTIATION TESTS PASSED!");
