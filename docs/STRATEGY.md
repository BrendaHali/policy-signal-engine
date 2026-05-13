# Strategy

## Position

A signal-based outbound motion for a state policy intelligence product. The system converts statehouse activity into a daily queue of high-relevance, account-specific outbound touches, sized to AE capacity and tied to the regulatory exposure the prospect already cares about.

The product is intent intelligence on legislative motion. The strategy is to be the first inbound the prospect receives on the bill that lands in their compliance team's inbox the same week.

## Product context

The motion targets the Enterprise tier of a modern policy intelligence platform: all-50-state monitoring, industry-tuned keyword alerts, hearing transcripts, aggregated dashboards, dedicated account manager. The free or low-tier product (daily statehouse coverage with push alerts) is self-serve and out of scope. The mid-tier (Pro: bill tracking, multi-state monitoring) is inside-sales. Enterprise is field sales with an AE, a sales engineer, and an executive sponsor.

The pitch the system creates is structured because the prospect is already inside the problem. Name the bill, name the specific operational pain, name the manual alternative, name the platform's answer, propose a small next step. The canonical pitch script and the per-lane talk tracks (urgent, top-tier, bulk) live in [`MOTION.md`](MOTION.md). What follows here is the strategy that frames the motion.

## ICP

| Tier | Profile | Why they buy |
|---|---|---|
| Tier 1 | Fortune 1000 regulated operators with multi-state footprints (insurance carriers, banks, health plans, utilities, telecom, large retail) | Each new state law translates directly into compliance, product, or pricing work. They have a Government Affairs function with a budget and a buying motion. |
| Tier 2 | Series C+ companies with regulatory exposure in two or more states | Scaling fast enough that policy uncertainty becomes a board-level item but lacking dedicated policy intelligence infrastructure. |
| Tier 3 | Regulated mid-market ($100M-$1B revenue) in industries where state-level rules dominate (cannabis, fintech, EdTech, climate) | High exposure-per-dollar-of-revenue. Often buying their first policy intelligence tool. |

**Buyer:** VP / Head of Government Affairs, Director of Public Policy, Chief Compliance Officer.

**Champion:** Policy Intelligence Lead, Senior Government Affairs Manager, Regulatory Affairs Director. The person who reads bills for a living.

**Disqualifiers:** Single-state operators. Pure-play federal advocacy shops. Companies with no regulatory exposure in their core product (e.g., direct-to-consumer e-commerce with no labeling, packaging, or sales-tax surface area).

## Signal hypothesis

State legislative activity is a four-to-six-week leading indicator of B2B intent for policy intelligence. The traditional intent stack (G2, Bombora, 6sense) detects search behavior and content engagement. Both are lagging signals: by the time a Government Affairs lead is searching "policy intelligence platform comparison," they have already framed the problem internally and built a shortlist.

A bill that names a target account's industry, advances in committee, or moves to floor action triggers the prospect's compliance and policy teams immediately. The buying conversation begins in those rooms, not in the search bar. The system catches the signal at the source.

## Motion

A signal-triggered, AE-led outbound motion supported by automated drafting and per-vertical sequence enrollment. Three lanes:

| Lane | Trigger | Action | Owner |
|---|---|---|---|
| Urgent | Bill at urgency 5 (signed, on the governor's desk, scheduled for floor vote) hits an account with state and industry overlap | Slack page to the account owner with the bill, the topic summary, and a one-line context | AE responds same-day, frames the conversation around the regulatory event |
| Top-tier | Score ≥ 0.8, account tier ≤ 2 | HubSpot task with a fully drafted three-part briefing (why now, why this account, suggested open) | AE adapts and sends within 48 hours |
| Bulk | Score 0.6–0.8 across the rest of the book | Sequence enrollment: vertical campaign nurture, drafted per pair | Marketing-owned cadence; AE picks up on engagement |

The system does not send on the AE's behalf. The system shortens the AE's research window from thirty minutes to five and routes only matches that pass a vertical-specific relevance bar.

## Pipeline math

Conservative downstream model at the shipped run scope (55 routed actions per day across 5 AEs, 60-account book):

| Step | Conversion | Daily output |
|---|---|---|
| Routed actions | · | 55 |
| AE acceptance (not snoozed within 48h) | 25% | 14 |
| Reply rate on accepted touches | 12% | 1.7 |
| Meeting booked from reply | 30% | 0.5 |
| Qualified opportunity from meeting | 50% | 0.25 |
| Median ACV (mid-market policy intelligence ARR) | $50,000 | $12,500 in pipeline created per day |

System cost per day at this scope: $0.65 in Claude API spend. Steady state with the classification cache active: under $0.20 per day at the same volume. Break-even is one qualified opportunity per quarter; realistic steady state is one per week.

## Hypotheses

The motion is a falsifiable bet on three claims. Each has a defined kill criterion.

**H1 · Policy activity is a leading signal of B2B intent for a policy intelligence product.**
Killed if positive_outcome rate on routed actions does not exceed the rate on a control group of cold accounts after 90 days.

**H2 · Vertical-aware scoring outperforms horizontal scoring.**
Killed if no vertical's positive_outcome rate diverges from horizontal scoring after 1,000 routed actions.

**H3 · Per-AE caps and classification caching make the system economically scalable past 10x volume.**
Killed if cost per routed action does not decline as bill volume scales.

## Handoffs

The system does not own the relationship. The AE does. The system reduces the cost of the AE doing their job well, and exposes outcome data to the people who need to learn from it.

| Persona | What they receive | What they own |
|---|---|---|
| AE | A drafted task in HubSpot with full context: bill text, account exposure framing, suggested open. Five minutes of editing replaces thirty minutes of research. | The send. The conversation. The relationship. |
| Marketing | Bulk-tier sequence enrollments by vertical. Warms an account ahead of an AE touch. | The vertical campaign. The content asset. |
| RevOps | A weekly reweight proposal generated from the outcomes log, structured for review and manual merge. The outcomes table itself, ready for analysis. | The scoring config. The decision to apply or reject the proposal. |
| Sales leadership | Weekly summary: routed actions, accepted, replied, meetings booked, opps created, sourced pipeline dollars. Cost vs. attributable revenue. | The investment decision. The team-level deployment plan. |

## Operational guardrails

A signal-based system loses its license to operate the moment AEs stop trusting the queue. Three guardrails are enforced or ready to enforce.

| Guardrail | Implementation |
|---|---|
| Per-AE daily caps (3 hubspot, 5 sequence, 3 slack) | Live in `scripts/run_pipeline.py`. Prevents the firehose problem where 383 raw matches drown 5 AEs. |
| Account-vertical suppression (14 days) | A documented next-build item; trivially implementable as a join on the outcomes log. Stops the same account from being touched on the same vertical four times in a week. |
| Shadow mode for the first two weeks of any rollout | Routes go to a private RevOps channel for review. AEs see nothing. The ramp that earns trust before the queue lands in their HubSpot. |

## Metrics

Three layers, in order of noise tolerance.

| Layer | Metric | Target |
|---|---|---|
| North star | Sourced pipeline dollars per quarter, first-touch attribution | Set by GTM leadership |
| Leading | AE acceptance rate (% of routed tasks not snoozed within 48h) | > 60% |
| Guardrail | Daily routed actions per AE | <= cap (3+5+3 = 11) |
| Guardrail | False positive rate (AE-marked "not relevant") | < 25% |

The leading metric, AE acceptance rate, is the single number that says whether the system is earning its place in the workflow. Move that, the rest follows.

## Rollout

Three phases, six weeks. The aim is to land in the AE's daily routine without breaking trust on day one.

| Phase | Weeks | Action |
|---|---|---|
| Shadow | 1-2 | Routes go to a private RevOps Slack channel. AEs do not see them. RevOps measures match volume, vertical distribution, and obvious false positives. |
| Pilot | 3-4 | Two AEs in one vertical opt in. Daily fifteen-minute standup on what was signal versus noise. Scoring weights tuned by hand. |
| Production | 5-6 | Full rollout. Weekly reweight proposal cadence begins. Outcomes log enrichment runs nightly. |

After production, the cadence is weekly: review reweight proposals; monthly review of false positive rate; quarterly review of scoring topology and vertical config.

## What this replaces

| Today | Limitation | What this changes |
|---|---|---|
| Manual policy scanning by an analyst or AE | Sub-1% coverage of relevant statehouse activity. Heroic effort. | Full coverage of ten states updated daily, with automatic vertical relevance scoring. |
| Generic intent platforms (G2, Bombora) | Lagging indicator. Not policy-aware. | A leading indicator that complements without competing. |
| Inbound-only motion | Misses accounts with regulatory exposure that have not yet self-identified. | Outbound triggered by external events the prospect cares about. |

## Risk register

| Risk | Mitigation |
|---|---|
| AE alert fatigue | Per-AE caps. Suppression window. Acceptance-rate monitoring. |
| Classification drift as Claude models update | Pin model version in the prompt files. Snapshot classifier behavior weekly into a regression set. |
| Open States API changes or rate limits | Wrap fetch layer in a thin adapter. Cache responses. Free tier provides 500 requests per day; pipeline uses ~30 at current scope. |
| LLM-driven reweight overcorrects | Hard cap at +/- 0.05 per cycle. Human approval before any merge. Hand off to logistic regression once outcomes exceed 500 per vertical. |
| False positives erode AE trust faster than true positives build it | Shadow phase before AEs see anything. Acceptance-rate threshold (60%) treated as a kill signal, not a vanity metric. |

## What this is not

A replacement for the AE's judgment. A generative outreach tool that sends on the AE's behalf. An attribution engine. The system is one signal source feeding one workflow, designed to compound with the others a GTM team already runs.
