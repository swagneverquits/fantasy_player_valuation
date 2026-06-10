# Fantasy Football Player Valuation Research Plan

**Date:** 2026-06-08

<details open>
<summary><big><big><big><strong>Motivation</strong></big></big></big></summary>

This plan frames a research path for benchmarking public fantasy football player valuation sources and building a more useful valuation model for 12-team superflex PPR leagues.

<div style="margin-left: 1.25rem; padding-left: 1rem; border-left: 3px solid #777;">

<details>
<summary><strong>Source Truth - separate what each market signal actually measures.</strong></summary>

- Compare KeepTradeCut as crowd-stated dynasty sentiment.
- Compare RosterAudit as observed trade-market behavior, according to its public materials.
- Treat disagreement between sources as a signal to inspect, not just noise to average away.

</details>

<details>
<summary><strong>Evaluation Discipline - keep market value, production value, and trade utility separate.</strong></summary>

- Measure market accuracy against observed prices or preferences.
- Measure production accuracy against future fantasy outcomes.
- Measure trade utility against roster improvement, risk, and liquidity.

</details>

<details>
<summary><strong>Practical First Pass - prove the math before automating collection.</strong></summary>

- Start with manual or allowed valuation snapshots.
- Generate deterministic source comparison reports.
- Defer scraping, databases, and heavier models until repeated snapshots justify them.

</details>

</div>

**The through-line is to build a transparent, reproducible valuation benchmark before trusting any single chart, market feed, or model.**

</details>
<hr style="height: 3px; background: rgba(160, 160, 160, 0.35); border: 0; margin: 0.25rem 0;">
<details open>
<summary><big><big><big><strong>Work Items</strong></big></big></big></summary>

**Status:** 🅿️ Not Started | 🚧 In Progress | ✅ Done | ⏸️ Paused | ⛔ Blocked

<div style="margin-left: 1.25rem; padding-left: 1rem; border-left: 3px solid #777;">

<details>
<summary><big><strong>1. ✅ Create Project Scaffold</strong></big></summary>

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
      <td>Create package</td>
      <td style="white-space: nowrap;">✅ Done</td>
      <td style="white-space: nowrap;">-</td>
      <td style="white-space: nowrap;">2026-06-08</td>
      <td>Package exists under <code>src/ffvaluation</code>.</td>
    </tr>
    <tr>
      <td style="white-space: nowrap;">b</td>
      <td>Create source registry</td>
      <td style="white-space: nowrap;">✅ Done</td>
      <td style="white-space: nowrap;">-</td>
      <td style="white-space: nowrap;">2026-06-08</td>
      <td>Initial registry lives in <code>src/ffvaluation/sources/registry.py</code>.</td>
    </tr>
    <tr>
      <td style="white-space: nowrap;">c</td>
      <td>Create metric helpers</td>
      <td style="white-space: nowrap;">✅ Done</td>
      <td style="white-space: nowrap;">-</td>
      <td style="white-space: nowrap;">2026-06-08</td>
      <td>Basic comparison metrics live in <code>src/ffvaluation/evaluation/metrics.py</code>.</td>
    </tr>
    <tr>
      <td style="white-space: nowrap;">d</td>
      <td>Add README and tests</td>
      <td style="white-space: nowrap;">✅ Done</td>
      <td style="white-space: nowrap;">-</td>
      <td style="white-space: nowrap;">2026-06-08</td>
      <td>README and lightweight tests are in place.</td>
    </tr>
  </tbody>
</table>

> <details>
> <summary><strong>Design Notes</strong></summary>
>
> The initial scaffold should stay small and research-oriented. Avoid heavy framework choices until the data shape and first useful reports are clear.
>
> </details>

</details>
<hr style="height: 1px; background: rgba(160, 160, 160, 0.25); border: 0; margin: 0.25rem 0;">
<details>
<summary><big><strong>2. ✅ Lock League Format</strong></big></summary>

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
      <td>Set team count</td>
      <td style="white-space: nowrap;">✅ Done</td>
      <td style="white-space: nowrap;">-</td>
      <td style="white-space: nowrap;">2026-06-08</td>
      <td>Encoded in <code>DEFAULT_FORMAT</code>.</td>
    </tr>
    <tr>
      <td style="white-space: nowrap;">b</td>
      <td>Set superflex</td>
      <td style="white-space: nowrap;">✅ Done</td>
      <td style="white-space: nowrap;">-</td>
      <td style="white-space: nowrap;">2026-06-08</td>
      <td>Superflex is the default format assumption.</td>
    </tr>
    <tr>
      <td style="white-space: nowrap;">c</td>
      <td>Set PPR scoring</td>
      <td style="white-space: nowrap;">✅ Done</td>
      <td style="white-space: nowrap;">-</td>
      <td style="white-space: nowrap;">2026-06-08</td>
      <td><code>ppr=1.0</code>; this is not zero-PPR standard scoring.</td>
    </tr>
    <tr>
      <td style="white-space: nowrap;">d</td>
      <td>Set passing TD scoring</td>
      <td style="white-space: nowrap;">✅ Done</td>
      <td style="white-space: nowrap;">-</td>
      <td style="white-space: nowrap;">2026-06-08</td>
      <td>Encoded as <code>passing_touchdown_points=4.0</code>.</td>
    </tr>
    <tr>
      <td style="white-space: nowrap;">e</td>
      <td>Disable tight end premium</td>
      <td style="white-space: nowrap;">✅ Done</td>
      <td style="white-space: nowrap;">-</td>
      <td style="white-space: nowrap;">2026-06-08</td>
      <td>Encoded as <code>tight_end_premium=0.0</code>.</td>
    </tr>
  </tbody>
</table>

> <details>
> <summary><strong>Design Notes</strong></summary>
>
> Superflex and PPR materially change player values. Mixing 1QB, non-PPR, or TEP values into the first pass would make source comparisons noisy before we have enough data to model format adjustments.
>
> </details>

</details>
<hr style="height: 1px; background: rgba(160, 160, 160, 0.25); border: 0; margin: 0.25rem 0;">
<details>
<summary><big><strong>3. ✅ Narrow Initial Sources</strong></big></summary>

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
      <td>Add KeepTradeCut</td>
      <td style="white-space: nowrap;">✅ Done</td>
      <td style="white-space: nowrap;">-</td>
      <td style="white-space: nowrap;">2026-06-08</td>
      <td>First crowd-sentiment source.</td>
    </tr>
    <tr>
      <td style="white-space: nowrap;">b</td>
      <td>Add RosterAudit</td>
      <td style="white-space: nowrap;">✅ Done</td>
      <td style="white-space: nowrap;">-</td>
      <td style="white-space: nowrap;">2026-06-08</td>
      <td>First observed trade-market source.</td>
    </tr>
    <tr>
      <td style="white-space: nowrap;">c</td>
      <td>Defer other sources</td>
      <td style="white-space: nowrap;">✅ Done</td>
      <td style="white-space: nowrap;">-</td>
      <td style="white-space: nowrap;">2026-06-08</td>
      <td>FantasyCalc, FantasyPros, Sleeper, ADP, and other aggregators can be added later.</td>
    </tr>
  </tbody>
</table>

> <details>
> <summary><strong>Design Notes</strong></summary>
>
> KeepTradeCut and RosterAudit create a clean first contrast: what managers say they value versus what real trades imply they value. That disagreement is likely more useful than adding many sources before the evaluation loop exists.
>
> </details>

</details>
<hr style="height: 1px; background: rgba(160, 160, 160, 0.25); border: 0; margin: 0.25rem 0;">
<details>
<summary><big><strong>4. ✅ Define Snapshot Ingestion Format</strong></big></summary>

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
      <td>Define CSV schema</td>
      <td style="white-space: nowrap;">✅ Done</td>
      <td style="white-space: nowrap;">-</td>
      <td style="white-space: nowrap;">2026-06-08</td>
      <td>Required columns: <code>source</code>, <code>captured_at</code>, <code>season</code>, <code>week</code>, <code>player_id</code>, <code>player_name</code>, <code>position</code>, <code>team</code>, <code>rank</code>, <code>raw_value</code>.</td>
    </tr>
    <tr>
      <td style="white-space: nowrap;">b</td>
      <td>Add validation</td>
      <td style="white-space: nowrap;">✅ Done</td>
      <td style="white-space: nowrap;">-</td>
      <td style="white-space: nowrap;">2026-06-08</td>
      <td><code>load_manual_snapshot</code> validates columns, source names, player IDs, and basic types.</td>
    </tr>
    <tr>
      <td style="white-space: nowrap;">c</td>
      <td>Add sample fixture</td>
      <td style="white-space: nowrap;">✅ Done</td>
      <td style="white-space: nowrap;">-</td>
      <td style="white-space: nowrap;">2026-06-08</td>
      <td>Sample fixture exists at <code>tests/fixtures/manual_snapshot.csv</code>.</td>
    </tr>
  </tbody>
</table>

> <details>
> <summary><strong>Design Notes</strong></summary>
>
> Point-in-time values are not guaranteed from every source, so snapshots are a first-class asset. Raw capture time matters as much as the value itself.
>
> </details>

</details>
<hr style="height: 1px; background: rgba(160, 160, 160, 0.25); border: 0; margin: 0.25rem 0;">
<details open>
<summary><big><strong>5. 🚧 Build Source Comparison Report</strong></big></summary>

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
      <td>Normalize values</td>
      <td style="white-space: nowrap;">🅿️ Not Started</td>
      <td style="white-space: nowrap;">-</td>
      <td style="white-space: nowrap;">-</td>
      <td>Convert source-specific raw values to a comparable scale.</td>
    </tr>
    <tr>
      <td style="white-space: nowrap;">b</td>
      <td>Compare rank correlation</td>
      <td style="white-space: nowrap;">🅿️ Not Started</td>
      <td style="white-space: nowrap;">-</td>
      <td style="white-space: nowrap;">-</td>
      <td>Compare KeepTradeCut and RosterAudit ordering across shared players.</td>
    </tr>
    <tr>
      <td style="white-space: nowrap;">c</td>
      <td>Build disagreement table</td>
      <td style="white-space: nowrap;">🅿️ Not Started</td>
      <td style="white-space: nowrap;">-</td>
      <td style="white-space: nowrap;">-</td>
      <td>Surface largest player-level value gaps.</td>
    </tr>
    <tr>
      <td style="white-space: nowrap;">d</td>
      <td>Export comparison report</td>
      <td style="white-space: nowrap;">🅿️ Not Started</td>
      <td style="white-space: nowrap;">-</td>
      <td style="white-space: nowrap;">-</td>
      <td>Write CSV and Markdown output for manual review.</td>
    </tr>
  </tbody>
</table>

> <details>
> <summary><strong>Design Notes</strong></summary>
>
> This should be the next executable artifact. Keep it deterministic and file-based: read a manual snapshot CSV, generate a comparison table, and avoid introducing a database until repeated snapshots justify it.
>
> </details>

</details>
<hr style="height: 1px; background: rgba(160, 160, 160, 0.25); border: 0; margin: 0.25rem 0;">
<details>
<summary><big><strong>6. 🅿️ Add Outcome Evaluation</strong></big></summary>

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
      <td>Define outcome labels</td>
      <td style="white-space: nowrap;">🅿️ Not Started</td>
      <td style="white-space: nowrap;">-</td>
      <td style="white-space: nowrap;">-</td>
      <td>Choose the first forward-looking labels.</td>
    </tr>
    <tr>
      <td style="white-space: nowrap;">b</td>
      <td>Build forward targets</td>
      <td style="white-space: nowrap;">🅿️ Not Started</td>
      <td style="white-space: nowrap;">-</td>
      <td style="white-space: nowrap;">-</td>
      <td>Use only information after the snapshot date.</td>
    </tr>
    <tr>
      <td style="white-space: nowrap;">c</td>
      <td>Compare cohorts</td>
      <td style="white-space: nowrap;">🅿️ Not Started</td>
      <td style="white-space: nowrap;">-</td>
      <td style="white-space: nowrap;">-</td>
      <td>Compare by position and age bucket.</td>
    </tr>
  </tbody>
</table>

> <details>
> <summary><strong>Design Notes</strong></summary>
>
> Outcome evaluation should not leak future information into source snapshots. The safest first pass is explicit snapshot date to future window evaluation, even if the labels are simple.
>
> </details>

</details>
<hr style="height: 1px; background: rgba(160, 160, 160, 0.25); border: 0; margin: 0.25rem 0;">
<details>
<summary><big><strong>7. 🅿️ Build Blended Baseline</strong></big></summary>

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
      <td>Add equal blend</td>
      <td style="white-space: nowrap;">🅿️ Not Started</td>
      <td style="white-space: nowrap;">-</td>
      <td style="white-space: nowrap;">-</td>
      <td>Average normalized source values.</td>
    </tr>
    <tr>
      <td style="white-space: nowrap;">b</td>
      <td>Add recency blend</td>
      <td style="white-space: nowrap;">🅿️ Not Started</td>
      <td style="white-space: nowrap;">-</td>
      <td style="white-space: nowrap;">-</td>
      <td>Weight newer snapshots more heavily.</td>
    </tr>
    <tr>
      <td style="white-space: nowrap;">c</td>
      <td>Add disagreement blend</td>
      <td style="white-space: nowrap;">🅿️ Not Started</td>
      <td style="white-space: nowrap;">-</td>
      <td style="white-space: nowrap;">-</td>
      <td>Treat large source gaps as uncertainty.</td>
    </tr>
  </tbody>
</table>

> <details>
> <summary><strong>Design Notes</strong></summary>
>
> A transparent blend should come before heavier models. If a simple blend is not useful, a more complex model probably needs better labels rather than more machinery.
>
> </details>

</details>
<hr style="height: 1px; background: rgba(160, 160, 160, 0.25); border: 0; margin: 0.25rem 0;">
<details>
<summary><big><strong>8. 🅿️ Research Access Constraints</strong></big></summary>

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
      <td>Review terms</td>
      <td style="white-space: nowrap;">🅿️ Not Started</td>
      <td style="white-space: nowrap;">-</td>
      <td style="white-space: nowrap;">-</td>
      <td>Confirm allowed collection methods.</td>
    </tr>
    <tr>
      <td style="white-space: nowrap;">b</td>
      <td>Identify ingestion paths</td>
      <td style="white-space: nowrap;">🅿️ Not Started</td>
      <td style="white-space: nowrap;">-</td>
      <td style="white-space: nowrap;">-</td>
      <td>Prefer APIs, exports, or manual snapshots.</td>
    </tr>
    <tr>
      <td style="white-space: nowrap;">c</td>
      <td>Document access limits</td>
      <td style="white-space: nowrap;">🅿️ Not Started</td>
      <td style="white-space: nowrap;">-</td>
      <td style="white-space: nowrap;">-</td>
      <td>Record source-specific caveats.</td>
    </tr>
  </tbody>
</table>

> <details>
> <summary><strong>Design Notes</strong></summary>
>
> Automated collection should follow each source's allowed access paths. Until that is clear, manual snapshots are the safest way to keep research moving.
>
> </details>

</details>

</div>

</details>
<hr style="height: 3px; background: rgba(160, 160, 160, 0.35); border: 0; margin: 0.25rem 0;">
<details>
<summary><big><big><big><strong>Open Questions</strong></big></big></big></summary>

- Are we targeting dynasty first, redraft first, or maintaining both under the same 12-team superflex scoring assumptions?
- Do we want public-only free data, paid/licensed data, or both?
- Should the model optimize for trade market value or future production value first?
- What league platform matters most for outcome and trade labels: Sleeper, ESPN, Yahoo, or MFL?

</details>
<hr style="height: 3px; background: rgba(160, 160, 160, 0.35); border: 0; margin: 0.25rem 0;">
<details>
<summary><big><big><big><strong>Appendix A - Research Details</strong></big></big></big></summary>

<details>
<summary><strong>League Scope</strong></summary>

- 12 teams.
- Superflex.
- Full PPR scoring: 1 point per reception.
- 4-point passing touchdowns.
- No tight end premium.
- Otherwise common/default fantasy scoring assumptions, not zero-PPR "standard scoring."

Superflex changes quarterback scarcity enough that mixing 1QB and superflex values will corrupt source comparisons. PPR changes receiver, running back, and tight end replacement levels enough that non-PPR values should stay out. Tight end premium changes positional replacement levels again, so it stays out of scope until the base model is working.

</details>

<details>
<summary><strong>Research Thesis</strong></summary>

- KeepTradeCut may be strong at measuring dynasty community sentiment, liquidity, and the prices managers say they would pay.
- RosterAudit may be stronger at measuring observed trade-market clearing prices because its public materials describe values derived from real Sleeper trade data.
- KeepTradeCut higher than RosterAudit may mean crowd sentiment is richer than observed trade-market value.
- RosterAudit higher than KeepTradeCut may mean real managers are paying more than voters say.
- Large disagreement should trigger review before trusting either source.

</details>

<details>
<summary><strong>Evaluation Targets</strong></summary>

- Market accuracy: pairwise preference accuracy, rank correlation against observed trade market, calibration error for player-for-player and package trades, and error by position and age bucket.
- Production accuracy: Spearman rank correlation, mean absolute rank error, weighted error on top assets, points above replacement error, and hit rate for top-N finishes by position.
- Trade utility: simulated accepted-trade edge, forward value change after trade date, downside risk and drawdown, and liquidity-adjusted value.

</details>

</details>
<hr style="height: 3px; background: rgba(160, 160, 160, 0.35); border: 0; margin: 0.25rem 0;">
<details>
<summary><big><big><big><strong>Appendix B - Data And Modeling Notes</strong></big></big></big></summary>

<details>
<summary><strong>Data Model</strong></summary>

- Player: ID mappings across Sleeper, ESPN, FantasyPros, GSIS, and source-specific slugs; name, team, position, age, experience, draft capital.
- Source definition: name, URL, value type, supported formats, update frequency, access method, historical availability, terms/robots notes, and known biases.
- Valuation snapshot: source, timestamp, season, week, format, player, rank, raw value, and normalized value.
- Outcome snapshot: player, horizon, fantasy points, points above replacement, positional finish, games played, injury flag, and role/team changes.
- Trade observation: timestamp, league format, assets on both sides, platform, pick inclusion, and implied package values.

</details>

<details>
<summary><strong>Modeling Approach</strong></summary>

- Normalize ranks to percentile or z-score by source snapshot.
- Fit source value curves to a common scale while preserving top-end curvature.
- Store raw values so transformations stay auditable.
- Start with baselines: KeepTradeCut only, RosterAudit only, equal-weight consensus, recency-weighted consensus, and disagreement-aware consensus.
- Consider improved models later: ridge regression, gradient boosted trees, Bayesian model averaging, and pairwise ranking models.

</details>

</details>
