# Motion

The system feeds the top of the funnel. This document covers everything downstream: the talk track per lane, discovery questions, the ROI model, proof point patterns, and the land-and-expand path that turns a signal-triggered first touch into Enterprise revenue.

## Product context

A modern state policy intelligence platform sells in three tiers:

| Tier | Buyer | Motion | What they get |
|---|---|---|---|
| News | Individual contributors, small advocacy orgs | Self-serve, credit card | Daily statehouse coverage, push alerts |
| Pro | Single or two-state operators, mid-market policy teams | Inside sales, demo + trial | Bill tracking, multi-state monitoring, real-time keyword alerts, hearing transcripts |
| Enterprise | Multi-state Fortune 1000 operators, large trade associations | Field sales, account exec + sales engineer + sponsor | All-50-state monitoring, aggregated dashboards, keyword tuning by industry/region, dedicated account manager, SLA |

The signal engine targets the **Enterprise** motion. Buyers are VPs of Government Affairs, Heads of Public Policy, and Chief Compliance Officers at multi-state regulated operators. The system routes the bill that lands in their compliance team's inbox to the AE who covers their account, the same week it lands.

## The pitch

The talk track writes itself because the prospect is already inside the problem.

> "AB 1015 just got signed in Georgia. It changes the Self-insurers Guaranty Trust Fund funded levels, and your team is recalculating workers comp assessment exposure right now. Tracking bills like this across all fifty states by hand takes a Government Affairs analyst about forty hours a week. Our platform does it automatically, with industry-tuned keyword alerts, hearing transcripts, and a dashboard your compliance and legal teams share. Worth a fifteen-minute walk-through?"

The structure is consistent across all three routing lanes: name the bill, name the specific operational pain it created, name the manual alternative, name the platform's answer, propose a small next step.

## Three lanes, three talk tracks

### Urgent lane (urgency=5, Slack alert)

Bill is signed, on the governor's desk, or scheduled for floor vote. AE responds same-day.

**Opening (60 seconds, voicemail or LinkedIn DM):**
> "Hi [Name], I saw [BillID] just [latest_action] in [State]. It changes [topic_summary]. Given [Account]'s footprint in [State], your compliance team is in the middle of this. We track this in real time across all fifty states; happy to share a quick read on what we're seeing. Free for ten minutes today?"

**Discovery questions on the first call:**
1. How did you first hear about [BillID]?
2. Who on your team owns multi-state compliance tracking today?
3. How many states are you actively monitoring?
4. What tools or sources is the team using right now (Bloomberg Government, Quorum, manual)?
5. When [BillID] hit the floor, what was the internal scramble like?

The fifth question is the one that opens the budget conversation.

### Top-tier lane (score ≥ 0.85, account tier ≤ 2, HubSpot task)

Score is high, account is strategic. AE drafts a real outbound within 48 hours, often a personalized email to the Government Affairs lead with one hand-written paragraph plus the briefing from the routed task.

**Email frame:**
- Subject: `[BillID] just moved in [State], relevant to [Account]?`
- Paragraph 1: the bill, the trigger, the specific exposure (from the briefing)
- Paragraph 2: the manual alternative (forty hours of analyst time across fifty states)
- Paragraph 3: the platform's answer, plus one peer reference
- CTA: a fifteen-minute call, framed as a read on what we're seeing

**Discovery on the call:** same five questions as the urgent lane, plus:
- How are you currently scoping coverage by state? (Top five? All fifty? Tier-driven?)
- What is the cost of missing a bill? (Triggers a budget conversation if the answer is anything operational.)
- Who else needs visibility into this besides Government Affairs? (Legal, compliance, comms; surfaces the land-and-expand path.)

### Bulk lane (0.6 ≤ score < 0.8, sequence enrollment)

Vertical campaign nurture. Marketing-owned cadence. AE picks up when the account engages.

**Sequence shape (vertical-specific, four touches over three weeks):**
1. Day 0: the bill briefing as an awareness touch ("here is what just moved in your industry")
2. Day 4: a peer use case ("[Peer in same vertical] uses us for exactly this kind of bill")
3. Day 11: a Government Affairs efficiency frame ("the manual scan version of this takes Y hours; here is the dashboard view")
4. Day 21: a fifteen-minute call ask, only if there has been any prior engagement

The sequence is designed to be deletable. If the prospect does not engage in three weeks, the system suppresses the account-vertical for sixty days and the AE moves on.

## ROI model (for Enterprise discovery)

The AE walks the prospect through this in the second meeting. Inputs are the prospect's own; outputs are conservative.

| Input | Prospect estimate | Notes |
|---|---|---|
| FTEs scanning state legislation today (analysts, paralegals, GA team) | ___ | Round to nearest half-FTE |
| Average loaded cost per FTE | $150,000 | Loaded includes benefits, tools, overhead |
| Percentage of FTE time spent on manual policy tracking | ___% | Typical answer: 40-70% |
| Number of states actively monitored | ___ | Out of 50 |
| Estimated additional states the team would cover if it could | ___ | Surfaces hidden demand |

**Output:**

| Metric | Calculation | Value |
|---|---|---|
| Annual cost of manual scanning today | FTEs × loaded cost × % time | $___ |
| Estimated cost of expanding to all 50 states manually | (50 ÷ current states) × annual cost | $___ |
| Enterprise platform annual cost | (from quote) | $___ |
| Net annual savings | Annual cost − platform cost | $___ |
| Payback period | platform cost ÷ monthly savings | ___ months |

The model is designed to be conservative on purpose. A Government Affairs team of two analysts at $150K loaded each, spending 60% of their time on manual policy tracking, costs $180K per year on the activity. Doubling coverage manually doubles that cost. The platform replaces the activity at a fraction of either number.

## Proof points

| Pattern | What the AE says | Example asset |
|---|---|---|
| Industry peer | "A peer in [vertical] uses us to track exactly this kind of bill across [N] states. Want me to share what their workflow looks like?" | Anonymized customer workflow one-pager |
| Volume of coverage | "We are tracking [N] bills today across [N] states; here is what is moving in your industry this week." | Live dashboard demo |
| Quality of classification | "Our keyword tuning is industry-specific; here is a screenshot of how [bills relevant to vertical] surface for a peer in [vertical]." | Industry-specific dashboard screenshot |
| Manual alternative | "The alternative is forty hours of analyst time per week. Here is what that looks like on a calendar." | Calendar / time-allocation visual |
| Speed | "[BillID] was on our platform within two hours of [latest_action]. The manual workflow is two days, sometimes a week." | Timestamped feed |

## Land and expand

Enterprise is the entry point for multi-state operators. Expansion follows three paths.

**Path 1: User seats.** Government Affairs is the buyer. Legal, compliance, regulatory affairs, and external communications all need read access to the same platform. Each adds seats at the Enterprise rate.

**Path 2: Industry tuning.** A diversified operator (e.g., a bank that also offers insurance products) buys industry-tuned keyword sets for each line of business. Each industry tuning is a meaningful uplift on the base Enterprise contract.

**Path 3: Custom monitoring.** The platform's keyword and tag system supports custom monitoring on regulatory topics that matter to one customer (e.g., a specific class of carve-outs in tax law). Custom monitoring is a paid add-on and the natural quarterly review item for the customer success team.

The signal engine plays into all three. Routed actions that surface adjacent industries within an existing customer become expansion triggers. The Outcome Enrichment Agent flags any reply that names a different stakeholder (a "wrong_contact" classification) as a seat expansion opportunity.

## Renewal levers

A customer who acts on routed signals from the platform retains. The system's outcomes log gives Customer Success a per-customer view of how often the platform was the source of a regulatory decision or workflow change.

**Renewal questions for Customer Success to ask quarterly:**
1. Which bills did the platform surface that the team acted on this quarter?
2. Which of those changed an internal workflow or compliance posture?
3. How many states are now in active coverage versus last quarter?
4. Which other internal stakeholders are now using the platform?

Negative answers across all four are a churn signal. The system feeds the data; Customer Success carries the conversation.

## What the AE owns versus what the system owns

| Stage | System | AE |
|---|---|---|
| Signal detection | Owns | Reads |
| Match scoring | Owns | Trusts (and tunes via the weekly reweight proposal) |
| Routing and queue management | Owns | Receives |
| First touch | Drafts | Sends |
| Discovery and qualification | Provides talking points | Owns |
| Demo, trial, close | Provides context | Owns end-to-end |
| Renewal and expansion | Surfaces signals | Owns the conversation |

The system is one input to the motion, not the motion itself. The AE owns the relationship throughout.
