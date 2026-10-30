"""FOMM · Letters to the Future, a Build with Beam demo.

Three things Beam does for time capsules:
1. Interviews you and writes the capsule in your own voice.
2. Reads every capsule of a life at once (long context) and writes a retrospective.
3. Checks if a capsule could hurt when it opens years later and prepares the recipient.
"""

import json
import os
import re
from datetime import date
from pathlib import Path

import gradio as gr

import beam
import prompts

SAMPLES = Path(__file__).parent / "samples"
SAMPLE = json.loads((SAMPLES / "marina.json").read_text(encoding="utf-8"))
HAND_WRITTEN = sorted(
    SAMPLE["capsules"] + json.loads((SAMPLES / "marina_extra.json").read_text(encoding="utf-8"))["capsules"],
    key=lambda c: c["written"],
)
LONG = (json.loads((SAMPLES / "marina_long.json").read_text(encoding="utf-8"))["capsules"]
        if (SAMPLES / "marina_long.json").exists() else None)
CHOICES = {f"Marina, {len(HAND_WRITTEN)} hand-written capsules (2014–2026)": HAND_WRITTEN}
if LONG:
    CHOICES = {f"Marina, long life: {len(LONG)} capsules (expanded with Beam)": LONG, **CHOICES}
CHOICES["Only my own"] = []
MAX_LIFE_CHARS = 2_500_000  # roughly 600k tokens, well inside Beam's 1M context
FIRST_QUESTION = (
    "Hi! Who is this capsule for, and when should it arrive? "
    "(You can write in any language.)"
)


def session_id(request: gr.Request) -> str:
    return getattr(request, "session_hash", None) or "local"


def friendly(err: Exception) -> str:
    if isinstance(err, beam.LimitReached):
        return f"⏳ {err}"
    if isinstance(err, beam.EmptyAnswer):
        return "Beam thought for too long and ran out of room before answering. Please try again."
    return f"Beam could not answer right now ({type(err).__name__}). Please try again in a moment."


# ---------- 1. Interview ----------

def transcript(history):
    def text(content):  # Gradio may hand back content as a list of parts
        if isinstance(content, list):
            return " ".join(p.get("text", "") if isinstance(p, dict) else str(p) for p in content)
        return str(content)
    return "\n".join(f"{'INTERVIEWER' if m['role'] == 'assistant' else 'PERSON'}: {text(m['content'])}" for m in history)


def interview_turn(message, history, request: gr.Request):
    message = (message or "").strip()
    if not message:
        yield history, ""
        return
    history = history + [{"role": "user", "content": message[:4000]}]
    yield history, ""
    # Sent as one transcript: Beam's API wants the reasoning of every earlier assistant turn otherwise.
    msgs = [
        {"role": "system", "content": prompts.INTERVIEWER},
        {"role": "user", "content": f"Interview so far:\n{transcript(history[-20:])}\n\nAsk your next question."},
    ]
    history = history + [{"role": "assistant", "content": ""}]
    try:
        for text in beam.stream(msgs, session_id(request), max_tokens=200, effort="low",
                                demo_text="What is one small thing you do every day right now that you think you'll miss?"):
            history[-1]["content"] = text
            yield history, ""
    except Exception as err:
        history[-1]["content"] = friendly(err)
        yield history, ""


def write_capsule(history, request: gr.Request):
    if len([m for m in history if m["role"] == "user"]) < 2:
        yield "Answer at least two questions first, so the capsule has something of you in it."
        return
    msgs = [
        {"role": "system", "content": prompts.WRITER},
        {"role": "user", "content": f"Today is {date.today().isoformat()}.\n\nInterview:\n{transcript(history)}"},
    ]
    try:
        yield from beam.stream(msgs, session_id(request), max_tokens=700,
                               demo_text="Dear future me, right now the coffee in the kitchen still smells like Saturday...")
    except Exception as err:
        yield friendly(err)


def seal(letter, to, opens, sealed):
    letter = (letter or "").strip()
    if not letter:
        return sealed, "Write the capsule first."
    try:
        opens = date.fromisoformat(str(opens)[:10]).isoformat()
    except ValueError:
        return sealed, "Pick an opening date like 2031-10-30."
    sealed = sealed + [{"written": date.today().isoformat(), "opens": opens, "to": to or "future me", "text": letter}]
    return sealed, f"🔒 Sealed until {opens}. You have {len(sealed)} capsule(s) in this session; they are now part of the Retrospective tab."


# ---------- 2. Retrospective ----------

def parse_upload(path):
    if not path:
        return []
    raw = Path(path).read_text(encoding="utf-8", errors="replace")
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            data = data.get("capsules", [])
        return [c for c in data if isinstance(c, dict) and c.get("text")]
    except json.JSONDecodeError:
        # Plain text: capsules separated by lines starting with a date, e.g. "2015-04-02: ..."
        parts = re.split(r"(?m)^(\d{4}-\d{2}-\d{2})\s*[:\-]\s*", raw)
        return [{"written": parts[i], "opens": "", "to": "", "text": parts[i + 1].strip()}
                for i in range(1, len(parts) - 1, 2)]


def life_summary(capsules):
    if not capsules:
        return "No capsules loaded."
    years = sorted(c.get("written", "")[:4] for c in capsules if c.get("written"))
    chars = sum(len(c["text"]) for c in capsules)
    span = f"{years[0]}–{years[-1]}" if years else "unknown years"
    return f"**{len(capsules)} capsules**, {span}, about {chars // 4:,} tokens. Beam reads them all at once."


def load_life(choice, upload, sealed):
    capsules = CHOICES.get(choice, []) + parse_upload(upload) + sealed
    capsules = sorted(capsules, key=lambda c: c.get("written", ""))
    return capsules, life_summary(capsules)


LANGUAGES = ["Same as the capsules", "English", "Português"]


def retrospective(capsules, language, request: gr.Request):
    if not capsules:
        yield "Load some capsules first."
        return
    body = "\n\n".join(
        f'<capsule n={i + 1} written={c.get("written", "")} opens={c.get("opens", "")} to="{c.get("to", "")}">\n'
        f'{c["text"]}\n</capsule>'
        for i, c in enumerate(capsules)
    )
    if len(body) > MAX_LIFE_CHARS:
        yield "That is more than this demo accepts (about 600k tokens). Try fewer capsules."
        return
    msgs = [
        {"role": "system", "content": prompts.RETROSPECTIVE},
        {"role": "user", "content": f"Today is {date.today().isoformat()}.\n\n{body}"},
    ]
    if language in LANGUAGES[1:]:
        msgs[1]["content"] += f"\n\nWrite the whole retrospective in {language}."
    try:
        yield from beam.stream(msgs, session_id(request), max_tokens=2000, temperature=0.5,
                               demo_text="## Threads that kept coming back\nThe sea [2014-12-31]...")
    except Exception as err:
        yield friendly(err)


# ---------- 3. Gentle opening ----------

def pick_sample(n):
    c = SAMPLE["sensitive_examples"][int(n)]
    return c["text"], c["written"], c.get("context", "")


def gentle(text, written, context, request: gr.Request):
    text = (text or "").strip()
    if not text:
        return "Paste a capsule first.", ""
    msgs = [
        {"role": "system", "content": prompts.GENTLE_OPENING},
        {"role": "user", "content": (
            f"Capsule written on {written or 'unknown date'}, opening on {date.today().isoformat()}.\n\n"
            f"<capsule>\n{text[:20000]}\n</capsule>\n\n"
            f"What is known about the recipient now: {context.strip() or 'nothing'}"
        )},
    ]
    try:
        raw = beam.complete(msgs, session_id(request), max_tokens=400, temperature=0.2,
                            demo_text='{"sensitivity": "high", "topics": ["a grandmother"], "why": "Demo.", "opening_note": "This one is about someone you love."}')
    except Exception as err:
        return friendly(err), ""
    match = re.search(r"\{.*\}", raw, re.S)
    try:
        r = json.loads(match.group(0)) if match else None
    except json.JSONDecodeError:
        r = None
    if not r:
        return raw, ""
    badge = {"low": "🟢 low", "medium": "🟡 medium", "high": "🔴 high"}.get(r.get("sensitivity"), r.get("sensitivity", "?"))
    topics = ", ".join(r.get("topics") or []) or "none"
    verdict = f"**Sensitivity:** {badge}\n\n**Topics:** {topics}\n\n{r.get('why', '')}"
    note = r.get("opening_note") or ""
    preview = f"### 💌 Before you open this…\n\n{note}" if note else "_No warning needed: it opens directly._"
    return verdict, preview


# ---------- UI ----------

HERE = Path(__file__).parent
CSS = (HERE / "style.css").read_text(encoding="utf-8") + (HERE / "earth.css").read_text(encoding="utf-8")
EARTH_SVG = (HERE / "earth.svg.html").read_text(encoding="utf-8")  # same Earth as fomm-site.html
FORCE_DARK = "() => { document.body.classList.add('dark'); }"

with gr.Blocks(title="FOMM · fear of missing memories") as demo:
    sealed = gr.State([])
    life = gr.State([])

    gr.HTML(
        EARTH_SVG
        + '<div class="hero"><div class="hero-orbWrap"><div class="capsule"><div class="halo"></div>'
        '<svg class="earth" role="img" aria-label="Earth"><use href="#earth"/></svg><div class="moon"></div>'
        "</div></div>"
        "<h1>FOMM</h1><div class=\"tagline\">fear of missing memories</div>"
        "<p>Time capsules that arrive on the day you choose. <b>Beam</b> helps you write them, "
        "reads a whole life of them at once, and makes sure they open gently.</p></div>"
    )
    if beam.demo_mode():
        gr.Markdown("> ⚠️ **Demo mode**: no `REFLECTION_API_KEY` or `HF_TOKEN` is set, so answers are canned and do not come from Beam.")

    with gr.Tab("1 · Write a capsule"):
        gr.Markdown("Beam interviews you, one question at a time, then writes the capsule **in your own words**.")
        chat = gr.Chatbot(value=[{"role": "assistant", "content": FIRST_QUESTION}], height=380, show_label=False)
        with gr.Row():
            msg = gr.Textbox(placeholder="Type your answer…", show_label=False, scale=5)
            send = gr.Button("Send", variant="primary", scale=1)
        write_btn = gr.Button("✍️ Write my capsule")
        letter = gr.Textbox(label="Your capsule (edit freely)", lines=10)
        with gr.Row():
            to = gr.Textbox(label="For", value="future me")
            opens = gr.Textbox(label="Opens on (YYYY-MM-DD)", value=date(date.today().year + 5, 1, 1).isoformat())
        seal_btn = gr.Button("🔒 Seal capsule", variant="primary")
        seal_msg = gr.Markdown()

        msg.submit(interview_turn, [msg, chat], [chat, msg])
        send.click(interview_turn, [msg, chat], [chat, msg])
        write_btn.click(write_capsule, chat, letter)
        seal_btn.click(seal, [letter, to, opens, sealed], [sealed, seal_msg])

    with gr.Tab("2 · A life in capsules"):
        gr.Markdown(
            "Beam's 1M-token context lets it read **every capsule someone wrote over the years in one pass** "
            "and tell them how they changed: recurring threads, things they let go of, and which promises to "
            "their future self they kept."
        )
        with gr.Row():
            source = gr.Radio(list(CHOICES), value=next(iter(CHOICES)), label="Capsules")
            upload = gr.File(label="Or upload yours (.json or .txt)", file_types=[".json", ".txt"], type="filepath")
        load_btn = gr.Button("Load capsules")
        summary = gr.Markdown()
        language = gr.Radio(LANGUAGES, value="English", label="Answer in")
        retro_btn = gr.Button("🌌 Read my life", variant="primary")
        retro_out = gr.Markdown()

        load_btn.click(load_life, [source, upload, sealed], [life, summary])
        retro_btn.click(retrospective, [life, language], retro_out)

    with gr.Tab("3 · Gentle opening"):
        gr.Markdown(
            "A capsule written in 2016 can arrive after a death or a breakup. Before delivering, Beam checks "
            "whether it could hurt and writes a short note that prepares the recipient, without spoiling it."
        )
        examples = gr.Radio([ex["label"] for ex in SAMPLE["sensitive_examples"]], label="Try an example", type="index")
        cap_text = gr.Textbox(label="Capsule", lines=8)
        with gr.Row():
            cap_written = gr.Textbox(label="Written on", placeholder="2017-06-12")
            cap_context = gr.Textbox(label="What we know about the recipient now (optional)", scale=2)
        check_btn = gr.Button("💌 Check before delivering", variant="primary")
        with gr.Row():
            verdict = gr.Markdown()
            preview = gr.Markdown(elem_classes="envelope")

        examples.change(pick_sample, examples, [cap_text, cap_written, cap_context])
        check_btn.click(gentle, [cap_text, cap_written, cap_context], [verdict, preview])

    gr.Markdown(
        "<small>Nothing you write here is stored: capsules live only in this browser session. "
        f"Model: `{beam.MODEL}` via {beam.PROVIDER if beam.REFLECTION_KEY else 'Hugging Face Inference Providers'}. "
        "Part of FOMM, a time-capsule social network built in Brazil.</small>"
    )

if __name__ == "__main__":
    demo.queue(default_concurrency_limit=4).launch(
        css=CSS, js=FORCE_DARK, theme=gr.themes.Base(primary_hue="violet"),
        # Render (and other hosts) tell the app which port to use
        server_name="0.0.0.0" if os.getenv("PORT") else None, server_port=int(os.getenv("PORT", "7860")),
    )
