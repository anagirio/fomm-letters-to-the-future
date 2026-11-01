"""Can Beam find the small details planted years apart in Marina's life, once they are buried in hundreds of
everyday capsules? Two tests, both graded by code (no AI judge):

1. Questions: 16 questions whose answers are in the hand-written capsules, often only by connecting two
   capsules years apart (the parrot man gets his real name 11 years after she drew him).
2. Retrospective: the app's own tab-2 prompt, with no hint of what to look for. We check which planted loops
   it connects on its own, and whether every date it cites really exists.

    REFLECTION_API_KEY=xxx python needle_test.py            # writes results/needles.json and results/needles.md
"""

import argparse
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import beam
import prompts

HERE = Path(__file__).parent
TODAY = "2026-11-01"

# (id, question, regex that a correct answer must match)
QUESTIONS = [
    ("parrot_man_name", "Marina drew an old man with a parrot on her bus. What was his REAL name?", r"\bValdir\b"),
    ("parrot_name", "What was the parrot's real name?", r"\bJuca\b"),
    ("parrot_man_moved", "Which city did the parrot man move to when he left the bus?", r"Ponta Grossa"),
    ("parrot_man_age", "How old was the parrot man when he died?", r"\b91\b"),
    ("postcard_city", "In which city did Marina find an old postcard of a man with a parrot?", r"Lisbo[an]"),
    ("first_lemon_date", "On what date (YYYY-MM-DD) did Marina pick the first lemon of the tree she grew from a seed?",
     r"2026-01-12"),
    ("lemon_years", "How many whole years passed between planting that seed and picking the first lemon?",
     r"\b10\b|\bten\b"),
    ("asa_branca_year", "In what year did Marina first play 'Asa Branca' all the way to the end?", r"\b2023\b"),
    ("asa_branca_late", "How many years after promising it to Tio Beto was that?", r"\b9\b|\bnine\b"),
    ("driving_tests", "How many times in total did Marina take the driving test?", r"\b3\b|\bthree\b"),
    ("swim_meters", "How many meters did she swim without stopping on the day she kept her 2014 promise to learn "
                    "to swim?", r"\b25\b"),
    ("dog_name", "What was the name of the dog buried under the jabuticabeira?", r"\bCoronel\b"),
    ("savings_fund", "What name did Marina give her savings fund in the bank app?", r"\bMAR\b"),
    ("rafa_daughter", "What is the name of Rafa's daughter?", r"\bLua\b"),
    ("first_salary_gift", "What did Marina buy her mother with her first salary?", r"printer|impressora"),
    ("book_pages", "How many pages does the finished book about her grandmother have?", r"\b64\b"),
]

QA_PROMPT = """You get every time capsule a person wrote over the years, as
<capsule n=... written=YYYY-MM-DD opens=YYYY-MM-DD to=...>text</capsule>. Answer each question using only the
capsules. Answers are short (a name, a number, a date, a place). If the capsules don't say, answer "unknown".
Answer ONLY with JSON, no code fence: {"<question id>": "<answer>", ...}"""

# Loops the retrospective should close by itself: every regex of a loop must appear in its text. They check the
# ending of each loop, not exact dates: the Beam-written filler moves some dates around (see README).
LOOPS = {
    "lemon seed → first lemon (2026)": [r"lemon|limão|Limonada", r"first lemon|primeiro limão", r"2026"],
    "'Asa Branca' promise → kept, nine years late (2023)": [r"Asa Branca", r"2023"],
    "parrot man drawn → real name Valdir (2025)": [r"parrot|papagaio", r"Valdir"],
    "learn to swim (2014) → 25 m (2022)": [r"swim|nadar", r"25 ?m|25 meters|2022-07-19"],
    "sea dream → swimming with Vó Lúcia in it (2026)": [r"dream|sonho", r"(Vó|grandmother|Lúcia)[^.\n]{0,120}(swim|nad)|(swim|nad)[^.\n]{0,120}(Vó|grandmother|Lúcia)"],
    "book about Vó → 'Menina do Mar' finished": [r"Menina do Mar", r"finished|64 pages|terminad|2026-09-27"],
}

# The first version of the grader also required the exact first and last dates of each loop.
STRICT_LOOPS = {
    "lemon": [r"lemon|limão|Limonada", r"2016-01-12|2016", r"2026-01-12"],
    "asa_branca": [r"Asa Branca", r"2014-04-07", r"2023-06-24"],
    "parrot": [r"parrot|papagaio", r"Valdir"],
    "swim": [r"swim|nadar", r"2014-03-10", r"2022-07-19"],
    "dream": [r"dream|sonho", r"2014-07-02", r"2026-07-20"],
    "book": [r"Menina do Mar", r"2026-09-27"],
}


def life(name):
    if name == "none":
        return []
    files = {"skeleton": ["marina.json", "marina_extra.json"], "long": ["marina_long.json"]}[name]
    caps = []
    for f in files:
        caps += json.loads((HERE / "samples" / f).read_text(encoding="utf-8"))["capsules"]
    return sorted(caps, key=lambda c: c["written"])


def as_blocks(caps):  # same format as the app's tab 2
    return "\n\n".join(
        f'<capsule n={i + 1} written={c.get("written", "")} opens={c.get("opens", "")} to="{c.get("to", "")}">\n'
        f'{c["text"]}\n</capsule>'
        for i, c in enumerate(caps)
    )


def call(system, user, effort, max_tokens, reasoning=beam.REASONING_BUDGET):
    for attempt in range(3):
        try:
            t = time.time()
            r = beam._client.chat.completions.create(
                model=beam.MODEL, temperature=0.2, max_tokens=max_tokens + reasoning,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                extra_body={"reasoning_effort": effort},
            )
            u = r.usage
            return {"text": r.choices[0].message.content or "", "finish": r.choices[0].finish_reason,
                    "seconds": round(time.time() - t, 1), "prompt_tokens": getattr(u, "prompt_tokens", None),
                    "completion_tokens": getattr(u, "completion_tokens", None)}
        except Exception as e:
            print(f"retry after {type(e).__name__}: {e}", flush=True)
    return {"text": "", "finish": "error"}


def run_qa(condition, effort, run):
    caps = life(condition)
    qs = "\n".join(f"{qid}: {q}" for qid, q, _ in QUESTIONS)
    user = (as_blocks(caps) if caps else "(no capsules)") + f"\n\nQuestions:\n{qs}"
    out = call(QA_PROMPT, user, effort, 1500)
    m = re.search(r"\{.*\}", out["text"], re.S)
    try:
        answers = json.loads(m.group(0)) if m else {}
    except json.JSONDecodeError:
        answers = {}
    graded = {qid: bool(re.search(rx, str(answers.get(qid, "")), re.I)) for qid, _, rx in QUESTIONS}
    print(f"qa {condition}/{effort}#{run}: {sum(graded.values())}/{len(QUESTIONS)}", flush=True)
    return {"test": "qa", "condition": condition, "capsules": len(caps), "effort": effort, "run": run,
            "answers": answers, "correct": graded, "score": sum(graded.values()), **out}


def reasoning_budget(n_capsules):  # same rule as the app: a long life needs room to think before answering
    return beam.REASONING_BUDGET * (2 if n_capsules > 1000 else 1)


def grade_loops(text, loops):
    return {name: all(re.search(rx, text, re.I) for rx in rxs) for name, rxs in loops.items()}


def run_retro(condition, effort, run):
    caps = life(condition)
    real = {c["written"] for c in caps}
    out = call(prompts.RETROSPECTIVE, f"Today is {TODAY}.\n\n{as_blocks(caps)}\n\nWrite the whole retrospective in English.", effort, 4000,
               reasoning=reasoning_budget(len(caps)))
    text = out["text"]
    loops = grade_loops(text, LOOPS)
    cited = re.findall(r"\b(\d{4}-\d{2}-\d{2})\b", text)
    invented = sorted({d for d in cited if d not in real and d != TODAY})
    print(f"retro {condition}/{effort}#{run}: {sum(loops.values())}/{len(LOOPS)} loops, "
          f"{len(cited)} dates cited, {len(invented)} not in the capsules", flush=True)
    return {"test": "retrospective", "condition": condition, "capsules": len(caps), "effort": effort, "run": run,
            "loops": loops, "loops_strict": grade_loops(text, STRICT_LOOPS), "dates_cited": len(cited), "dates_not_found": invented, **out}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--regrade", action="store_true", help="grade the saved answers again, no Beam calls")
    ap.add_argument("--retro-only", action="store_true", help="redo the retrospectives, keep the saved questions")
    args = ap.parse_args()

    out = HERE / "results"
    out.mkdir(exist_ok=True)
    if not args.regrade and (beam.demo_mode() or not beam.REFLECTION_KEY):
        raise SystemExit("Set REFLECTION_API_KEY: this script calls Beam for real.")
    if args.regrade:
        results = json.loads((out / "needles.json").read_text())["results"]
        for r in results:
            if r["test"] == "retrospective":
                r["loops"], r["loops_strict"] = grade_loops(r["text"], LOOPS), grade_loops(r["text"], STRICT_LOOPS)
        return save(out, results)
    jobs, results = [], []
    if args.retro_only:
        results = [r for r in json.loads((out / "needles.json").read_text())["results"] if r["test"] == "qa"]
    else:
        jobs += [(run_qa, "none", "low", 1)]
        jobs += [(run_qa, "skeleton", "low", r) for r in range(1, args.runs + 1)]
        jobs += [(run_qa, "long", e, r) for e in ("low", "medium") for r in range(1, args.runs + 1)]
    jobs += [(run_retro, "skeleton", "medium", r) for r in range(1, args.runs + 1)]
    jobs += [(run_retro, "long", "low", r) for r in range(1, args.runs + 3)]
    jobs += [(run_retro, "long", "medium", r) for r in range(1, args.runs + 1)]
    with ThreadPoolExecutor(11) as pool:
        results += list(pool.map(lambda j: j[0](*j[1:]), jobs))

    save(out, results)


def save(out, results):
    (out / "needles.json").write_text(json.dumps({
        "model": beam.MODEL, "date": TODAY,
        "questions": [{"id": q, "question": t, "answer_regex": rx} for q, t, rx in QUESTIONS],
        "loops": LOOPS, "strict_loops": STRICT_LOOPS, "results": results,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "needles.md").write_text(summary(results), encoding="utf-8")
    print(summary(results))


def summary(results):
    lines = ["| Test | Life | Capsules | Prompt tokens | Effort | Runs | Result | Time |", "|---|---|---|---|---|---|---|---|"]
    groups = {}
    for r in results:
        groups.setdefault((r["test"], r["condition"], r["effort"]), []).append(r)
    for (test, cond, effort), rs in groups.items():
        tokens = max((r.get("prompt_tokens") or 0) for r in rs)
        secs = sum(r.get("seconds") or 0 for r in rs) / len(rs)
        if test == "qa":
            res = " · ".join(f'{r["score"]}/{len(QUESTIONS)}' for r in rs)
        else:
            res = " · ".join(f'{sum(r["loops"].values())}/{len(LOOPS)}' if r["text"] else "empty" for r in rs)
            res += f' loops; {sum(len(r["dates_not_found"]) for r in rs)} of {sum(r["dates_cited"] for r in rs)} cited dates not found'
            res += f'; {sum(r["finish"] == "length" and not r["text"] for r in rs)} empty (thought until the limit)'

        lines.append(f"| {test} | {cond} | {rs[0]['capsules']} | {tokens:,} | {effort} | {len(rs)} | {res} | {secs:.0f} s |")
    misses = {}
    for r in results:
        if r["test"] == "qa" and r["condition"] != "none":
            for qid, ok in r["correct"].items():
                if not ok:
                    misses.setdefault(qid, []).append(f'{r["condition"]}/{r["effort"]}: {r["answers"].get(qid, "")!r}')
    if misses:
        lines += ["", "Wrong answers:", ""] + [f"- `{q}`: " + "; ".join(v) for q, v in misses.items()]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()
