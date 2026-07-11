# Sleeper 2025 Trade Ingestion Plan

**Date:** 2026-07-11

<details open>
<summary><big><big><big><strong>Motivation</strong></big></big></big></summary>

This plan defines how we will collect a large, auditable 2025 Sleeper trade dataset for the first trade-value experiments.

<div style="margin-left: 1.25rem; padding-left: 1rem; border-left: 3px solid #777;">

<details>
<summary><strong>Broad Market - capture dynasty superflex trades across reasonable league sizes.</strong></summary>

- Include 2025 leagues where `is_dynasty = 1` and `is_superflex = 1`.
- Include leagues with `total_rosters BETWEEN 8 AND 16`.
- Retain PPR, TE premium, roster positions, and league size as modeling context rather than filters.

</details>

<details>
<summary><strong>Raw Evidence - preserve the Sleeper transaction payload before interpretation.</strong></summary>

- Store completed trade transactions in SQLite keyed by `league_id` and `transaction_id`.
- Keep players, picks, FAAB, roster IDs, timestamps, round, and source capture metadata.
- Make ingestion resumable and safe to rerun without duplicating transactions.

</details>

<details>
<summary><strong>Model Readiness - turn raw transactions into manager-side packages later.</strong></summary>

- Keep raw trade ingestion independent of roster hydration.
- Hydrate `league_id + roster_id -> user_id` whenever useful.
- Build processed trade sides only after the raw dataset is stable.

</details>

</div>

**The through-line is to collect a broad, durable raw market record first, then add interpretation in reproducible processing steps.**

</details>
<hr style="height: 3px; background: rgba(160, 160, 160, 0.35); border: 0; margin: 0.25rem 0;">
<details open>
<summary><big><big><big><strong>Work Items</strong></big></big></big></summary>

**Status:** ⏳ Not Started | 🚧 In Progress | ✅ Done | ⏸️ Paused | 🛑 Blocked

<div style="margin-left: 1.25rem; padding-left: 1rem; border-left: 3px solid #777;">

<details>
<summary><big><strong>1. ⏳ Lock 2025 Target League Universe</strong></big></summary>

<table style="width: 100%; table-layout: fixed;">
  <colgroup>
    <col style="width: 2%; white-space: nowrap;">
    <col style="width: 20%;">
    <col style="width: 10%; white-space: nowrap;">
    <col style="width: 10%; white-space: nowrap;">
    <col style="width: 10%; white-space: nowrap;">
    <col style="width: 48%;">
  </colgroup>
  <thead><tr><th>#</th><th>Subtask</th><th>Status</th><th>PR</th><th>Date Completed</th><th>Notes</th></tr></thead>
  <tbody>
    <tr><td style="white-space: nowrap;">a</td><td>Apply target filter</td><td style="white-space: nowrap;">🚧 In Progress</td><td style="white-space: nowrap;">-</td><td style="white-space: nowrap;">-</td><td>Use 2025 dynasty superflex leagues with 8-16 rosters; current universe is approximately 125k leagues.</td></tr>
    <tr><td style="white-space: nowrap;">b</td><td>Materialize league IDs</td><td style="white-space: nowrap;">⏳ Not Started</td><td style="white-space: nowrap;">-</td><td style="white-space: nowrap;">-</td><td>Write a deterministic target-league selection into SQLite so the ingestion run has a stable worklist.</td></tr>
    <tr><td style="white-space: nowrap;">c</td><td>Record league context</td><td style="white-space: nowrap;">⏳ Not Started</td><td style="white-space: nowrap;">-</td><td style="white-space: nowrap;">-</td><td>Retain league size, scoring, TE premium, roster positions, and season for downstream stratification.</td></tr>
  </tbody>
</table>

> <details>
> <summary><strong>Design Notes</strong></summary>
>
> The filter defines the initial market, not the final model. We should not discard format variables that may explain differences in trade behavior.
>
> </details>

</details>
<hr style="height: 1px; background: rgba(160, 160, 160, 0.25); border: 0; margin: 0.25rem 0;">
<details>
<summary><big><strong>2. ⏳ Define Raw Trade SQLite Tables</strong></big></summary>

<table style="width: 100%; table-layout: fixed;">
  <colgroup><col style="width: 2%; white-space: nowrap;"><col style="width: 20%;"><col style="width: 10%; white-space: nowrap;"><col style="width: 10%; white-space: nowrap;"><col style="width: 10%; white-space: nowrap;"><col style="width: 48%;"></colgroup>
  <thead><tr><th>#</th><th>Subtask</th><th>Status</th><th>PR</th><th>Date Completed</th><th>Notes</th></tr></thead>
  <tbody>
    <tr><td style="white-space: nowrap;">a</td><td>Store raw transactions</td><td style="white-space: nowrap;">🚧 In Progress</td><td style="white-space: nowrap;">-</td><td style="white-space: nowrap;">-</td><td>Persist the complete normalized Sleeper transaction row, including raw JSON asset payloads.</td></tr>
    <tr><td style="white-space: nowrap;">b</td><td>Key and upsert rows</td><td style="white-space: nowrap;">🚧 In Progress</td><td style="white-space: nowrap;">-</td><td style="white-space: nowrap;">-</td><td>Use `(league_id, transaction_id)` as the natural key and make reruns idempotent.</td></tr>
    <tr><td style="white-space: nowrap;">c</td><td>Add ingestion metadata</td><td style="white-space: nowrap;">⏳ Not Started</td><td style="white-space: nowrap;">-</td><td style="white-space: nowrap;">-</td><td>Track source season, transaction round, capture timestamp, completion timestamp, and fetch status.</td></tr>
  </tbody>
</table>

> <details>
> <summary><strong>Design Notes</strong></summary>
>
> The raw table is the source of truth. Processed tables can be rebuilt; raw payloads should not need to be fetched again merely because a modeling interpretation changes.
>
> </details>

</details>
<hr style="height: 1px; background: rgba(160, 160, 160, 0.25); border: 0; margin: 0.25rem 0;">
<details>
<summary><big><strong>3. ⏳ Build Resumable 2025 Trade Fetch</strong></summary>

<table style="width: 100%; table-layout: fixed;">
  <colgroup><col style="width: 2%; white-space: nowrap;"><col style="width: 20%;"><col style="width: 10%; white-space: nowrap;"><col style="width: 10%; white-space: nowrap;"><col style="width: 10%; white-space: nowrap;"><col style="width: 48%;"></colgroup>
  <thead><tr><th>#</th><th>Subtask</th><th>Status</th><th>PR</th><th>Date Completed</th><th>Notes</th></tr></thead>
  <tbody>
    <tr><td style="white-space: nowrap;">a</td><td>Fetch rounds 1-18</td><td style="white-space: nowrap;">🚧 In Progress</td><td style="white-space: nowrap;">-</td><td style="white-space: nowrap;">-</td><td>Request each transaction round for each target 2025 league and keep only completed trades.</td></tr>
    <tr><td style="white-space: nowrap;">b</td><td>Checkpoint by league</td><td style="white-space: nowrap;">⏳ Not Started</td><td style="white-space: nowrap;">-</td><td style="white-space: nowrap;">-</td><td>Record completed league/round work so an interruption resumes without repeating finished requests unnecessarily.</td></tr>
    <tr><td style="white-space: nowrap;">c</td><td>Throttle and retry</td><td style="white-space: nowrap;">⏳ Not Started</td><td style="white-space: nowrap;">-</td><td style="white-space: nowrap;">-</td><td>Respect the Sleeper request ceiling and retry transient 5xx, 52x, timeout, SSL, and connection failures.</td></tr>
  </tbody>
</table>

> <details>
> <summary><strong>Design Notes</strong></summary>
>
> Trade ingestion does not depend on roster hydration. Raw transactions already contain the league and roster identifiers needed for later attribution.
>
> </details>

</details>
<hr style="height: 1px; background: rgba(160, 160, 160, 0.25); border: 0; margin: 0.25rem 0;">
<details>
<summary><big><strong>4. ⏳ Run a Scale Pilot</strong></summary>

<table style="width: 100%; table-layout: fixed;">
  <colgroup><col style="width: 2%; white-space: nowrap;"><col style="width: 20%;"><col style="width: 10%; white-space: nowrap;"><col style="width: 10%; white-space: nowrap;"><col style="width: 10%; white-space: nowrap;"><col style="width: 48%;"></colgroup>
  <thead><tr><th>#</th><th>Subtask</th><th>Status</th><th>PR</th><th>Date Completed</th><th>Notes</th></tr></thead>
  <tbody>
    <tr><td style="white-space: nowrap;">a</td><td>Pull 100 leagues</td><td style="white-space: nowrap;">⏳ Not Started</td><td style="white-space: nowrap;">-</td><td style="white-space: nowrap;">-</td><td>Measure requests, runtime, trades per league, duplicate rate, and raw database growth.</td></tr>
    <tr><td style="white-space: nowrap;">b</td><td>Pull 1,000 leagues</td><td style="white-space: nowrap;">⏳ Not Started</td><td style="white-space: nowrap;">-</td><td style="white-space: nowrap;">-</td><td>Validate that throughput and error rates remain stable at a useful sample size.</td></tr>
    <tr><td style="white-space: nowrap;">c</td><td>Estimate full run</td><td style="white-space: nowrap;">⏳ Not Started</td><td style="white-space: nowrap;">-</td><td style="white-space: nowrap;">-</td><td>Project runtime, storage, and expected completed-trade count for approximately 125k leagues.</td></tr>
  </tbody>
</table>

> <details>
> <summary><strong>Design Notes</strong></summary>
>
> The pilot is a capacity measurement, not a modeling sample. Its main purpose is to prevent committing to a full run without knowing the request and storage footprint.
>
> </details>

</details>
<hr style="height: 1px; background: rgba(160, 160, 160, 0.25); border: 0; margin: 0.25rem 0;">
<details>
<summary><big><strong>5. ⏳ Execute Full 2025 Collection</strong></summary>

<table style="width: 100%; table-layout: fixed;">
  <colgroup><col style="width: 2%; white-space: nowrap;"><col style="width: 20%;"><col style="width: 10%; white-space: nowrap;"><col style="width: 10%; white-space: nowrap;"><col style="width: 10%; white-space: nowrap;"><col style="width: 48%;"></colgroup>
  <thead><tr><th>#</th><th>Subtask</th><th>Status</th><th>PR</th><th>Date Completed</th><th>Notes</th></tr></thead>
  <tbody>
    <tr><td style="white-space: nowrap;">a</td><td>Run target worklist</td><td style="white-space: nowrap;">⏳ Not Started</td><td style="white-space: nowrap;">-</td><td style="white-space: nowrap;">-</td><td>Run the resumable collector over all materialized 2025 target leagues.</td></tr>
    <tr><td style="white-space: nowrap;">b</td><td>Track completion state</td><td style="white-space: nowrap;">⏳ Not Started</td><td style="white-space: nowrap;">-</td><td style="white-space: nowrap;">-</td><td>Report completed leagues, failed leagues, requests, retries, trades, and database size/counts.</td></tr>
    <tr><td style="white-space: nowrap;">c</td><td>Retry failed work</td><td style="white-space: nowrap;">⏳ Not Started</td><td style="white-space: nowrap;">-</td><td style="white-space: nowrap;">-</td><td>Rerun only incomplete or failed league/round work until the target universe is accounted for.</td></tr>
  </tbody>
</table>

> <details>
> <summary><strong>Design Notes</strong></summary>
>
> A full run should be restartable after a machine restart, rate limit, network outage, or user interruption without corrupting or duplicating the raw dataset.
>
> </details>

</details>
<hr style="height: 1px; background: rgba(160, 160, 160, 0.25); border: 0; margin: 0.25rem 0;">
<details>
<summary><big><strong>6. ⏳ Validate Raw Dataset</strong></summary>

<table style="width: 100%; table-layout: fixed;">
  <colgroup><col style="width: 2%; white-space: nowrap;"><col style="width: 20%;"><col style="width: 10%; white-space: nowrap;"><col style="width: 10%; white-space: nowrap;"><col style="width: 10%; white-space: nowrap;"><col style="width: 48%;"></colgroup>
  <thead><tr><th>#</th><th>Subtask</th><th>Status</th><th>PR</th><th>Date Completed</th><th>Notes</th></tr></thead>
  <tbody>
    <tr><td style="white-space: nowrap;">a</td><td>Check key uniqueness</td><td style="white-space: nowrap;">⏳ Not Started</td><td style="white-space: nowrap;">-</td><td style="white-space: nowrap;">-</td><td>Confirm no duplicate `(league_id, transaction_id)` rows remain.</td></tr>
    <tr><td style="white-space: nowrap;">b</td><td>Profile trade coverage</td><td style="white-space: nowrap;">⏳ Not Started</td><td style="white-space: nowrap;">-</td><td style="white-space: nowrap;">-</td><td>Count trades by league, round, package size, player, pick, FAAB, and completed date.</td></tr>
    <tr><td style="white-space: nowrap;">c</td><td>Measure missingness</td><td style="white-space: nowrap;">⏳ Not Started</td><td style="white-space: nowrap;">-</td><td style="white-space: nowrap;">-</td><td>Identify leagues with missing rounds, malformed payloads, or no completed trades.</td></tr>
  </tbody>
</table>

> <details>
> <summary><strong>Design Notes</strong></summary>
>
> Before modeling, we need to know whether the data represents a connected market or a collection of sparse league-specific islands.
>
> </details>

</details>

</div>

</details>
<hr style="height: 3px; background: rgba(160, 160, 160, 0.35); border: 0; margin: 0.25rem 0;">
<details open>
<summary><big><big><big><strong>Open Questions</strong></big></big></big></summary>

- Should failed leagues be retried indefinitely, or capped and reported after a fixed number of attempts?
- Should transaction rounds 1-18 be enough for the 2025 season, or do we need a separate offseason strategy?
- How should deleted leagues and leagues with incomplete transaction history be classified?
- Should we retain non-target leagues discovered incidentally for future comparison models?
- What minimum trade count makes a league useful for the first model?

</details>
<hr style="height: 3px; background: rgba(160, 160, 160, 0.35); border: 0; margin: 0.25rem 0;">
<details>
<summary><big><big><big><strong>Appendix A - Target Query</strong></big></big></big></summary>

```sql
SELECT league_id
FROM leagues
WHERE league_season = 2025
  AND is_dynasty = 1
  AND is_superflex = 1
  AND total_rosters BETWEEN 8 AND 16;
```

</details>
<hr style="height: 3px; background: rgba(160, 160, 160, 0.35); border: 0; margin: 0.25rem 0;">
<details>
<summary><big><big><big><strong>Appendix B - Collection Shape</strong></big></big></big></summary>

```text
discovery.sqlite
  leagues                  # target league universe and settings

trades.sqlite or raw table
  trades                   # raw completed Sleeper transactions
  leagues                  # copied league context
  players                  # optional player lookup
  rosters                  # optional league_id + roster_id -> user_id bridge

processed table, later
  trade_sides              # manager-side player/pick/FAAB packages
```

Rosters are intentionally not a prerequisite for raw trade ingestion. The raw transactions already contain the stable `league_id` and roster identifiers needed for later attribution.

</details>
