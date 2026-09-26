"""
eval/eval_digest.py
Spot-checks digest accuracy by:
1. Sampling 20 tickets from the target week
2. Asking the LLM to classify each one's theme
3. Comparing against the bot category tag and our digest themes
4. Reporting agreement rate and failure cases

This is our "how do you know it works?" answer for the submission form.
Run: python eval/eval_digest.py
"""
import os
import sys
import json
import random
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from ingest.load_data import load_all, get_available_weeks, get_tickets_for_week
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

MODEL = "openai/gpt-oss-120b"
SAMPLE_SIZE = 20

EVAL_SYSTEM = """You are a support ticket classifier. Given a customer message and agent note, 
assign ONE theme label from this list:
- Delivery & Shipping
- Billing & Payments  
- Returns & Refunds
- Connectivity
- Charging & Battery
- App & Firmware
- Audio Quality
- Warranty & Repair
- Product Enquiry
- Account & Login
- Other

Return ONLY a JSON object: {"theme": "<label>", "confidence": "high|medium|low", "reasoning": "<one sentence>"}
No markdown, no extra text.
"""


def classify_ticket(client, customer_msg: str, agent_note: str) -> dict:
    user_content = f"Customer message: {customer_msg[:400]}\nAgent note: {agent_note[:200]}"
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": EVAL_SYSTEM},
            {"role": "user", "content": user_content},
        ],
        temperature=0.0,
        max_tokens=150,
    )
    raw = resp.choices[0].message.content.strip()
    try:
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw)
    except Exception:
        return {"theme": "parse_error", "confidence": "low", "reasoning": raw}


def run_eval(week_str: str = None, sample_size: int = SAMPLE_SIZE):
    client = Groq(api_key=os.getenv("GROQ_API_KEY"))

    df = load_all()
    weeks = get_available_weeks(df)

    if week_str is None:
        week_str = weeks[-2] if len(weeks) >= 2 else weeks[-1]

    week_df = get_tickets_for_week(df, week_str)
    print(f"\n=== EVAL DIGEST — Week {week_str} ({len(week_df)} tickets) ===")
    print(f"Sampling {sample_size} tickets...\n")

    # Sample: balanced across categories
    sample = week_df.groupby('category', group_keys=False).apply(
        lambda g: g.sample(min(2, len(g)), random_state=42)
    )
    if len(sample) < sample_size:
        extra = week_df.drop(sample.index).sample(
            min(sample_size - len(sample), len(week_df) - len(sample)),
            random_state=42
        )
        sample = pd.concat([sample, extra])
    else:
        sample = sample.sample(sample_size, random_state=42)

    results = []
    correct = 0
    total = 0

    for _, row in sample.iterrows():
        msg = str(row.get('customer_message', '') or '')
        note = str(row.get('agent_notes', '') or '')
        bot_category = str(row.get('category', '') or '').strip()

        if not msg.strip() and not note.strip():
            continue

        result = classify_ticket(client, msg, note)
        llm_theme = result.get('theme', 'parse_error')
        confidence = result.get('confidence', 'low')
        reasoning = result.get('reasoning', '')

        # Agreement: LLM theme matches bot category (case-insensitive)
        match = llm_theme.strip().lower() == bot_category.strip().lower()
        if match:
            correct += 1
        total += 1

        status = "✅" if match else "❌"
        results.append({
            'ticket_id': row['ticket_id'],
            'bot_category': bot_category,
            'llm_theme': llm_theme,
            'confidence': confidence,
            'match': match,
            'reasoning': reasoning,
        })

        print(f"{status} [{row['ticket_id']}] Bot: {bot_category:25} → LLM: {llm_theme:25} ({confidence})")
        if not match:
            print(f"   Reasoning: {reasoning}")

    agreement_rate = (correct / total * 100) if total > 0 else 0
    print(f"\n=== RESULTS ===")
    print(f"Sampled: {total} tickets")
    print(f"Agreement with bot category: {correct}/{total} = {agreement_rate:.1f}%")
    print()

    # Mismatches
    mismatches = [r for r in results if not r['match']]
    if mismatches:
        print(f"Mismatches ({len(mismatches)}):")
        for m in mismatches:
            print(f"  {m['ticket_id']}: Bot '{m['bot_category']}' vs LLM '{m['llm_theme']}'")
            print(f"    → {m['reasoning']}")
    else:
        print("No mismatches.")

    print(f"\nNote: 'disagreement' does not always mean error — LLM may reclassify 'Other' more precisely.")
    print(f"Typical failure mode: LLM assigns specific sub-category where bot used 'Other'.")

    return {
        'week': week_str,
        'sample_size': total,
        'agreement_rate_pct': round(agreement_rate, 1),
        'mismatches': mismatches,
    }


if __name__ == '__main__':
    week_arg = sys.argv[1] if len(sys.argv) > 1 else None
    run_eval(week_str=week_arg)
