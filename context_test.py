"""Two follow-ups to needle_test.py, same 16 questions, same grading by code (no AI judge):

1. Whole life vs RAG. Is reading all 5,112 capsules in one request better than retrieving the capsules that look
   most like each question? RAG asks one question at a time with its top-k capsules (dense: multilingual-e5-large;
   sparse: BM25), in date order, with the same prompt.
2. Context length. The 74 hand-written capsules plus a growing random sample of the Beam-written filler, from
   ~30k to ~240k tokens (each life contains the smaller ones; the full 480k life is in needle_test.py). Where does Beam start to miss, or to come back empty?

Three questions (driving_tests, lemon_years, first_lemon_date) have conflicting evidence in the filler (see README),
so every result is also given on the 13 clean questions.

    REFLECTION_API_KEY=xxx uv run --python 3.12 --with-requirements requirements.txt --with fastembed --with rank-bm25 \\
        python context_test.py                 # writes results/context.json and results/context.md
"""

import argparse
import json
import random
import re
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import needle_test as nt

HERE = Path(__file__).parent
CACHE = HERE / ".cache"
CONFLICTING = {"driving_tests", "lemon_years", "first_lemon_date"}
SIZES = [240, 560, 1200, 2480]  # filler capsules added to the 74 hand-written ones (~30k → ~240k tokens; 480k is in needle_test.py)
RAG_K = {"dense": [20, 100], "bm25": [50]}
EMBED_MODEL = "intfloat/multilingual-e5-large"

ONE_QUESTION = nt.QA_PROMPT.replace("Answer each question", "Answer the question")


def lives():
    long = nt.life("long")
    hand = {c["text"] for c in nt.life("skeleton")}
    skeleton = [c for c in long if c["text"] in hand]
    filler = [c for c in long if c["text"] not in hand]
    random.Random(7).shuffle(filler)
    return long, skeleton, filler


def grade(answers):
    return {qid: bool(re.search(rx, str(answers.get(qid, "")), re.I)) for qid, _, rx in nt.QUESTIONS}


def parse(text):
    m = re.search(r"\{.*\}", text, re.S)
    try:
        return json.loads(m.group(0)) if m else {}
    except json.JSONDecodeError:
        return {}


def clean_score(correct):
    return sum(ok for qid, ok in correct.items() if qid not in CONFLICTING)


# ---------- 1. RAG ----------

def retrievers(long):
    import numpy as np
    from rank_bm25 import BM25Okapi

    CACHE.mkdir(exist_ok=True)
    path = CACHE / "e5_large.npy"
    from fastembed import TextEmbedding
    model = TextEmbedding(EMBED_MODEL)
    if path.exists():
        docs = np.load(path)
    else:
        docs = np.array(list(model.embed([f'passage: {c["text"]}' for c in long], batch_size=32)))
        np.save(path, docs)
    docs /= np.linalg.norm(docs, axis=1, keepdims=True)

    def tokens(t):
        return re.findall(r"\w+", t.lower())

    bm25 = BM25Okapi([tokens(c["text"]) for c in long])

    def dense(q, k):
        v = next(iter(model.embed([f"query: {q}"])))
        return list(np.argsort(-(docs @ (v / np.linalg.norm(v))))[:k])

    def sparse(q, k):
        return list(np.argsort(-bm25.get_scores(tokens(q)))[:k])

    return {"dense": dense, "bm25": sparse}


def patient_call(*args, **kw):  # the API answers 429 when many small calls arrive at once
    for wait in (5, 15, 30, 60, 120, 240):
        out = nt.call(*args, **kw)
        if out["finish"] != "error":
            return out
        time.sleep(wait)
    raise RuntimeError("Beam kept refusing the call (rate limit)")


def run_rag(long, hits, method, k, run):
    answers, prompt_tokens, seconds = {}, 0, 0.0
    for qid, q, _ in nt.QUESTIONS:
        caps = sorted((long[i] for i in hits[(method, k, qid)]), key=lambda c: c["written"])
        out = patient_call(ONE_QUESTION, f"{nt.as_blocks(caps)}\n\nQuestions:\n{qid}: {q}", "low", 400)
        answers[qid] = parse(out["text"]).get(qid, "") or f'(no JSON: {out["text"][:80]!r}, finish={out["finish"]})'
        prompt_tokens += out.get("prompt_tokens") or 0
        seconds += out.get("seconds") or 0
    correct = grade(answers)
    print(f"rag {method}@{k}#{run}: {sum(correct.values())}/16 ({clean_score(correct)}/13 clean)", flush=True)
    return {"test": "rag", "condition": f"{method} top-{k}", "k": k, "run": run, "answers": answers,
            "correct": correct, "score": sum(correct.values()), "clean": clean_score(correct),
            "prompt_tokens_total": prompt_tokens, "seconds": round(seconds, 1)}


# A retrospective has no question to search with, so RAG has to guess one.
RETRO_QUERY = ("promises to my future self, things that came back years later, recurring people, objects, songs, "
               "plants and dreams, things I let go of")
RETRO_K = [100, 300]


def run_rag_retro(long, hits, method, k, run):
    caps = sorted((long[i] for i in hits[(method, k, "retro")]), key=lambda c: c["written"])
    real = {c["written"] for c in long}
    out = patient_call(nt.prompts.RETROSPECTIVE, f"Today is {nt.TODAY}.\n\n{nt.as_blocks(caps)}\n\n"
                       "Write the whole retrospective in English.", "low", 4000)
    text = out["text"]
    loops = nt.grade_loops(text, nt.LOOPS)
    cited = re.findall(r"\b(\d{4}-\d{2}-\d{2})\b", text)
    print(f"rag-retro {method}@{k}#{run}: {sum(loops.values())}/6 loops", flush=True)
    return {"test": "rag-retro", "condition": f"{method} top-{k}", "k": k, "run": run, "loops": loops,
            "score": sum(loops.values()), "dates_cited": len(cited),
            "dates_not_found": sorted({d for d in cited if d not in real and d != nt.TODAY}), **out}


# ---------- 2. Context length ----------

def run_size(skeleton, filler, n, effort, run):
    caps = sorted(skeleton + filler[:n], key=lambda c: c["written"])
    qs = "\n".join(f"{qid}: {q}" for qid, q, _ in nt.QUESTIONS)
    out = nt.call(nt.QA_PROMPT, f"{nt.as_blocks(caps)}\n\nQuestions:\n{qs}", effort, 1500,
                  reasoning=nt.reasoning_budget(len(caps)))
    answers = parse(out["text"])
    correct = grade(answers)
    empty = not out["text"]
    print(f"size {len(caps)}/{effort}#{run}: {out.get('prompt_tokens')} tokens, "
          f"{'EMPTY' if empty else f'{sum(correct.values())}/16'}", flush=True)
    return {"test": "size", "condition": f"{len(caps)} capsules", "capsules": len(caps), "effort": effort,
            "run": run, "answers": answers, "correct": correct, "score": sum(correct.values()),
            "clean": clean_score(correct), "empty": empty, **out}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--only", choices=["rag", "size", "rag-retro"])
    args = ap.parse_args()
    if nt.beam.demo_mode() or not nt.beam.REFLECTION_KEY:
        raise SystemExit("Set REFLECTION_API_KEY: this script calls Beam for real.")

    long, skeleton, filler = lives()
    jobs = []
    if args.only == "rag-retro":
        find = retrievers(long)
        hits = {(m, k, "retro"): find[m](RETRO_QUERY, k) for m in ("dense", "bm25") for k in RETRO_K}
        jobs += [(run_rag_retro, long, hits, m, k, r) for m in ("dense", "bm25") for k in RETRO_K
                 for r in range(1, args.runs + 1)]
    elif args.only != "size":
        find = retrievers(long)
        hits = {(m, k, qid): find[m](q, k) for m, ks in RAG_K.items() for k in ks for qid, q, _ in nt.QUESTIONS}
        jobs += [(run_rag, long, hits, m, k, r) for m, ks in RAG_K.items() for k in ks for r in range(1, args.runs + 1)]
    if args.only not in ("rag", "rag-retro"):
        jobs += [(run_size, skeleton, filler, n, e, r) for n in SIZES for e in ("low", "medium")
                 for r in range(1, args.runs + 1)]
    with ThreadPoolExecutor(3 if args.only in ("rag", "rag-retro") else 10) as pool:
        results = list(pool.map(lambda j: j[0](*j[1:]), jobs))

    out = HERE / "results" / "context.json"
    if args.only and out.exists():  # keep the other half of a previous run
        results = [r for r in json.loads(out.read_text())["results"] if r["test"] != args.only] + results
    out.write_text(json.dumps({"model": nt.beam.MODEL, "date": nt.TODAY, "embedding_model": EMBED_MODEL,
                               "conflicting_questions": sorted(CONFLICTING), "results": results},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    (HERE / "results" / "context.md").write_text(summary(results), encoding="utf-8")
    print(summary(results))


def summary(results):
    lines = ["| Test | Setup | Effort | Prompt tokens | All 16 (per run) | 13 clean (per run) | Empty | Time |",
             "|---|---|---|---|---|---|---|---|"]
    groups = {}
    for r in results:
        groups.setdefault((r["test"], r["condition"], r.get("effort", "low")), []).append(r)
    for (test, cond, effort), rs in sorted(groups.items(), key=lambda g: (g[0][0], g[1][0].get("capsules", 0), g[0][1])):
        if test != "rag-retro":
            tokens = (max(r.get("prompt_tokens") or 0 for r in rs) if test == "size"
                      else max(r["prompt_tokens_total"] for r in rs) // len(nt.QUESTIONS))
            tokens = f"{tokens:,}" + (" per question" if test == "rag" else "")
        if test == "rag-retro":
            tokens = f'{max(r.get("prompt_tokens") or 0 for r in rs):,}'
            loops = " · ".join(f'{r["score"]}/6' if r["text"] else "empty" for r in rs)
            secs = sum(r.get("seconds") or 0 for r in rs) / len(rs)
            lines.append(f"| {test} | {cond} | {effort} | {tokens} | {loops} loops | – | – | {secs:.0f} s |")
            continue
        full = " · ".join("–" if r.get("empty") else str(r["score"]) for r in rs)
        clean = " · ".join("–" if r.get("empty") else str(r["clean"]) for r in rs)
        empty = sum(bool(r.get("empty")) for r in rs)
        secs = sum(r.get("seconds") or 0 for r in rs) / len(rs)
        lines.append(f"| {test} | {cond} | {effort} | {tokens} | {full} | {clean} | {empty} of {len(rs)} | {secs:.0f} s |")
    misses = {}
    for r in results:
        if r["test"] != "rag-retro" and not r.get("empty"):
            for qid, ok in r["correct"].items():
                if not ok:
                    misses.setdefault(qid, []).append(f'{r["condition"]}/{r.get("effort", "low")}: {r["answers"].get(qid, "")!r}')
    if misses:
        lines += ["", "Wrong answers:", ""] + [f"- `{q}`: " + "; ".join(v) for q, v in misses.items()]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()
