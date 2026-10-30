---
title: "FOMM · fear of missing memories"
emoji: 💌
colorFrom: indigo
colorTo: purple
sdk: static
app_file: index.html
pinned: false
license: apache-2.0
short_description: Time capsules written, read and opened gently with Beam
models:
  - reflection/Beam-1.0-501B-A23B
tags:
  - build-with-beam
  - time-capsule
  - long-context
---

# FOMM · fear of missing memories

**FOMM ("fear of missing memories")** is a time-capsule social network built in Brazil: you record a video,
an audio or a letter, pick a date, and it is delivered to someone on that day, next month or in ten years.

This Space is the part of FOMM that only a model like **Beam** makes possible. Beam does three jobs:

| Tab | What Beam does | Why Beam |
|---|---|---|
| **1 · Write a capsule** | Interviews you one question at a time, then writes the capsule **in your own voice**, from your own details. | Most people freeze in front of "write to yourself in 10 years". A good interviewer gets real, specific memories out. |
| **2 · A life in capsules** | Reads **every capsule a person wrote over the years in a single pass** and writes a retrospective: recurring threads, what they let go of, and which promises to their future self they kept, broke or left open, all cited by date. | Beam's **1M-token context**. A heavy user of FOMM writes hundreds of thousands of tokens across a decade. No chunking or RAG: the whole life is in the context, so Beam can connect a promise from 2014 to the capsule that kept it in 2022. |
| **3 · Gentle opening** | Before a capsule written years ago is delivered, Beam judges whether it could hurt now (a grandparent who died, an ex-partner) and writes a short note that prepares the recipient without spoiling it. Returns structured JSON. | Time capsules are uniquely risky: the author could not know the future. This is a real safety feature for a real product. |

Try tab 2 with the built-in sample life of **Marina** (a fictional person, synthetic data written for this demo):

- **74 hand-written capsules, 2014–2026.** Small details are planted years apart on purpose: a lemon seed
  planted in a yogurt cup in 2016 gives its first lemon in 2026; a promise to learn "Asa Branca" on the guitar
  is kept nine years late; the old man with a parrot she drew on the bus in 2014 turns out, in 2025, to have a
  real name. Would you notice them all? Beam has to.
- **Long life, expanded with Beam.** [`make_long_life.py`](make_long_life.py) uses Beam to grow the hand-written
  skeleton into hundreds of everyday capsules around it, without contradicting it. That makes a real
  long-context test: the planted details are now needles in a much bigger haystack.

## How Beam is used

- Model: [`reflection/Beam-1.0-501B-A23B`](https://huggingface.co/reflection/Beam-1.0-501B-A23B), called through
  either through the [Reflection API](https://developers.reflection.ai) (OpenAI-compatible) or
  [Hugging Face Inference Providers](https://huggingface.co/docs/inference-providers), both with
  `huggingface_hub.InferenceClient` (`chat.completions`, streaming).
- Four system prompts, one per job, are in [`prompts.py`](prompts.py). The API call, streaming and usage limits are in [`beam.py`](beam.py).
- Reasoning: Beam thinks before it answers, and the thinking counts against the token limit. Each job sets
  `reasoning_effort` (`low` for the interview, so questions come back fast; `medium` for the rest) and gets extra
  room for reasoning. At the default effort, reading a whole life could use up the entire budget thinking.
- Long context: capsules are sent as `<capsule n written opens to>` blocks, sorted by date; the demo accepts up to
  about 600k tokens per request.
- Structured output: the gentle-opening check asks for strict JSON (`sensitivity`, `topics`, `why`, `opening_note`)
  and the UI renders it as a badge and a sealed-envelope preview.
- Multilingual: users can write in any language (FOMM's users write in Portuguese); Beam answers in the user's language.

## Privacy and safety

- Nothing is stored. Capsules live only in the browser session (`gr.State`) and disappear on refresh.
- The real FOMM app (accounts, payments, ID verification) is **not** part of this Space; only the Beam features are.
- Usage limits protect the host's credits: `BEAM_SESSION_LIMIT` calls per session (default 25) and
  `BEAM_DAILY_LIMIT` per day (default 600).

## Where it runs

All the code is in this repository. The Gradio app itself runs on [Render](https://fomm-letters-to-the-future.onrender.com)
(free plan, see [`render.yaml`](render.yaml)) because it needs a server to keep the Beam API key secret, and this
Space shows it embedded. If nobody used it for a while, it takes about a minute to wake up.
Code mirror: [github.com/anagirio/fomm-letters-to-the-future](https://github.com/anagirio/fomm-letters-to-the-future).

## Run it yourself

```bash
pip install -r requirements.txt
REFLECTION_API_KEY=xxx python app.py   # or HF_TOKEN=hf_xxx
```

Without a key the app starts in a clearly-labelled **demo mode** with canned answers, so you can look at the UI
without spending credits.

| Variable | Default | |
|---|---|---|
| `REFLECTION_API_KEY` | none | Key from platform.reflection.ai. Used first if set (Space secret) |
| `HF_TOKEN` | none | Or a Hugging Face token with Inference Providers permission (Space secret) |
| `BEAM_MODEL` | `reflection/Beam-1.0-501B-A23B` | |
| `BEAM_PROVIDER` | `auto` | e.g. `baseten` |
| `BEAM_SESSION_LIMIT` / `BEAM_DAILY_LIMIT` | `25` / `600` | |

## Files

```
index.html          The Space page (embeds the app running on Render)
render.yaml         How Render runs the app
app.py              Gradio UI and the three features
beam.py             Beam client, streaming, limits, demo mode
prompts.py          System prompts
style.css           FOMM look (dark space, stars, Earth)
make_long_life.py   Uses Beam to expand the sample life into hundreds of capsules
samples/            Synthetic life of Marina (hand-written + Beam-expanded) and sensitive examples
```

Built for the **Build with Beam** competition by Reflection AI. License: Apache 2.0.
