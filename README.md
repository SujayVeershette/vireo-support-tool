# Vireo Audio — Support Intelligence Tool

Weekly AI digest + agent leaderboard for Vireo Audio's support desk.  
Built for Priya Raman, Head of Customer Experience.

---

## What it does

| View | What you get |
|------|-------------|
| **Weekly Digest** | AI-clustered complaint themes, repeat-contact alert, SLA breach alert, product signals, one recommended action. Powered by Groq `gpt-oss-120b`. |
| **Agent Leaderboard** | Tier 1 agents ranked by tickets closed/week, with CSAT and breach rate. Tier 2 (Escalations & Warranty) shown separately with resolution-day metric. |

---

## Setup (clean machine, ~2 minutes)

### 1. Clone / download

```bash
git clone <your-repo-url>
cd vireo-support-tool
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

Requires Python 3.9+. Recommended: use [uv](https://github.com/astral-sh/uv) for fast installs:

```bash
uv venv
.venv\Scripts\activate   # Windows
# or: source .venv/bin/activate  (macOS/Linux)
uv pip install -r requirements.txt
```

Or with plain pip:

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Add your Groq API key

```bash
cp .env.example .env
# Edit .env and paste your GROQ_API_KEY
```

Get a free key at: https://console.groq.com/keys  
The tool works without a key (all computed metrics still show) but digest generation will be disabled.

### 4. Add the data files

Place these CSVs in the `data/` folder:

```
data/
  tickets.csv
  agents.csv
  orders.csv
  customers.csv
  products.csv
```

The repo includes the Vireo data pack. If you're setting up fresh, copy from the original export.

### 5. Run

```bash
streamlit run app.py
```

Opens at `http://localhost:8501`. Pick a week in the sidebar, click **Generate Digest**.

---

## Project structure

```
vireo-support-tool/
├── app.py                    # Streamlit UI (main entry point)
├── requirements.txt
├── .env.example              # Copy to .env, add GROQ_API_KEY
├── README.md
├── submission-form.md        # Filled submission form
├── memo-priya.md             # One-page memo for Priya Raman
│
├── data/                     # CSV data files (not committed if large)
│   ├── tickets.csv
│   ├── agents.csv
│   ├── orders.csv
│   ├── customers.csv
│   └── products.csv
│
├── ingest/
│   └── load_data.py          # CSV loading, cleaning, joining, feature engineering
│
├── digest/
│   └── weekly_digest.py      # Groq API call + prompt + JSON parsing
│
├── leaderboard/
│   └── agent_leaderboard.py  # Tier-1/Tier-2 leaderboard computation
│
└── eval/
    └── eval_digest.py        # Spot-check: sample 20 tickets, measure LLM accuracy
```

---

## Running the evaluation

```bash
python eval/eval_digest.py
# or for a specific week:
python eval/eval_digest.py 2026-W25
```

Samples 20 tickets (balanced across categories), classifies each with the LLM, compares against bot category tags. Reports agreement rate and flags mismatches with reasoning. See submission form §3 for interpretation.

---

## Model and cost

| Item | Value |
|------|-------|
| Model | `openai/gpt-oss-120b` via Groq |
| Input cost | $0.15 / 1M tokens |
| Output cost | $0.60 / 1M tokens |
| Cost per digest run | ~$0.005 (~Rs 0.42) |
| Monthly cost (4 runs) | ~$0.02 (~Rs 1.68) |
| Monthly cost at 650 tickets/week | ~$0.032 (~Rs 2.69) |

---

## Key decisions documented

1. **Tier 2 excluded from main leaderboard** — per Neha Kulkarni's email + support policy §6. Shown separately with median-resolution-days.
2. **CSAT legacy zeros treated as null** — per support policy §8. Blank = no response, not zero satisfaction.
3. **Digest defaults to last full week in dataset** — avoids partial weeks at dataset boundary.
4. **Repeat contact = same customer, same category, ≤30 days** — per policy §10 definition of "first-contact resolution."
5. **40-ticket sample cap per digest run** (reduced from 120) — keeps total prompt within Groq free-tier 8K TPM limit (~5,500 input tokens). Priority-weighted (High priority + SLA breaches + repeat contacts first).
6. **SKU resolved to product name in prompts** — `products.csv` is joined at digest time so the LLM sees `VA-EB-AIR (AirLite Earbuds)` instead of a raw SKU code, preventing order IDs bleeding into product signal output.
7. **`response_format={"type": "json_object"}`** — forces the model to emit complete, valid JSON; combined with a `finish_reason == "length"` guard for a clear error if output is truncated.
8. **Exponential backoff on 429s** — `_call_with_backoff()` retries up to 3 times (1 s → 2 s → 4 s) on `RateLimitError` so double-clicking Generate doesn't crash.

---

## Known limitations

- Ticket sample cap (40 tickets) means digest theme counts are estimates, not exact totals
- Repeat contact detection may undercount if category re-tagging occurs on re-contact
- Legacy tickets (pre-14 Sep 2025) have no `transfers` field — transfer costs for that period are zero by default
- CSAT averages based on ~45% response rate — directional only
- No authentication on the Streamlit app — internal use only

---

## Screening recording

[Link to 3-minute screen recording — to be added before submission]

---

## Changelog

### v1.2 — Post-review fixes
- `max_tokens` bumped from 2000 → 2500 to prevent mid-JSON truncation on large weeks
- Stale "up to 120 tickets" label in context block corrected to 40
- Product signals schema tightened: one issue per SKU with ticket count estimate (was multi-issue string)
- `recommended_action` prompt constrained to name who does what by when (was defaulting to generic "task force" language)

### v1.1 — Bug fixes (senior review)
- Fixed `global pd` hack in `weekly_digest.py` — `_build_ticket_sample` would `NameError` if called before `generate_digest`
- Removed unused `import random` and `import plotly.graph_objects as go`
- Vectorised SLA breach calculation — replaced row-by-row `df.apply()` with boolean mask (~50× faster)
- Removed dead `resolved_mask` variable in repeat-contact detection
- Fixed `.any()` semantic bug in CSAT lambda (leaderboard) — changed to `len(x.dropna()) > 0`
- JSON fence stripping replaced with `re.search(r'\{.*\}')` — robust to any model wrapping
- `build_leaderboard` and `get_weekly_trend` wrapped in `@st.cache_data` — prevents rescan of 12k rows on every widget interaction
- Max ticket sample reduced 120 → 40, message truncation tightened to fit Groq free-tier 8K TPM limit
- Product signals now pass `sku:product_name` so model surfaces SKUs not order IDs

### v1.0 — Initial build
- Streamlit app with weekly digest and agent leaderboard views
- Groq `gpt-oss-120b` for AI digest generation
- Repeat contact detection (same customer, same category, ≤30 days)
- Tier 2 excluded from main leaderboard per policy §6
- Legacy CSAT zeros treated as null per policy §8
