# Memo: What We Found in 18 Months of Support Tickets

**To:** Priya Raman, Head of Customer Experience, Vireo Audio  
**From:** Sujay S Veershette  
**Date:** September 2026  
**Reading time:** ~8 minutes

---

## The short version

We read 18 months of your tickets. The biggest finding isn't in any category — it's that **1 in 6 resolved tickets comes back as the same problem from the same customer within 30 days.** That's 1,944 avoidable contacts, costing roughly **Rs 94,000 a quarter** at your blended contact rate. The weekly digest we've built is designed to surface the patterns driving those repeats before they compound.

---

## What we built

A tool that runs every week and gives you two things:

**1. A digest of what's actually happening** — not the bot's category tags (which are coarse), but a plain-English summary of the themes appearing in customer messages that week, ordered by frequency and severity. It flags repeat-contact spikes, SLA breach patterns, and product-specific signals. It ends with one recommended action for the week. The whole thing takes about 10 seconds to generate.

**2. An agent leaderboard** — Tier 1 agents, ranked by tickets closed within the week, broken down by team. CSAT and SLA breach rate sit alongside the ticket count so you're not rewarding speed at the expense of quality. Escalations & Warranty are shown separately with resolution-time metrics — they work differently by design, and ranking them on volume would be misleading.

To run it: open the tool, pick a week from the dropdown, click Generate Digest. That's it.

---

## The number you need

**Repeat contact rate: 16.4%.** Same customer, same issue category, re-contacting within 30 days of a resolved ticket.

At your blended cost of Rs 290 per contact, those 1,944 repeat contacts over 18 months cost **Rs 5.64 lakh** — or about **Rs 94,000 every quarter** — for calls and chats that shouldn't need to happen.

The three categories driving the most repeats are Delivery & Shipping (540 repeat contacts), Billing & Payments (367), and Returns & Refunds (276). Delivery repeats alone account for nearly 28% of all repeat contacts.

A rough interpretation: customers are resolving their tickets without their actual problem being fixed. They come back. Your agents spend time re-explaining the same issue. That's the loop the digest is designed to break — by making the pattern visible weekly rather than buried in 18 months of data nobody reads.

---

## What we noticed that you didn't ask about

**The Connectivity / App & Firmware cluster is worth watching.** A notable volume of tickets about Bluetooth pairing issues are split between two categories depending on which agent tags them. This means the category count understates the real volume of connectivity complaints. The digest picks this up even when the bot doesn't, because it reads the actual customer messages.

**Lot-code clustering.** Your orders data includes the manufacturing lot printed on each box. We didn't have time to build this, but if a particular hardware complaint (say, charging failures on the AirLite) is concentrated in one lot code, that's a quality-control signal that should go to your product team before the warranty claims pile up. It's the most useful thing we didn't build.

**The 650-tickets-a-week figure in your brief doesn't match the export.** The data we received shows roughly 175–190 tickets a week in recent months. If the real volume is 650/week — either this export is a sample, or the team has grown significantly since the cut — the repeat-contact cost above should be multiplied by about 3.5×, which would put the quarterly cost closer to **Rs 3.3 lakh**. Worth checking with Sameer.

---

## What this tool doesn't do (and why)

It doesn't resolve tickets. It doesn't suggest responses to agents. It doesn't auto-tag anything. It reads what happened last week and tells you the pattern, in plain language, so you can decide what to do about it.

We deliberately didn't build a "platform." You said you don't need one, and you're right — a tool that gives you a readable digest on Monday morning is more useful than a dashboard nobody opens. The natural next step, if this proves useful after a few weeks, is to schedule the digest to email you automatically every Monday. That's about an hour of additional work.

---

## One thing to do this week

Look at the repeat-contact breakdown by category and pick one — the one with the highest count or the most visible pattern in the digest. Ask your team: what are we closing on this issue that isn't actually fixing it? That answer is worth more than any dashboard.

---

*The tool runs from your existing ticket data. No new data collection required. Costs approximately Rs 1.70 per week to run at current volume — the API call is not a cost consideration.*
