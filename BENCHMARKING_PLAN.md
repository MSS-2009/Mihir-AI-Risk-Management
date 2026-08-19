# The benchmarking and model-improvement layer

Plan only. No code until this is agreed.

## What is actually being asked for

Two things that sound like one:

1. **Benchmarking** — a customer's numbers compared against comparable companies
   rather than against a published estimate.
2. **Model improvement** — each customer's data making every future customer's
   calculation more accurate.

They are the same mechanism, which is convenient and not obvious. Our estimator
already shrinks a customer's measured rate toward a **prior**. Today that prior
is expert judgment from the industry pack. The whole layer is: replace the
authored prior with one **estimated from the customer pool**, and expose the
pool's spread as the benchmark.

That is empirical Bayes. It is a hundred years old, it is defensible in front of
a technical evaluator, and it is the only version of this that does not require
inventing a new statistical story.

### What must be pooled, and what must never be

**Pool raw sufficient statistics. Never pool posterior means.**

This was wrong in the first draft and it is the kind of wrong that would have
survived to production looking healthy. Every organisation's posterior is
already shrunk toward the authored pack prior, so averaging posteriors averages
numbers that partly contain the prior. The "empirical" prior then echoes the
authored one back wearing a peer badge.

Simulated against a true population rate of 1.10 where the authored prior guesses
0.458, wrong by 58%:

| peers | years each | pooled from posterior means | error | pooled from raw statistics | error |
|---|---|---|---|---|---|
| 8 | 1.0 | 0.617 | **-43.9%** | 1.096 | -0.4% |
| 8 | 3.0 | 0.780 | -29.1% | 1.102 | +0.2% |
| 60 | 3.0 | 0.777 | -29.4% | 1.096 | -0.4% |
| 200 | 3.0 | 0.779 | -29.2% | 1.100 | -0.0% |
| 1000 | 5.0 | 0.859 | **-21.9%** | 1.100 | 0.0% |

The last two rows are the whole argument. **A thousand peers is as biased as
eight.** This is bias, not noise, so it never averages out: what erodes it is
per-firm exposure, which weakens each firm's shrinkage, not the number of firms.
We would accumulate customers for two years, watch the pool grow, and the number
would stay wrong in the same place while looking more authoritative every month.

The fix costs nothing, because the contribution row already carries
`observed_events` and `observed_years`. For a Gamma-Poisson model the pooled
maximum-likelihood rate is **total events divided by total exposure**, which
lands within 1% at every size above.

The same defect breaks the benchmark itself. Posterior means are shrunk toward
each other, so their spread understates real between-company variation by a
steady **34%** in these runs. Every customer would be told they sit further from
their peer distribution than they actually do.

**Consequence for the interface: the pooled mean and the pooled spread are not
equally trustworthy and must not ship together.** Fitting the negative-binomial
marginal likelihood recovers the population mean well, but the shape parameter
governing between-company spread is unstable on small pools. Estimate the mean
from raw statistics early; treat the spread as needing substantially more
evidence, and until it has that, show a **peer average** rather than a peer
distribution.

## Why this fits without re-architecting

`estimation/frequency.py` already computes a Gamma-Poisson posterior from
`(prior_mean, prior_strength_years, observed_events, observed_years)`. The prior
is the only input that comes from the pack rather than the customer.

So the change is narrow: a `PriorSource` that returns either the pack's authored
triple or a pooled empirical one, with everything downstream unchanged. The
provenance field gains a third value alongside `measured` / `blended` /
`prior`: **`peer`**.

No engine changes. No pack changes. No new simulation path.

## The three hard constraints

### 1. Two floors, not one, and below either there is no benchmark

With one customer, "the peer average" is that customer. With three, a single
outlier moves it enough to be wrong. Publishing a comparison built from too few
books is the generic-advice problem wearing a better outfit, and it is worse
than the honest version because it looks specific.

A single count is the wrong gate, because it measures the wrong thing. Eight
organisations with three months of history each is far weaker evidence than
eight with five years, and one threshold cannot tell them apart. There are
really two requirements doing two different jobs:

| gate | serves | proposal |
|---|---|---|
| `MIN_PEER_ORGS` | **privacy** (k-anonymity) | 8 distinct organisations |
| `MIN_POOLED_YEARS` | **statistical validity** | a floor on summed exposure, and on total observed events |

**Both must pass.** Gating on organisations alone lets the pool switch on with
eight nearly-empty books; gating on exposure alone would let three chatty
customers constitute a "peer set". The methodology page states both numbers.

Below either gate the pack prior stands and the UI says "not enough comparable
books yet", the same way the track record already refuses to report accuracy
below 20 resolved decisions.

The numbers are arguable. That there are two of them is not.

### 2. Only pooled statistics may leave a tenant, ever

A benchmark that lets customer B infer customer A's vendor failure rate is a
data breach with a chart on top. Two mechanisms:

- **k-anonymity floor.** No statistic is computed over fewer than `MIN_PEERS`
  organisations, and no bucket (industry x size band) is reported below it.
- **Contribution capping.** One organisation's contribution to a pooled estimate
  is capped, so a single extreme book cannot be reverse-engineered from a shift
  in the published mean. This also happens to make the estimate robust, which is
  the usual sign that a privacy constraint was the right shape.

Differential privacy proper is the next step up and I would not start there: the
noise it adds is hard to explain to a CFO, and the k-anonymity floor plus
capping covers the realistic attack at our scale.

### 3. The right to do this has to exist before the first customer

Using aggregated customer data to improve the model is a **terms of service and
DPA question, not an engineering one**. It must say so in writing, in plain
language, before the first book is ingested. Retrofitting consent after the fact
is the thing that ends companies, and an automotive prospect's legal review will
ask this question specifically.

**Recommendation: opt-out, stated prominently, with the aggregate-only guarantee
in the same sentence.** An org row gains `contributes_to_benchmarks bool`, and
the pooling query honours it. An opted-out customer still *receives* benchmarks;
they just do not feed them. That asymmetry is defensible and generous, and it
avoids the death spiral where nobody contributes.

## What gets pooled

Not raw records. Never raw records. What crosses the boundary is one row per
(organisation, parameter, snapshot):

| field | why |
|---|---|
| `industry_pack` | the bucket |
| `parameter_key` | e.g. `third_party_failure.frequency` |
| `posterior_mean` | the estimate |
| `observed_events`, `observed_years` | so the pool can weight by evidence |
| `size_band` | revenue bucket, coarse: a $40M and a $900M distributor are not peers |
| `pool_version` | which pool produced a prior, so a past run stays explainable |
| `snapshot_id` | provenance and the ability to withdraw |

Note what is absent: no counterparty names, no amounts, no dates, no invoice or
PO rows. The pooled table cannot reconstruct a book because it never contained
one. That property should be structural, enforced by the table's columns, not by
a query being written carefully.

## Buckets are hierarchical, not partitioned

Five industries times several size bands times eleven parameters is a great many
buckets, and requiring each to independently clear the floor would need dozens of
customers per industry before anything lit up at all. The layer would sit dark
far longer than the data actually justifies.

So the levels nest rather than divide:

1. **Industry level.** As soon as (industry, parameter) clears both gates, the
   pooled prior replaces the authored one for everybody in that industry.
2. **Size band refines it.** A band's own statistics adjust the industry prior
   only once that band independently clears both gates. Until then a band
   inherits the industry number rather than falling back to the authored prior.

Same machinery, same floors, never violated. The benchmark simply switches on
far sooner, and degrades to a coarser but still empirical peer set instead of
degrading all the way back to expert judgment.

## A pooled prior must not break reproducibility

Two guarantees collide, and the collision is silent. B1 says withdrawal deletes
an organisation's contribution rows. Version 3 guarantees every past assessment
is exactly reproducible from its snapshot. But the pooled prior is an input to
the assessment, so when a peer withdraws, the pool shifts and every assessment
that used it quietly stops reproducing.

**The assessment envelope records the prior it actually used**, with a pool
version identifier and a hash, alongside the seed and the model version. A past
run then stays explainable after the pool moves underneath it.

This costs one column and buys a real feature. "Why did my number change" can
now distinguish **your data changed** from **your peer set changed**, which are
different facts a CFO would act on differently, and which the monitoring layer
already insists every change carries a cause for.

## The four deliverables

| CP | Deliverable | Done means |
|---|---|---|
| **B1** | `benchmarks/contributions.py` + table | Every assessment writes one row per estimated parameter. Withdrawal deletes them. |
| **B2** | `benchmarks/pool.py` — empirical prior | Pools **raw sufficient statistics**, total events over total exposure, never posterior means. Returns a prior or `None` below either floor. Property tests: never derived from fewer than `MIN_PEER_ORGS`, and a regression asserting the estimator recovers a planted population rate within a few percent at 8, 60 and 1000 peers, since that sweep is exactly what exposed the bias. |
| **B3** | Wire into `estimation/` as `PriorSource` | Zero pooled data reproduces today's output **byte for byte**. That is the regression guarantee, same as v3's. The envelope records the pool version and hash of the prior actually used, so a past run stays reproducible after the pool moves. |
| **B4** | Surface it | Provenance reads `peer`. Dashboard shows a peer **average** first; the peer **distribution** only once the spread parameter has enough evidence to be stable. Methodology page explains empirical Bayes, states both floors, and shows coverage with its confidence interval. |

## The calibration loop, which is the actual moat

`outcomes.py` already stores the full predicted distribution against realized
outcomes and refuses to claim accuracy below 20 resolved decisions. That is the
feedback signal, and it is worth more than the benchmark.

Once there are resolved outcomes, **interval coverage** is measurable: if the
80% interval contains the truth 80% of the time, the model is calibrated. If it
contains it 55% of the time, the model is overconfident and the pack priors are
wrong in a way that can be corrected.

**Coverage is itself an estimate and must be reported with its own interval.**
At the 20-resolved-decision floor, an observed 80% coverage is consistent with a
true coverage anywhere from roughly 59% to 93%. That is wide enough to detect
gross miscalibration, which is genuinely useful, and nowhere near enough to
claim the model is well calibrated. Narrowing it to about nine points takes on
the order of three hundred resolved decisions.

So the threshold for **reporting** coverage and the threshold for **claiming
calibration** are two different numbers, and the interface shows the interval
rather than the point. There is a pleasing recursion worth making explicit to a
customer: the product that prices the uncertainty in its own model prices the
uncertainty in its own report card too.

**This is the thing no competitor can copy**, because it requires customers who
took decisions and outcomes that resolved. A benchmark is a data-network effect.
Calibration is a proof of correctness. The second one is what wins a technical
evaluation.

## What I would explicitly not build

- **Training a model on customer data** in the machine-learning sense. There is
  no supervised target here, the data is small and slow, and it would replace an
  explainable Bayesian update with something a CFO cannot be walked through. The
  explainability is the product.
- **Cross-industry pooling.** A wealth manager's client churn rate says nothing
  about a distributor's vendor failure rate. Pooling them would improve the
  statistics and destroy the meaning.
- **A benchmark on magnitude.** Frequencies are measurable from finance data;
  loss magnitudes largely are not, and pooling estimates that are all derived
  from the same published prior would manufacture a false consensus. Frequencies
  first, and say so.

## Sequencing against reality

There are zero customers, so there is no pool. B1 is still worth building first
and immediately: contributions accumulate from the first assessment, and the
pool cannot be backfilled from books we did not record. B2 through B4 sit dormant
and correct until `MIN_PEERS` is reached.

The honest framing for a prospect: *"your numbers are estimated from your own
history against a published prior today, and against comparable books once there
are enough of them. Here is the threshold, and here is what you would see."*
That is a roadmap a CFO can believe, and it beats claiming a peer set we do not
have.


## What changed in this revision

Five corrections, one of which was a real defect rather than a refinement.

**Pooling posterior means was wrong.** It contaminates the empirical prior with
the authored one and the bias does not shrink with more customers. Verified
independently at 200 and 1000 peers, where the error holds at -29% and -22%.
Pool raw sufficient statistics instead. The spread understatement this also
causes is why the peer average and the peer distribution now ship separately.

**One floor became two**, because organisation count serves privacy and pooled
exposure serves validity, and a single number cannot do both jobs.

**Buckets became hierarchical**, so the industry level lights up as soon as it
clears the floors and size bands refine it later, instead of every cell waiting
alone in the dark.

**The envelope records the prior it used**, because a withdrawing peer would
otherwise silently break the reproducibility guarantee v3 makes.

**Calibration is reported with its own interval**, and the bar for claiming
calibration sits above the bar for reporting it.
