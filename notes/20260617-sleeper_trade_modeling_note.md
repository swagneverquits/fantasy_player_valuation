# Sleeper Trade Modeling Note

**Date:** 2026-06-17

This note is a plain-English math sketch for learning fantasy football asset values from completed Sleeper trades. The target setting is still narrow on purpose: 12-team dynasty PPR superflex leagues with no tight end premium.

The basic idea is simple:

> If two managers completed a trade, then the two packages were probably close enough in perceived value to make the deal happen.

Not every trade is fair. Not every manager is sharp. But across enough trades, the market should reveal a value curve.

## 1. What A Trade Gives Us

Suppose trade $t$ has two sides:

$$
A_t
$$

$$
B_t
$$

Here, $A_t$ is the package received by side A, and $B_t$ is the package received by side B. Each side is a package of assets. Assets can be players, rookie picks, or other tradeable objects Sleeper exposes.

The modeling assumption is:

$$
V(A_t) \approx V(B_t)
$$

where $V(\cdot)$ is the model's package-value function.

This does **not** mean every completed trade is perfectly fair. It means completed trades are noisy observations of market-clearing package values.

## 2. Linear Baseline

Start with the dumbest useful model.

Let each asset $i$ have a latent value:

$$
v_i
$$

For a package $P$, define package value as the sum of asset values:

$$
V(P) = \sum_{i \in P} v_i
$$

For trade $t$, the imbalance is:

$$
e_t = V(A_t) - V(B_t)
$$

The baseline objective is:

$$
\min_v \sum_{t \in T} e_t^2
$$

or equivalently:

$$
\min_v \sum_{t \in T} \left(V(A_t) - V(B_t)\right)^2
$$

This gives us a first-pass value system where real trades look as balanced as possible.

The problem: pure linear sums are probably wrong. Two useful assets often do not buy one elite asset, even if the chart says the sums match.

## 3. Priors

Some assets will have very few observations. If we let the model freely move every value, one weird trade can make a random player look massively overvalued.

So we start with a prior value:

$$
p_i
$$

That prior can come from RosterAudit, KeepTradeCut, an average of sources, or a previous model run.

Then we penalize moving too far from the prior:

$$
\min_v \left[ \sum_{t \in T} \left(V(A_t) - V(B_t)\right)^2 + \lambda \sum_i (v_i - p_i)^2 \right]
$$

Here:

- $v_i$ is the learned value.
- $p_i$ is the prior value.
- $\lambda$ is the prior-strength parameter.

High prior strength: values stay close to the prior.

Low prior strength: trades move values more aggressively.

A better version can make the penalty depend on observation count:

$$
\lambda_i \left(v_i - p_i\right)^2
$$

where lightly traded assets get stronger shrinkage and heavily traded assets get more freedom.

## 4. Why Linear Package Value Is Not Enough

Consider a trade where one side gets an elite player and the other side gets two good players.

A linear model says:

$$
V(P) = v_1 + v_2
$$

But dynasty markets often behave more like:

The combined package can be worth less than the raw sum of its parts.

because:

- elite players are scarce;
- roster spots have opportunity cost;
- consolidation is valuable;
- secondary pieces are less liquid;
- managers pay a premium to turn depth into lineup advantage.

So we need a package function, not just an asset function.

## 5. Discounted Package Function

Sort the assets in a package by standalone value:

$$
v_{(1)} \ge v_{(2)} \ge v_{(3)} \ge \cdots
$$

Then define package value as:

$$
V(P) = v_{(1)} + d_2 v_{(2)} + d_3 v_{(3)} + \cdots
$$

where:

$$
1 \ge d_2 \ge d_3 \ge \cdots \ge 0
$$

The best asset keeps full value. Secondary assets are discounted.

Example:

$$
V(P) = v_{(1)} + 0.75v_{(2)} + 0.55v_{(3)}
$$

This lets the model learn that the second and third pieces in a package do not contribute at full sticker price.

The full objective becomes:

$$
\min_{v,d} \left[ \sum_{t \in T} \left(V_d(A_t) - V_d(B_t)\right)^2 + \lambda \sum_i (v_i - p_i)^2 \right]
$$

where $V_d(\cdot)$ is the discounted package function.

## 6. Roster-Spot Penalty

A 3-for-1 trade does not only exchange values. It also changes roster pressure.

If a side receives more assets than it sends, it may need to cut players or use extra bench slots.

Let:

$$
n(P)
$$

Here, $n(P)$ is the number of assets in package $P$.

For a trade side, define net incoming roster pressure:

$$
r(A_t, B_t) = \max(0, n(A_t) - n(B_t))
$$

Then package value can include a roster penalty:

$$
V(P) = v_{(1)} + d_2v_{(2)} + d_3v_{(3)} + \cdots - \rho \cdot r
$$

where $\rho$ is the learned cost of an extra roster spot.

This gives the model a way to explain why:

> Three okay players are often not equivalent to one elite player.

even when the public chart sum looks close.

## 7. Robust Loss

Some trades are weird. Some are bad. Some involve context we cannot observe.

Squared error gives outliers a lot of influence:

$$
L(e_t) = e_t^2
$$

A robust alternative is absolute error:

$$
L(e_t) = |e_t|
$$

Or Huber loss. For small errors:

$$
L_\delta(e_t) = \frac{1}{2}e_t^2
$$

For large errors:

$$
L_\delta(e_t) = \delta\left(|e_t| - \frac{1}{2}\delta\right)
$$

Then the objective becomes:

$$
\min_\theta \left[ \sum_{t \in T} L\left(V_\theta(A_t) - V_\theta(B_t)\right) + R(\theta) \right]
$$

where $\theta$ includes asset values and package parameters, and $R(\theta)$ is regularization.

## 8. Revealed Preference Version

Another way to frame trades is not "both sides are exactly equal." It is:

> Both managers preferred, or at least accepted, the package they received.

That can become a probabilistic model.

Let:

$$
\Delta_t = V(A_t) - V(B_t)
$$

A simple likelihood could say that balanced trades are more probable when $\Delta_t$ is near zero:

$$
P(t) \propto \exp(-|\Delta_t|)
$$

Or:

$$
P(t) \propto \exp(-\Delta_t^2)
$$

This is basically the same instinct as balance-error minimization, but with a probabilistic interpretation.

## 9. Time

Player values change. A trade from March and a trade from October may imply different values.

The simplest model ignores time:

$$
v_i(t) = v_i
$$

A more realistic model lets values move by date:

$$
v_i(t) = v_i^0 + f_i(t)
$$

But that is much harder.

Practical first step:

- fit season-level values;
- record trade date;
- evaluate errors over time;
- only add time-varying values if stale trades visibly hurt fit.

## 10. Evaluation

The model should be judged on held-out trades.

For held-out trade $t$, compute:

$$
\hat{e}_t = V(A_t) - V(B_t)
$$

Useful metrics:

Mean absolute error:

$$
\mathrm{MAE} = \frac{1}{|T|} \sum_{t \in T} |\hat{e}_t|
$$

Root mean squared error:

$$
\mathrm{RMSE} = \sqrt{\frac{1}{|T|} \sum_{t \in T} \hat{e}_t^2}
$$

Also inspect:

- error by package size;
- error by position;
- error by age bucket;
- error by asset tier;
- error by consolidation direction;
- rank stability across bootstrap samples.

## 11. What The Model Should Output

The model should produce:

- asset values;
- prior values;
- learned movement from prior;
- observation counts;
- uncertainty or stability scores;
- package discount parameters;
- trade residuals;
- source comparisons against RosterAudit and KeepTradeCut.

The best output is not just a ranking table. It is a ranking table plus an explanation for why values moved.

## 12. Open Questions

- How much should obviously one-sided trades count?
- Should package discounts differ by position?
- Should pick values be learned separately by season and round?
- How should future rookie picks be valued before draft order is known?
- Should the model estimate uncertainty directly?
- Should player values be season-level, date-level, or both?
- Should public sources be priors, validation targets, or both?
- How much should liquidity matter separately from value?

## 13. Working Mental Model

The core modeling stack is:

> Observed trades -> package balance objective -> asset values -> package discounts -> diagnostics

The first useful model should probably be:

$$
\min_{v,d} \left[ \sum_{t \in T} L\left(V_d(A_t) - V_d(B_t)\right) + \lambda \sum_i (v_i - p_i)^2 \right]
$$

with:

$$
V_d(P) = v_{(1)} + d_2v_{(2)} + d_3v_{(3)} + \cdots
$$

That is enough to test the most important question:

> Can real Sleeper trades recover a sensible value curve, especially at the elite consolidation end?

## Appendix A. Valuing Package Deals

The package-deal question is central:

> How should the model think about Player A for Player B + Player C?

The cleanest starting point is still linearity.

$$
V(P) = \sum_{i \in P} v_i
$$

Linearity is attractive because it makes every trade easy to score. Add up the assets on one side, add up the assets on the other side, and compare the totals.

For a trade like:

> Player A for Player B + Player C

the model says:

$$
v_A \approx v_B + v_C
$$

That is mathematically convenient and probably the right baseline. It also makes model output easy to explain: every asset has one value, and package value is just the sum.

The concern is that dynasty markets may not be fully linear. A manager often prefers one elite starter over two lesser starters, even if the two lesser players have the same summed public value.

That means the observed market may behave more like:

$$
v_A \approx v_B + v_C - h(B, C)
$$

where $h(B, C)$ is a package discount.

The discount should probably be zero in the first model. We only add it if the linear model repeatedly struggles with consolidation trades.

Useful ways to think about optional package discounts:

- **Rank discount:** the best asset keeps full value, and the second or third asset gets a learned haircut.
- **Roster-spot discount:** each extra incoming asset has a fixed cost because it consumes a roster spot.
- **Concentration discount:** packages with value spread across many assets are worth less than packages concentrated in one elite asset.
- **Tier discount:** depth pieces below a certain lineup-value tier contribute less than their raw values.

The most practical linear-plus-discount version is:

$$
V(P) = \sum_{i \in P} v_i - \rho \cdot \max(0, n(P) - 1)
$$

This keeps package value mostly additive, while giving the model one simple way to account for the cost of turning one roster slot into two or three.

A more flexible version is:

$$
V(P) = v_{(1)} + d_2v_{(2)} + d_3v_{(3)}
$$

This is still easy to explain, but it is less linear: the value of an asset depends on whether it is the best, second-best, or third-best asset in the package.

The modeling order should probably be:

1. Fit pure linear values.
2. Inspect errors on 1-for-2 and 1-for-3 trades.
3. Add the smallest package discount that materially improves held-out fit.
4. Keep the discount interpretable enough that a trade calculator can explain it.

The guiding principle:

> Prefer linear package values until the data proves that package shape matters.
