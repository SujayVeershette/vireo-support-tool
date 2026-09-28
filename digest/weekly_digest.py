"""
digest/weekly_digest.py
Generates the weekly AI digest for Priya Raman using Groq gpt-oss-120b.

What it does:
- Takes all tickets for a given ISO week
- Sends customer_message + agent_notes samples to the LLM
- LLM returns: top complaint themes, notable signals, repeat-contact alert
- Returns structured dict ready for Streamlit rendering
"""
import os
import re
import json
import time
import logging
import pandas as pd
from groq import Groq
from groq import RateLimitError

MODEL = "openai/gpt-oss-120b"

# Cost per 1M tokens (as of Sep 2026)
COST_INPUT_PER_1M = 0.15
COST_OUTPUT_PER_1M = 0.60


logger = logging.getLogger(__name__)


def _get_client():
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY not set in environment. Add it to your .env file.")
    return Groq(api_key=api_key)


def _call_with_backoff(client, max_retries=3, base_delay=1.0, **kwargs):
    """
    Call client.chat.completions.create(**kwargs) with exponential backoff
    on Groq 429 RateLimitError.

    Retry schedule: 1s → 2s → 4s (doubles each attempt).
    Raises the final error if all retries are exhausted.
    """
    delay = base_delay
    for attempt in range(1, max_retries + 2):  # +2: initial attempt + retries
        try:
            return client.chat.completions.create(**kwargs)
        except RateLimitError as exc:
            if attempt > max_retries:
                logger.error("Rate limit hit after %d attempts — giving up.", max_retries + 1)
                raise
            logger.warning(
                "Rate limit hit (attempt %d/%d). Retrying in %.1fs…",
                attempt, max_retries + 1, delay,
            )
            time.sleep(delay)
            delay *= 2


def _load_sku_map():
    """
    Return a dict {sku: product_name} from data/products.csv.
    Falls back to an empty dict if the file isn't found.
    """
    products_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'products.csv')
    try:
        prod_df = pd.read_csv(products_path, usecols=['sku', 'product_name'])
        return dict(zip(prod_df['sku'], prod_df['product_name']))
    except Exception:
        return {}


def _build_ticket_sample(week_df, max_tickets=40):
    """
    Build a compact text representation of tickets for the LLM.
    Cap at max_tickets to stay within token budget. Prioritise:
    - High priority
    - SLA breached
    - Repeat contacts
    - Random sample of the rest
    """
    sku_map = _load_sku_map()

    # Priority selection
    high = week_df[week_df['priority'] == 'High']
    sla = week_df[week_df['sla_breached'] == True]
    repeat = week_df[week_df['is_repeat_contact'] == True]

    priority_ids = set(high.index) | set(sla.index) | set(repeat.index)
    priority_rows = week_df.loc[list(priority_ids)]

    rest = week_df.drop(index=list(priority_ids))

    remaining_slots = max(0, max_tickets - len(priority_rows))
    if remaining_slots > 0 and len(rest) > 0:
        sampled_rest = rest.sample(min(remaining_slots, len(rest)), random_state=42)
    else:
        sampled_rest = rest.iloc[0:0]

    selected = pd.concat([priority_rows, sampled_rest]).head(max_tickets)

    lines = []
    for _, row in selected.iterrows():
        msg = str(row.get('customer_message', '') or '').strip()[:150]
        note = str(row.get('agent_notes', '') or '').strip()[:100]
        cat = str(row.get('category', '') or '').strip()
        ch = str(row.get('channel', '') or '').strip()
        is_repeat = '⚠️ REPEAT' if row.get('is_repeat_contact') else ''
        is_breach = '🔴 SLA-BREACH' if row.get('sla_breached') else ''
        sku = str(row.get('product_sku', '') or '').strip()
        # Resolve SKU to a human-readable product name so the model uses the
        # canonical name instead of nearby order IDs or raw SKU codes.
        product_name = sku_map.get(sku, '')
        product_label = f"{sku} ({product_name})" if product_name else sku
        lines.append(
            f"[{cat}|{ch}|{product_label}{' ' + is_repeat if is_repeat else ''}{' ' + is_breach if is_breach else ''}]\n"
            f"Customer: {msg}\nAgent note: {note}"
        )

    return "\n\n---\n\n".join(lines)


DIGEST_SYSTEM_PROMPT = """You are a senior customer-experience analyst at Vireo Audio, a consumer-audio brand (earbuds, headphones, smart speakers, smartwatches).
You receive a batch of support tickets from a single week and produce a concise weekly digest for the Head of Customer Experience.

Return ONLY valid JSON with this exact schema (no markdown fences, no extra keys):
{
  "week_summary": "<2-3 sentence plain-English summary of the week>",
  "top_themes": [
    {
      "theme": "<short theme name>",
      "ticket_count": <integer estimate from the sample>,
      "description": "<1-2 sentences: what customers are saying, any pattern>",
      "example_verbatim": "<one short customer quote, paraphrased slightly if too long>",
      "severity": "high|medium|low"
    }
  ],
  "repeat_contact_alert": {
    "flagged": <true|false>,
    "summary": "<if flagged: which category is driving repeats and likely root cause>"
  },
  "sla_breach_alert": {
    "flagged": <true|false>,
    "channels_affected": ["<channel>"],
    "summary": "<brief note>"
  },
  "product_signals": [
    {
      "sku": "<product_sku>",
      "top_issue": "<single most reported problem for this product>",
      "ticket_count": <integer estimate>
    }
  ],
  "recommended_action": "<one specific, named action: who does what by when — e.g. 'Logistics lead to audit VA-AC-CBL delivery route by Wednesday'>"
}

Rules:
- top_themes: 4 to 6 themes, ordered by frequency/severity descending.
- Do not invent data not present in the tickets.
- Be specific: name SKUs, categories, agent patterns where visible.
- If a theme appears in the tickets as 'Other', try to infer a more specific label from the customer messages.
- Keep language direct and operational — this is for an ops manager, not marketing.
"""


def generate_digest(week_df, week_str):
    """
    Main entry point. Returns (digest_dict, usage_stats).
    digest_dict: parsed JSON from LLM
    usage_stats: {'input_tokens': int, 'output_tokens': int, 'cost_usd': float}
    """
    if len(week_df) == 0:
        return {"error": "No tickets found for this week."}, {}

    ticket_text = _build_ticket_sample(week_df, max_tickets=40)

    # Stats to inject as context
    total = len(week_df)
    repeat_count = int(week_df['is_repeat_contact'].sum())
    breach_count = int(week_df['sla_breached'].sum())
    refund_total = float(week_df['refund_amount_inr'].sum())
    replacements = int(week_df['replacement_issued'].sum())
    csat_vals = week_df['csat_score'].dropna()
    avg_csat = float(csat_vals.mean()) if len(csat_vals) > 0 else None
    channel_counts = week_df['channel'].value_counts().to_dict()
    cat_counts = week_df['category'].value_counts().to_dict()

    context_block = f"""WEEK: {week_str}
TOTAL TICKETS: {total}
REPEAT CONTACTS (same customer, same category, ≤30 days): {repeat_count} ({100*repeat_count/max(total,1):.1f}%)
SLA BREACHES: {breach_count} ({100*breach_count/max(total,1):.1f}%)
REFUNDS RAISED: Rs {refund_total:,.0f}
REPLACEMENTS ISSUED: {replacements}
AVG CSAT (respondents): {f'{avg_csat:.2f}' if avg_csat else 'n/a'}
CHANNEL MIX: {json.dumps(channel_counts)}
CATEGORY COUNTS (bot-tagged): {json.dumps(cat_counts)}

TICKET SAMPLE (up to 40 tickets, priority-weighted):
{ticket_text}
"""

    client = _get_client()

    response = _call_with_backoff(
        client,
        max_retries=3,
        base_delay=1.0,
        model=MODEL,
        messages=[
            {"role": "system", "content": DIGEST_SYSTEM_PROMPT},
            {"role": "user", "content": context_block},
        ],
        temperature=0.2,
        max_tokens=2500,
        response_format={"type": "json_object"},
    )

    raw = response.choices[0].message.content.strip()

    # Guard: if the model hit max_tokens, the JSON will be truncated and unparseable.
    finish_reason = response.choices[0].finish_reason
    if finish_reason == "length":
        return {
            "error": (
                f"Model output was truncated (finish_reason='length'). "
                f"The response hit the {2500}-token limit before completing the JSON. "
                "Try reducing max_tickets or simplifying the prompt."
            )
        }, {}

    # Parse JSON — response_format=json_object should guarantee valid JSON,
    # but we keep the fallback chain for safety.
    try:
        digest = json.loads(raw)
    except json.JSONDecodeError:
        # Strip markdown fences if the model wrapped the JSON anyway
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        if match:
            try:
                digest = json.loads(match.group())
            except json.JSONDecodeError as e:
                digest = {
                    "error": f"JSON parse failed after extraction: {e}",
                    "raw_response": raw,
                }
        else:
            digest = {
                "error": "No JSON object found in model response.",
                "raw_response": raw,
            }

    usage = response.usage
    input_tokens = usage.prompt_tokens
    output_tokens = usage.completion_tokens
    cost_usd = (input_tokens * COST_INPUT_PER_1M / 1_000_000) + \
               (output_tokens * COST_OUTPUT_PER_1M / 1_000_000)

    usage_stats = {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost_usd": cost_usd,
        "cost_inr": cost_usd * 84,  # approximate USD→INR
    }

    return digest, usage_stats


if __name__ == '__main__':
    import sys
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
    from ingest.load_data import load_all, get_available_weeks, get_tickets_for_week
    from dotenv import load_dotenv
    load_dotenv()

    df = load_all()
    weeks = get_available_weeks(df)
    # Default: last full week in dataset
    target_week = weeks[-2] if len(weeks) >= 2 else weeks[-1]
    print(f"Running digest for week: {target_week}")
    week_df = get_tickets_for_week(df, target_week)
    print(f"Tickets in week: {len(week_df)}")

    digest, stats = generate_digest(week_df, target_week)
    print(json.dumps(digest, indent=2))
    print(f"\nUsage: {stats}")
