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

### 1. A benchmark has a minimum N, and below it there is no benchmark

With one customer, "the peer average" is that customer. With three, a single
outlier moves it enough to be wrong. Publishing a comparison built from too few
books is the generic-advice problem wearing a better outfit, and it is worse
than the honest version because it looks specific.

**Proposal: `MIN_PEERS = 8` distinct organisations per (industry, parameter)
before a peer prior or a benchmark is shown at all.** Below it the pack prior
stands and the UI says "not enough comparable books yet", the same way the
track record already refuses to report accuracy below 20 resolved decisions.

The number is arguable. The rule that it exists is not.

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
| `snapshot_id` | provenance and the ability to withdraw |

Note what is absent: no counterparty names, no amounts, no dates, no invoice or
PO rows. The pooled table cannot reconstruct a book because it never contained
one. That property should be structural, enforced by the table's columns, not by
a query being written carefully.

## The four deliverables

| CP | Deliverable | Done means |
|---|---|---|
| **B1** | `benchmarks/contributions.py` + table | Every assessment writes one row per estimated parameter. Withdrawal deletes them. |
| **B2** | `benchmarks/pool.py` — empirical prior | Given a bucket, returns a pooled prior triple or `None` below `MIN_PEERS`. Property test: never returns a value derived from fewer than `MIN_PEERS` orgs. |
| **B3** | Wire into `estimation/` as `PriorSource` | Zero pooled data reproduces today's output **byte for byte**. That is the regression guarantee, same as v3's. |
| **B4** | Surface it | Dashboard shows the customer's value against the peer distribution, provenance reads `peer`, methodology page explains empirical Bayes and states `MIN_PEERS`. |

## The calibration loop, which is the actual moat

`outcomes.py` already stores the full predicted distribution against realized
outcomes and refuses to claim accuracy below 20 resolved decisions. That is the
feedback signal, and it is worth more than the benchmark.

Once there are resolved outcomes, **interval coverage** is measurable: if the
80% interval contains the truth 80% of the time, the model is calibrated. If it
contains it 55% of the time, the model is overconfident and the pack priors are
wrong in a way that can be corrected.

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
