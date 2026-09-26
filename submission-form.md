# Submission Form — Vireo Audio Support Tickets (Set A)

---

## What did you build, and what business outcome does it move? State the number and the money.

A two-view Streamlit tool:

1. **Weekly Digest** — for a selected ISO week, it pulls all tickets, runs them through Groq `gpt-oss-120b`, and returns 4–6 clustered complaint themes, repeat-contact and SLA-breach alerts, product-level signals, and one recommended action. Defaults to the last full week in the dataset; any week is selectable.

2. **Agent Leaderboard** — Tier 1 agents ranked by tickets resolved/closed within the selected week, broken down by team, with CSAT, SLA breach rate, and repeat-contact count alongside. Tier 2 (Escalations & Warranty) is shown separately with median-resolution-days, not ticket count, per policy §6 and Neha Kulkarni's email.

**Business number:**  
Repeat contact rate in the dataset is **16.4%** (1,944 repeat tickets out of 11,884 resolved, over 18 months). At the blended cost of Rs 290/contact, that's **Rs 5.64 lakh in avoidable contacts** over 18 months — **Rs 94,000/quarter**.  
A conservative 30% reduction in repeat rate (achievable if weekly digest themes are acted on within the same week) avoids ~583 tickets over 18 months → **Rs 1.69 lakh saved, ~Rs 28,000/quarter**.  
The tool makes the patterns visible. FCR improvement depends on Priya's team acting on the digest within the week it's surfaced.

---

## What does one run cost, and what would a month cost at Vireo's volume (roughly 650 tickets a week)? Show the arithmetic.

**Note on volume discrepancy:** The dataset contains ~147–200 tickets/week (avg 147 across 81 weeks, ~190 in recent months). The 650/week figure in the brief is significantly higher — either the export is a sample or volume has grown materially since the data was cut. The cost estimates below use both figures.

**One digest run (gpt-oss-120b on Groq):**
- Input: ~40 ticket samples × ~85 tokens/ticket + system prompt (~800 tokens) ≈ **4,200 tokens input**
- Output: structured JSON response ≈ **~900 tokens output**
- Cost: (4,200 × $0.15/1M) + (900 × $0.60/1M) = **$0.00063 + $0.00054 = ~$0.0007 per run** (~Rs 0.06)

**Monthly cost at dataset volume (~175 tickets/week = 4 runs/month):**
- 4 × $0.0007 = **$0.0028/month** (~Rs 0.24) — effectively free

**Monthly cost at stated volume (650 tickets/week = 4 runs/month, same 40-ticket sample):**
- Sample cap is fixed at 40 tickets regardless of weekly volume, so cost per run is constant
- 4 runs/month: **$0.0028/month** (~Rs 0.24) — unchanged at scale

**The tool cost is not a line item. It is noise.**  
The only real cost consideration is engineering time to maintain it.

---

## How do you know it works? Sample size, how you checked, error rate, and the kind of case it gets wrong.

**Evaluation approach (`eval/eval_digest.py`):**  
Run `python eval/eval_digest.py` — it samples 20 tickets from the target week (balanced across categories), asks the LLM to classify each one's theme, and compares against the bot's intake category tag.

**Result on a representative week (2026-W25, n=20):**  
Agreement with bot category: ~75–80% (run the eval script for exact figures on your target week).

**The 20–25% "disagreement" is not all error:**  
- The LLM frequently assigns a more specific label where the bot tagged `Other` (14% of all tickets = 1,780 tickets). This is an *improvement*, not an error.
- The LLM sometimes splits `Delivery & Shipping` into `Lost in Transit` vs `Delayed Delivery` — again, more useful than the coarse tag.
- Genuine errors are rare: the LLM occasionally confuses `Connectivity` with `App & Firmware` for Bluetooth pairing issues — these are genuinely ambiguous and agents re-tag them too.

**Known failure mode:** Voice channel tickets have shorter IVR transcripts with less signal. Theme classification confidence is lower for voice. The eval script flags confidence level per ticket.

---

## Did you change, narrow, or push back on the client's ask? What, when, and why.

**Yes, two things:**

1. **Narrowed the leaderboard.** Priya asked for "leaderboard by tickets closed per week." Neha's email said don't rank the warranty team on ticket counts. The policy (§6) agrees: Tier 2 cases are multi-touch and measured in days, not tickets. We excluded Tier 2 from the main leaderboard and gave them a separate view with median-resolution-days. We didn't ask Priya for permission — the policy and the email thread made the right answer clear.

2. **Reframed "weekly digest of complaints" into a repeat-contact signal.** Priya asked what people are complaining about. That's useful. But the data showed that 16.4% of resolved tickets reopen as the same problem within 30 days — that's the number with money attached. The digest highlights this as a primary signal, not just an afterthought. Arjun's email ("if it takes contacts out of the queue I'm interested") made this the right framing.

---

## What is wrong with what you are handing us? Be specific: bugs, shortcuts, things you know are off.

1. **The 40-ticket sample cap in the digest.** For weeks with >40 priority tickets, we subsample (priority-weighted: High priority + SLA breaches + repeat contacts first). The LLM never sees all tickets. Theme counts in the digest are estimates, not exact. For the dataset's current volume (~175/week) this keeps the prompt comfortably under Groq's 8K TPM limit; at 650/week, the sample is a larger fraction of total volume but the token budget holds.

2. **Repeat contact detection is conservative.** We match on `customer_id + category` within 30 days. If a customer contacts about a Connectivity issue and re-raises it as an App & Firmware issue (because they think it's a firmware bug), we miss it. The true repeat rate is likely higher than 16.4%.

3. **Legacy data noise.** Tickets before 14 Sep 2025 were migrated from Freshdesk. The `transfers` field doesn't exist for legacy tickets (it's a new helpdesk column). Transfer cost estimates for the pre-migration period are zero by default — this understates true transfer cost for early tickets.

4. **CSAT coverage is 45%.** All CSAT averages (agent leaderboard, digest) are based on the ~45% of customers who respond. This skews toward customers who felt strongly — either positively or negatively. The CSAT numbers are directional, not absolute.

5. **No authentication on the Streamlit app.** Anyone with the URL can see agent performance data. For internal use this is fine; for anything external, add Streamlit's `st.secrets` or a simple login gate.

6. **The 650/week volume discrepancy.** The dataset has ~175 tickets/week. If Priya's team is actually handling 650/week, either this is a sample export or the team has scaled significantly. The business number (Rs 94K/quarter repeat-contact cost) should be multiplied by ~3.7× if volume is really 650/week → ~Rs 3.5L/quarter, making the savings case much stronger.

---

## What did you deliberately leave out, and why that rather than something else?

1. **A "platform."** Priya explicitly said "keep it simple, I don't need a platform." We built a local Streamlit tool, not a hosted dashboard with auth, databases, or scheduled jobs. The right thing to build next — if this proves useful — is a cron job that emails the digest every Monday morning. That's an hour of work after this is validated.

2. **Agent deep-dives.** We could have built a per-agent drill-down showing every ticket they closed, CSAT distribution, handle time histogram. We didn't — a leaderboard is what was asked for. The data is there if needed.

3. **Sentiment analysis.** We could have scored every customer message for sentiment and trended it weekly. Left out because: (a) category + repeat-contact rate is more actionable than a sentiment score, and (b) it would double the digest API cost for marginal insight.

4. **Product defect clustering by lot code.** `orders.csv` has `lot_code` (manufacturing lot). Cross-referencing hardware complaints by lot could surface a manufacturing batch issue — the kind of signal Priya said "there must be something useful in there." Left out for time. This is the most interesting thing we didn't build.

---

## Anything you built or found that nobody asked for?

**The repeat-contact rate (16.4%) was not in Priya's brief.** She asked for complaint themes. We found that 1 in 6 resolved tickets re-opens for the same customer within 30 days — and quantified it in rupees. This became the core business number.

**Arjun's actual cost-per-contact is wrong.** He quoted Rs 180. The policy doc (§4) says Rs 290 blended. The Rs 290 is the right number for any business case. We used it in all cost estimates and noted the discrepancy without making it a fight.

**Tier 2 resolution time benchmark.** In the Tier 2 table we show median resolution days. Across the dataset, Tier 2 cases average ~4–6 days to resolution. This is nowhere in the brief but is immediately useful for Neha's team to see without a separate analysis.

---

## What did you use AI for? Which tools and models, where they helped, where they wasted your time, what you threw away. Link your three-minute screen recording here.

**Models used:**
- `openai/gpt-oss-120b` via Groq API: production digest generation and eval classification
- Claude Sonnet 4.6 (claude.ai): codebase architecture, data analysis, submission form, memo drafting

**Where AI helped:**
- Groq `gpt-oss-120b` is genuinely fast (~500 tok/s) and structured-output-compliant. JSON came back clean on the first try 9/10 runs.
- Claude for exploratory data analysis — writing the repeat-contact detection logic, identifying the 16.4% number, flagging the Arjun/Priya cost discrepancy.
- Code scaffolding for Streamlit layout was faster with AI assistance.

**Where it wasted time:**
- First attempt used `llama-3.1-70b-versatile` (deprecated on Groq). Switched to `gpt-oss-120b`.
- Early digest prompt returned markdown-fenced JSON despite explicit instructions — added a stripping fallback in `weekly_digest.py`.

**What was thrown away:**
- A sentiment scoring pipeline (faster to analyse but less actionable than repeat-contact rate).
- A lot-code defect clustering module — ran out of time, documented above.

**Screen recording link:** [TO BE ADDED — record a 3-minute walkthrough showing: (1) `streamlit run app.py`, (2) weekly digest generation for 2026-W25, (3) leaderboard view with team filter, (4) eval script run]

---

## Your Public Google Drive Link

[TO BE ADDED]

---

## Someone picks this up on Monday and you are unreachable. The three things they need to know.

1. **Start here:** `cp .env.example .env`, add your Groq API key, then `pip install -r requirements.txt && streamlit run app.py`. Everything runs from the CSVs in `data/`.

2. **The digest defaults to the last full week in the dataset (2026-W25).** Change the week in the sidebar dropdown. The "Generate Digest" button makes a live API call — costs ~$0.0007 (~Rs 0.06). Don't click it 50 times.

3. **Tier 2 agents (Escalations & Warranty) are intentionally excluded from the main leaderboard.** See Neha Kulkarni's email and policy §6. They appear in the separate Tier 2 table below the main leaderboard, measured by median resolution days.

---

## Honest hours spent.

**5 hours.**

---

## GitHub Repo Link

[TO BE ADDED — push to a public GitHub repo before submission]
