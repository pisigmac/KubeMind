import { KubeMindClient } from "@kubemind/sdk";

async function runDemo() {
  console.log("=".repeat(70));
  console.log("🚀 KubeMind TypeScript SDK End-to-End Demo");
  console.log("=".repeat(70));

  const client = new KubeMindClient({
    apiKey: "km_live_dev_key",
    workspaceId: "acme_corp",
    routerUrl: "http://localhost:9080",
    mindUrl: "http://localhost:9081",
    sentinelUrl: "http://localhost:9083",
  });

  // 1. Dry-run Intent and Security Classification
  console.log("\n--- 1. Classifying Intent & Sensitivity ---");
  try {
    const classification = await client.classify(
      "Dr. Jane Doe lives at 742 Evergreen Terrace and requested a summary."
    );
    console.log("Classified Intent:", classification.intent);
    console.log("Confidence Score:", classification.confidence);
  } catch (err: any) {
    console.log("Notice (Router):", err.message);
  }

  // 2. CFO Financial Analytics
  console.log("\n--- 2. Fetching CFO Cost & Token Usage Analytics ---");
  try {
    const analytics = await client.getCostAnalytics(24);
    console.log("Total Requests (24h):", analytics.total_requests);
    console.log("Total Tokens Processed:", analytics.total_tokens);
    console.log("Estimated Spend ($):", analytics.estimated_spend_usd);
    console.log("Provider Distribution:", analytics.providers);
  } catch (err: any) {
    console.log("Notice (Analytics):", err.message);
  }

  // 3. Cryptographic Ledger Verification
  console.log("\n--- 3. Cryptographically Verifying Audit Ledger ---");
  try {
    const audit = await client.verifyAuditLedger({ limit: 20 });
    console.log("SHA-256 Chain Intact & Verified:", audit.verified);
    console.log("Head Chain Hash:", audit.head_hash);
    console.log("Total Verified Entries:", audit.total_entries || audit.entries?.length || 0);
  } catch (err: any) {
    console.log("Notice (Sentinel):", err.message);
  }

  console.log("\n" + "=".repeat(70));
  console.log("✅ TypeScript Demo Walkthrough Complete");
  console.log("=".repeat(70));
}

runDemo().catch(console.error);
