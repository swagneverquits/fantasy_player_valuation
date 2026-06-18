# Sleeper Trade Modeling Note

**Date:** 2026-06-17

<details open>
<summary><big><big><big><strong>Motivation</strong></big></big></big></summary>

This note frames the modeling logic for learning fantasy football asset values from completed Sleeper trades in 12-team dynasty PPR superflex leagues with no tight end premium.

<div style="margin-left: 1.25rem; padding-left: 1rem; border-left: 3px solid #777;">

<details>
<summary><strong>Trade Balance - infer value from packages managers actually accepted.</strong></summary>

- Treat each completed trade as a noisy statement that two asset packages were close enough to exchange.
- Learn player and pick values that make observed trade sides look plausibly balanced.
- Keep league-format filters tight so the first model is not explaining settings noise.

</details>

<details>
<summary><strong>Package Shape - stop pretending every asset adds linearly.</strong></summary>

- Model consolidation and diversification explicitly.
- Let secondary assets contribute less than their standalone value when bundled.
- Penalize roster-slot pressure where multi-asset packages consume scarce bench space.

</details>

<details>
<summary><strong>Inspectable Complexity - earn every fancy term.</strong></summary>

- Start with a transparent baseline objective.
- Add package functions, priors, and hierarchy only when diagnostics justify them.
- Preserve enough intermediate artifacts to explain why any player value moved.

</details>

</div>

**The through-line is to turn completed trades into a market-implied value curve without hiding the assumptions that make the curve possible.**

</details>
<hr style="height: 3px; background: rgba(160, 160, 160, 0.35); border: 0; margin: 0.25rem 0;">
<details open>
<summary><big><big><big><strong>Modeling Framework</strong></big></big></big></summary>

<div style="margin-left: 1.25rem; padding-left: 1rem; border-left: 3px solid #777;">

<details open>
<summary><big><strong>1. Baseline Balance Model</strong></big></summary>

- Represent each completed trade as two packages: side A and side B.
- Assign every asset a latent scalar value.
- Define first-pass package value as the sum of included asset values.
- Minimize package imbalance across completed trades.
- Regularize learned values toward priors so sparse assets do not overreact to one trade.

> <details>
> <summary><strong>Design Notes</strong></summary>
>
> The baseline is intentionally simple. Its job is to expose data problems, weak priors, and obvious nonlinearity before we start adding package math.
>
> </details>

</details>
<hr style="height: 1px; background: rgba(160, 160, 160, 0.25); border: 0; margin: 0.25rem 0;">
<details open>
<summary><big><strong>2. Package Value Function</strong></big></summary>

- Sort package assets by estimated standalone value.
- Preserve most or all value for the top asset.
- Apply learned discounts to secondary assets.
- Add optional roster-slot penalties for package sides that add more bodies than they remove.
- Estimate package-function parameters jointly with asset values.

> <details>
> <summary><strong>Design Notes</strong></summary>
>
> This is the core move. A two-for-one trade is not a spreadsheet sum; managers pay for consolidation, roster flexibility, and access to scarce elite players.
>
> </details>

</details>
<hr style="height: 1px; background: rgba(160, 160, 160, 0.25); border: 0; margin: 0.25rem 0;">
<details open>
<summary><big><strong>3. Priors And Regularization</strong></big></summary>

- Seed player and pick values from a stable public or internal prior.
- Penalize large moves away from priors when trade evidence is thin.
- Let high-volume assets move more freely than rarely traded assets.
- Consider position-specific shrinkage so sparse positions do not drift incoherently.
- Track prior value, learned value, and movement separately for explainability.

> <details>
> <summary><strong>Design Notes</strong></summary>
>
> Priors are not a crutch; they are what keeps a noisy market model from hallucinating certainty from thin trade samples.
>
> </details>

</details>
<hr style="height: 1px; background: rgba(160, 160, 160, 0.25); border: 0; margin: 0.25rem 0;">
<details open>
<summary><big><strong>4. Evaluation Loop</strong></big></summary>

- Hold out completed trades and measure package-balance error.
- Bootstrap trades to measure value stability.
- Compare ranks and tiers against RosterAudit and KeepTradeCut snapshots.
- Inspect error by position, age bucket, asset tier, and package size.
- Write case studies for the largest disagreements with public sources.

> <details>
> <summary><strong>Design Notes</strong></summary>
>
> Agreement with public charts is useful, but not the final target. The model should win by explaining observed trades, especially where public sources disagree.
>
> </details>

</details>

</div>

</details>
<hr style="height: 3px; background: rgba(160, 160, 160, 0.35); border: 0; margin: 0.25rem 0;">
<details open>
<summary><big><big><big><strong>Candidate Objectives</strong></big></big></big></summary>

<div style="margin-left: 1.25rem; padding-left: 1rem; border-left: 3px solid #777;">

<details>
<summary><strong>Squared Balance Error</strong></summary>

- Minimize squared difference between side A package value and side B package value.
- Simple, inspectable, and easy to debug.
- Sensitive to outlier trades and lopsided league behavior.

</details>

<details>
<summary><strong>Robust Balance Error</strong></summary>

- Use absolute, Huber, or winsorized losses to reduce outlier influence.
- Better suited for public leagues with uneven manager skill.
- Still keeps the central trade-balance interpretation.

</details>

<details>
<summary><strong>Pairwise Revealed Preference</strong></summary>

- Treat the accepted side as at least plausible relative to the given-away side.
- Model trade acceptance as a probability instead of forcing exact equality.
- Useful if many trades are intentionally one-sided, speculative, or deadline-driven.

</details>

</div>

</details>
<hr style="height: 3px; background: rgba(160, 160, 160, 0.35); border: 0; margin: 0.25rem 0;">
<details open>
<summary><big><big><big><strong>Open Questions</strong></big></big></big></summary>

- How much should one-sided trades influence market value versus being treated as noise?
- Should package discounts depend on league size, roster size, or starting lineup shape?
- Should player values be static within a season, time-indexed by transaction date, or both?
- How should future rookie picks be valued before draft order is known?
- What minimum trade count should an asset need before it can move materially away from its prior?
- Should the model optimize for trade-market value, future production value, or a deliberately separate utility score?

</details>
<hr style="height: 3px; background: rgba(160, 160, 160, 0.35); border: 0; margin: 0.25rem 0;">
<details>
<summary><big><big><big><strong>Appendix A - Minimal Mathematical Sketch</strong></big></big></big></summary>

<details>
<summary><strong>Linear Baseline</strong></summary>

- Let each asset have value <code>v_i</code>.
- Let a package <code>P</code> contain assets <code>i in P</code>.
- Define <code>V(P) = sum(v_i)</code>.
- For each trade, minimize <code>loss(V(A), V(B))</code>.
- Add prior penalty <code>lambda * sum((v_i - prior_i)^2)</code>.

</details>

<details>
<summary><strong>Discounted Package Function</strong></summary>

- Sort package values from highest to lowest.
- Define <code>V(P) = v_1 + d_2*v_2 + d_3*v_3 + ...</code>.
- Constrain discounts so <code>1 >= d_2 >= d_3 >= ... >= 0</code>.
- Add a roster penalty when one side receives more assets than it sends.
- Learn discounts from held-out trade fit, not by hand-tuning chart vibes.

</details>

</details>
<hr style="height: 3px; background: rgba(160, 160, 160, 0.35); border: 0; margin: 0.25rem 0;">
<details>
<summary><big><big><big><strong>Appendix B - Model Artifacts</strong></big></big></big></summary>

<details>
<summary><strong>Expected Outputs</strong></summary>

- Asset value table with prior value, learned value, movement, and observation count.
- Pick value table by season, round, and original owner context when available.
- Trade fit table with predicted side values and residuals.
- Package diagnostics by package size and consolidation direction.
- Source comparison report against RosterAudit and KeepTradeCut.

</details>

<details>
<summary><strong>Candidate Paths</strong></summary>

- Store processed trade modeling datasets under <code>data/processed/sleeper/trade_value_model/</code>.
- Store fitted model outputs under <code>data/processed/sleeper/trade_value_model/models/</code>.
- Store diagnostics under <code>data/processed/sleeper/trade_value_model/reports/</code>.
- Store scratch experiments under <code>data/scratch/sleeper/modeling/</code>.

</details>

</details>
