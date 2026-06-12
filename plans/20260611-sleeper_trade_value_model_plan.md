# Sleeper Trade Value Model Plan

**Date:** 2026-06-11

<details open>
<summary><big><big><big><strong>Motivation</strong></big></big></big></summary>

This plan frames a research path for constructing player value scores directly from observed Sleeper trades, instead of only comparing against public trade-value charts.

<div style="margin-left: 1.25rem; padding-left: 1rem; border-left: 3px solid #777;">

<details>
<summary><strong>Observed Market Prices - infer value from what managers actually trade.</strong></summary>

- Treat completed trades as noisy market-clearing observations.
- Estimate latent player and pick values that make real trade packages look plausibly balanced.
- Preserve enough trade context to separate fair market prices from league-specific weirdness.

</details>

<details>
<summary><strong>Package Math - model why two good assets rarely equal one elite asset.</strong></summary>

- Add consolidation discounts for secondary assets in multi-player packages.
- Test roster-spot penalties and position-specific scarcity effects.
- Let the top-end curve emerge from observed package behavior instead of forcing linear additivity.

</details>

<details>
<summary><strong>Practical Modeling Loop - start explainable, then get fancier only if needed.</strong></summary>

- Build a transparent baseline from normalized Sleeper trade observations.
- Compare learned values against RosterAudit and KeepTradeCut snapshots.
- Add complexity only when diagnostics show the simple model is missing repeatable trade behavior.

</details>

</div>

**The through-line is to learn a market-implied value curve from real trades while keeping every modeling assumption inspectable.**

</details>
<hr style="height: 3px; background: rgba(160, 160, 160, 0.35); border: 0; margin: 0.25rem 0;">
<details open>
<summary><big><big><big><strong>Work Items</strong></big></big></big></summary>

**Status:** 🅿️ Not Started | 🚧 In Progress | ✅ Done | ⏸️ Paused | ⛔ Blocked

<div style="margin-left: 1.25rem; padding-left: 1rem; border-left: 3px solid #777;">

<details>
<summary><big><strong>1. 🅿️ Define Sleeper Trade Dataset</strong></big></summary>

<table style="width: 100%; table-layout: fixed;">
  <colgroup>
    <col style="width: 2%; white-space: nowrap;">
    <col style="width: 20%;">
    <col style="width: 10%; white-space: nowrap;">
    <col style="width: 10%; white-space: nowrap;">
    <col style="width: 10%; white-space: nowrap;">
    <col style="width: 48%;">
  </colgroup>
  <thead>
    <tr>
      <th>#</th>
      <th>Subtask</th>
      <th>Status</th>
      <th>PR</th>
      <th>Date Completed</th>
      <th>Notes</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td style="white-space: nowrap;">a</td>
      <td>Lock league format</td>
      <td style="white-space: nowrap;">🅿️ Not Started</td>
      <td style="white-space: nowrap;">-</td>
      <td style="white-space: nowrap;">-</td>
      <td>Restrict the initial dataset to 12-team dynasty PPR superflex leagues with no tight end premium.</td>
    </tr>
    <tr>
      <td style="white-space: nowrap;">b</td>
      <td>Identify trade source</td>
      <td style="white-space: nowrap;">🚧 In Progress</td>
      <td style="white-space: nowrap;">-</td>
      <td style="white-space: nowrap;">-</td>
      <td>Added seed-user discovery plus a Sleeper league-history puller; still need real seeds to size usable target-format data.</td>
    </tr>
    <tr>
      <td style="white-space: nowrap;">c</td>
      <td>Define raw schema</td>
      <td style="white-space: nowrap;">🅿️ Not Started</td>
      <td style="white-space: nowrap;">-</td>
      <td style="white-space: nowrap;">-</td>
      <td>Capture trade ID, league ID, timestamp, season, roster IDs, assets sent, assets received, and league settings proving the target format.</td>
    </tr>
    <tr>
      <td style="white-space: nowrap;">d</td>
      <td>Normalize assets</td>
      <td style="white-space: nowrap;">🅿️ Not Started</td>
      <td style="white-space: nowrap;">-</td>
      <td style="white-space: nowrap;">-</td>
      <td>Map players to Sleeper IDs and picks to structured season, round, and original owner fields.</td>
    </tr>
  </tbody>
</table>

> <details>
> <summary><strong>Design Notes</strong></summary>
>
> The first useful dataset does not need every Sleeper trade on earth. It needs enough clean, auditable trades from 12-team dynasty PPR superflex leagues with no tight end premium to test whether inferred values are coherent.
>
> </details>

</details>
<hr style="height: 1px; background: rgba(160, 160, 160, 0.25); border: 0; margin: 0.25rem 0;">
<details>
<summary><big><strong>2. 🅿️ Build Trade Package Representation</strong></big></summary>

<table style="width: 100%; table-layout: fixed;">
  <colgroup>
    <col style="width: 2%; white-space: nowrap;">
    <col style="width: 20%;">
    <col style="width: 10%; white-space: nowrap;">
    <col style="width: 10%; white-space: nowrap;">
    <col style="width: 10%; white-space: nowrap;">
    <col style="width: 48%;">
  </colgroup>
  <thead>
    <tr>
      <th>#</th>
      <th>Subtask</th>
      <th>Status</th>
      <th>PR</th>
      <th>Date Completed</th>
      <th>Notes</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td style="white-space: nowrap;">a</td>
      <td>Encode trade sides</td>
      <td style="white-space: nowrap;">🅿️ Not Started</td>
      <td style="white-space: nowrap;">-</td>
      <td style="white-space: nowrap;">-</td>
      <td>Represent each side as an ordered package of player and pick asset IDs.</td>
    </tr>
    <tr>
      <td style="white-space: nowrap;">b</td>
      <td>Add package features</td>
      <td style="white-space: nowrap;">🅿️ Not Started</td>
      <td style="white-space: nowrap;">-</td>
      <td style="white-space: nowrap;">-</td>
      <td>Compute asset count, top asset, secondary value mass, position mix, pick mix, and roster-slot pressure features.</td>
    </tr>
    <tr>
      <td style="white-space: nowrap;">c</td>
      <td>Filter bad trades</td>
      <td style="white-space: nowrap;">🅿️ Not Started</td>
      <td style="white-space: nowrap;">-</td>
      <td style="white-space: nowrap;">-</td>
      <td>Flag trades with missing assets, extreme league settings, obvious commissioner edits, or unsupported draft pick structures.</td>
    </tr>
  </tbody>
</table>

> <details>
> <summary><strong>Design Notes</strong></summary>
>
> Package representation should preserve asymmetry. A 1-for-3 trade is not just four asset rows; the model needs to know which side consolidated and which side diversified.
>
> </details>

</details>
<hr style="height: 1px; background: rgba(160, 160, 160, 0.25); border: 0; margin: 0.25rem 0;">
<details>
<summary><big><strong>3. 🅿️ Fit Linear Balance Baseline</strong></big></summary>

<table style="width: 100%; table-layout: fixed;">
  <colgroup>
    <col style="width: 2%; white-space: nowrap;">
    <col style="width: 20%;">
    <col style="width: 10%; white-space: nowrap;">
    <col style="width: 10%; white-space: nowrap;">
    <col style="width: 10%; white-space: nowrap;">
    <col style="width: 48%;">
  </colgroup>
  <thead>
    <tr>
      <th>#</th>
      <th>Subtask</th>
      <th>Status</th>
      <th>PR</th>
      <th>Date Completed</th>
      <th>Notes</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td style="white-space: nowrap;">a</td>
      <td>Initialize values</td>
      <td style="white-space: nowrap;">🅿️ Not Started</td>
      <td style="white-space: nowrap;">-</td>
      <td style="white-space: nowrap;">-</td>
      <td>Start from RosterAudit, KeepTradeCut, or rank-based priors so sparse assets do not float wildly.</td>
    </tr>
    <tr>
      <td style="white-space: nowrap;">b</td>
      <td>Fit balanced trades</td>
      <td style="white-space: nowrap;">🅿️ Not Started</td>
      <td style="white-space: nowrap;">-</td>
      <td style="white-space: nowrap;">-</td>
      <td>Optimize asset values so completed trade sides are close in total package value.</td>
    </tr>
    <tr>
      <td style="white-space: nowrap;">c</td>
      <td>Add regularization</td>
      <td style="white-space: nowrap;">🅿️ Not Started</td>
      <td style="white-space: nowrap;">-</td>
      <td style="white-space: nowrap;">-</td>
      <td>Shrink low-observation players toward priors and constrain values to a stable monotonic range.</td>
    </tr>
  </tbody>
</table>

> <details>
> <summary><strong>Design Notes</strong></summary>
>
> The linear baseline is intentionally naive. It gives us a diagnostic floor: if the simple model cannot recover a sensible top 100, either the data is messy or the assumptions are too weak.
>
> </details>

</details>
<hr style="height: 1px; background: rgba(160, 160, 160, 0.25); border: 0; margin: 0.25rem 0;">
<details>
<summary><big><strong>4. 🅿️ Add Consolidation Premium</strong></big></summary>

<table style="width: 100%; table-layout: fixed;">
  <colgroup>
    <col style="width: 2%; white-space: nowrap;">
    <col style="width: 20%;">
    <col style="width: 10%; white-space: nowrap;">
    <col style="width: 10%; white-space: nowrap;">
    <col style="width: 10%; white-space: nowrap;">
    <col style="width: 48%;">
  </colgroup>
  <thead>
    <tr>
      <th>#</th>
      <th>Subtask</th>
      <th>Status</th>
      <th>PR</th>
      <th>Date Completed</th>
      <th>Notes</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td style="white-space: nowrap;">a</td>
      <td>Discount secondary assets</td>
      <td style="white-space: nowrap;">🅿️ Not Started</td>
      <td style="white-space: nowrap;">-</td>
      <td style="white-space: nowrap;">-</td>
      <td>Model package value as top asset plus discounted secondary assets, with the discount learned from trades.</td>
    </tr>
    <tr>
      <td style="white-space: nowrap;">b</td>
      <td>Add roster penalties</td>
      <td style="white-space: nowrap;">🅿️ Not Started</td>
      <td style="white-space: nowrap;">-</td>
      <td style="white-space: nowrap;">-</td>
      <td>Penalize packages that require extra roster spots, especially in shallow-starting formats.</td>
    </tr>
    <tr>
      <td style="white-space: nowrap;">c</td>
      <td>Estimate top-end curve</td>
      <td style="white-space: nowrap;">🅿️ Not Started</td>
      <td style="white-space: nowrap;">-</td>
      <td style="white-space: nowrap;">-</td>
      <td>Compare learned values against log, exponential, and percentile transforms to understand the implied market curve.</td>
    </tr>
  </tbody>
</table>

> <details>
> <summary><strong>Design Notes</strong></summary>
>
> This is where the model should explain why two 5,000-value assets often do not buy one 10,000-value asset. The goal is not a magic multiplier; it is a stable package function that matches observed trade behavior.
>
> </details>

</details>
<hr style="height: 1px; background: rgba(160, 160, 160, 0.25); border: 0; margin: 0.25rem 0;">
<details>
<summary><big><strong>5. 🅿️ Validate Against Market Sources</strong></big></summary>

<table style="width: 100%; table-layout: fixed;">
  <colgroup>
    <col style="width: 2%; white-space: nowrap;">
    <col style="width: 20%;">
    <col style="width: 10%; white-space: nowrap;">
    <col style="width: 10%; white-space: nowrap;">
    <col style="width: 10%; white-space: nowrap;">
    <col style="width: 48%;">
  </colgroup>
  <thead>
    <tr>
      <th>#</th>
      <th>Subtask</th>
      <th>Status</th>
      <th>PR</th>
      <th>Date Completed</th>
      <th>Notes</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td style="white-space: nowrap;">a</td>
      <td>Compare RosterAudit</td>
      <td style="white-space: nowrap;">🅿️ Not Started</td>
      <td style="white-space: nowrap;">-</td>
      <td style="white-space: nowrap;">-</td>
      <td>Measure rank correlation and value-curve differences against RosterAudit snapshots.</td>
    </tr>
    <tr>
      <td style="white-space: nowrap;">b</td>
      <td>Compare KeepTradeCut</td>
      <td style="white-space: nowrap;">🅿️ Not Started</td>
      <td style="white-space: nowrap;">-</td>
      <td style="white-space: nowrap;">-</td>
      <td>Use KTC as a crowd-sentiment benchmark once a stable snapshot puller exists.</td>
    </tr>
    <tr>
      <td style="white-space: nowrap;">c</td>
      <td>Report disagreement</td>
      <td style="white-space: nowrap;">🅿️ Not Started</td>
      <td style="white-space: nowrap;">-</td>
      <td style="white-space: nowrap;">-</td>
      <td>Export players whose inferred trade-market values disagree sharply with public charts.</td>
    </tr>
  </tbody>
</table>

> <details>
> <summary><strong>Design Notes</strong></summary>
>
> Agreement with public sources is not the objective by itself. Disagreement is useful when the model can trace it back to actual package trades, scarcity effects, or stale public sentiment.
>
> </details>

</details>

</div>

</details>
<hr style="height: 3px; background: rgba(160, 160, 160, 0.35); border: 0; margin: 0.25rem 0;">
<details>
<summary><big><big><big><strong>Open Questions</strong></big></big></big></summary>

- Which Sleeper leagues are acceptable to use for initial trade data?
- How strict should the first-pass filter be for ambiguous league settings that look like 12-team dynasty PPR superflex but do not clearly expose every scoring rule?
- How should accepted trades be interpreted: balanced market prices, one-sided wins, or revealed preferences from both managers?
- How should we handle future rookie picks before the draft order is known?
- What minimum observation count should an asset need before its learned value can move far from the prior?

</details>
<hr style="height: 3px; background: rgba(160, 160, 160, 0.35); border: 0; margin: 0.25rem 0;">
<details>
<summary><big><big><big><strong>Appendix A - Modeling Sketch</strong></big></big></big></summary>

<details>
<summary><strong>Baseline Objective</strong></summary>

- Each completed trade provides two packages, side A and side B.
- Assign each asset a latent value.
- Define package value as the sum of included asset values for the first baseline.
- Minimize the difference between side A package value and side B package value across completed trades.
- Add regularization so learned values do not move too far from priors without strong trade evidence.

</details>

<details>
<summary><strong>Consolidation Objective</strong></summary>

- Sort each package by current estimated asset value.
- Preserve full value for the best asset in the package.
- Apply a learned discount to secondary assets.
- Optionally apply additional penalties for extra roster spots consumed.
- Fit asset values and package-function parameters together, then validate against held-out trades.

</details>

<details>
<summary><strong>Evaluation Ideas</strong></summary>

- Held-out trade balance error.
- Rank stability across bootstrap samples.
- Correlation against RosterAudit and KeepTradeCut snapshots.
- Error by position, asset tier, age bucket, and package size.
- Case studies for the largest source disagreements.

</details>

</details>
<hr style="height: 3px; background: rgba(160, 160, 160, 0.35); border: 0; margin: 0.25rem 0;">
<details>
<summary><big><big><big><strong>Appendix B - Data Notes</strong></big></big></big></summary>

<details>
<summary><strong>Candidate Raw Paths</strong></summary>

- Store discovered Sleeper users under <code>data/raw/sleeper/discovery/users_history.csv</code>.
- Store discovered Sleeper leagues under <code>data/raw/sleeper/discovery/leagues_history.csv</code>.
- Store discovered Sleeper league-user edges under <code>data/raw/sleeper/discovery/league_users_history.csv</code>.
- Store unexpanded discovery users under <code>data/raw/sleeper/discovery/user_frontier.csv</code>.
- Seed discovery with <code>ffvaluation seed-sleeper-network --username &lt;username&gt;</code>.
- Expand discovery iteratively with <code>ffvaluation expand-sleeper-network</code>; each run processes unexpanded frontier users, appends newly found league users back into the frontier, and flushes discovery CSVs after each expanded user.
- Store raw Sleeper trade pulls under <code>data/raw/sleeper/trades/YYYYMMDD.csv</code>.
- Store upserted trade observations under <code>data/raw/sleeper/trades/history.csv</code>.
- Pull with <code>ffvaluation pull-sleeper-trades --league-id &lt;league_id&gt;</code>; by default it follows <code>previous_league_id</code> and keeps completed trades from the past 365 days.
- Store intermediate model datasets under <code>data/processed/sleeper/trade_value_model/</code>.
- Store exploratory probes under <code>data/scratch/sleeper/</code>.

</details>

<details>
<summary><strong>Asset Types</strong></summary>

- Active NFL players.
- Retired or unsigned players still appearing in older trades.
- Future rookie picks.
- Waiver budget or other league-specific assets if Sleeper exposes them.
- Empty roster spots are not assets, but roster pressure should influence package value.

</details>

</details>
