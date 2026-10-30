"""Use Beam to grow Marina's hand-written capsules into a long life (hundreds of capsules).

The hand-written capsules are the skeleton: every year, Beam fills in the everyday capsules around them,
without contradicting the skeleton. The result is a long-context test for tab 2 and can also be published
as a synthetic dataset.

    REFLECTION_API_KEY=xxx python make_long_life.py --per-year 40   # or HF_TOKEN=hf_xxx
"""

import argparse
import json
import re
import sys
from pathlib import Path

import beam

HERE = Path(__file__).parent / "samples"

PROMPT = """You are helping build a SYNTHETIC dataset of time capsules for FOMM, a time-capsule app.
Below is the hand-written skeleton of the life of Marina, a fictional Brazilian woman, as capsules she wrote
to her future self (and a few to other people) between 2014 and 2026.

Write {n} NEW capsules that Marina wrote during {year}. Rules:
- Small, everyday moments around the skeleton's events of {year}: work, money, friends, family, food, weather,
  drawing, the bus, swimming, the lemon tree, dreams. Mostly not dramatic.
- Never contradict the skeleton (dates, names, who is alive, where she lives, what she has or hasn't done yet).
  Don't resolve anything earlier than the skeleton does. Don't invent new major events (deaths, moves, breakups).
- Her voice: warm, self-ironic, concrete. Vary length from 30 to 250 words.
- About one in four capsules in Brazilian Portuguese, the rest in English.
- Dates must be in {year} and not equal to any skeleton date. "opens" is 1 to 10 years after "written".
- "to" is usually "future me", sometimes Bia, Mom, Tio Beto or someone else from the skeleton.

Answer ONLY with a JSON array, no code fence:
[{{"written": "YYYY-MM-DD", "opens": "YYYY-MM-DD", "to": "...", "text": "..."}}, ...]

Skeleton:
{skeleton}"""


def skeleton():
    caps = []
    for name in ("marina.json", "marina_extra.json"):
        caps += json.loads((HERE / name).read_text(encoding="utf-8"))["capsules"]
    return sorted(caps, key=lambda c: c["written"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-year", type=int, default=40)
    ap.add_argument("--out", default=str(HERE / "marina_long.json"))
    args = ap.parse_args()

    if beam.demo_mode():
        sys.exit("Set REFLECTION_API_KEY or HF_TOKEN first: this script calls Beam for real.")
    beam.PER_SESSION_LIMIT = beam.DAILY_LIMIT = 10_000

    base = skeleton()
    text = "\n\n".join(f'[{c["written"]} → {c["opens"]}, to {c["to"]}] {c["text"]}' for c in base)
    taken = {c["written"] for c in base}
    generated = []

    for year in range(2014, 2027):
        count = 0
        for start in range(0, args.per_year, 40):  # batches keep each answer under max_tokens
            raw = beam.complete(
                [{"role": "user", "content": PROMPT.format(n=min(40, args.per_year - start), year=year, skeleton=text)}],
                "generator", max_tokens=12000, temperature=0.9,
            )
            match = re.search(r"\[.*\]", raw, re.S)
            try:
                caps = json.loads(match.group(0)) if match else []
            except json.JSONDecodeError:
                caps = []
            ok = [c for c in caps
                  if isinstance(c, dict) and c.get("text") and str(c.get("written", "")).startswith(str(year))
                  and c["written"] not in taken]
            taken.update(c["written"] for c in ok)
            generated += ok
            count += len(ok)
        print(f"{year}: {count} capsules")

    life = sorted(base + generated, key=lambda c: c["written"])
    chars = sum(len(c["text"]) for c in life)
    Path(args.out).write_text(json.dumps({
        "about": "Synthetic data. Hand-written skeleton (marina.json + marina_extra.json) expanded by "
                 f"{beam.MODEL}. Marina is fictional.",
        "capsules": life,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Saved {len(life)} capsules, about {chars // 4:,} tokens, to {args.out}")


if __name__ == "__main__":
    main()
