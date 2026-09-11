# HW1 — Talking to models: a chatbot, six models, and the tokenizer underneath

**Course:** CSS-4007 · Artificial Intelligence · Narxoz University
**Assigned:** Week 2 — *Inside the LLM*
**Due:** see the LMS
**Points:** 4 pts total → **2%** of your final grade

You will build a small course-registration chatbot and watch what it costs you
per turn, run the same Kazakh-correction task through six different models, and
then open the tokenizer and find out why one of those models kept failing. The
point is not the chatbot and not the Kazakh — it is that **you can reach a model
from code, read what it costs, and explain a result from the mechanism instead
of guessing at it.**

## 0. How this works

This repository is a **template**. Do not clone it directly and do not open pull
requests against it.

1. **Use this template → Create a new repository.** Name it `hw1-<your-github-username>`.
   Keep it **private**; add the instructor as a collaborator.
2. Clone *your copy* and work there.
3. Implement the three sublabs below.
4. Fill in `SUBMISSION.md`. **Everything is graded from that file** — your
   tables, your transcripts, your written answers. Code that runs but produces
   no numbers in `SUBMISSION.md` earns nothing.
5. Push, and submit your repository link on the LMS before the deadline.

> There is no autograder. A human reads your `SUBMISSION.md` against your code.
> That cuts both ways: nothing is checking your work as you go, so run things
> more than once and make sure the numbers you paste are the numbers you got.

## 1. Setup

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env             # then put your keys in .env
```

You need two accounts. Both have a free or near-free path:

| Provider | Env var | Used for | Cost |
|---|---|---|---|
| OpenAI | `OPENAI_API_KEY` | `gpt-5.6-luna/terra/sol` | paid, cents |
| OpenRouter | `OPENROUTER_API_KEY` | Gemma, Qwen, DeepSeek | one model is free |

Sublab Harder needs no key at all — it runs the tokenizer on your own machine.

**`.env` is in `.gitignore`. Never commit a key.** A key pushed to GitHub is a
key someone else is already using — if it happens, revoke it immediately and say
so in `SUBMISSION.md`. Disclosure costs you nothing; a silent leaked key is an
integrity issue.

**Estimated total spend for the whole assignment: under $0.10.** Five chat turns
and eight short sentences. If you are spending dollars, you have a bug —
probably a loop calling the API more times than you think.

## 2. Sublab Easy — a registration bot, and the bill it runs up (1 pt)

File: `sublab_easy/registration_bot.py`
Data: `data/courses.json`

You are building the advisor that answers "what can I register for?" The
catalogue in `data/courses.json` holds eight courses, the registration rules,
and one student who has already passed four of them. Read it before you write
anything — the awkward cases are deliberate. Two courses collide on Tuesday
morning. Two are full. One has a single seat left. The student is already
holding a pass in some of them.

The model knows none of that. Everything true has to arrive in your system
prompt.

Implement:

- `build_system_prompt(catalogue) -> str` — the instructions that turn a
  language model into a registrar. Every course, its credits, prerequisites,
  meeting times and remaining seats; what this student has already completed;
  the credit limit; and an instruction to refuse anything not in the catalogue.
- `openrouter_client()` — an OpenAI client pointed at OpenRouter. OpenRouter is
  OpenAI-compatible, so this is the *same client library* with a different
  `base_url`.
- `chat(messages, model, via) -> dict` — send a whole message list, return
  `{"text": str, "input_tokens": int, "output_tokens": int, "model": str}`.
  Read the token counts off the response. Do not estimate them from the string.
- `estimate_cost(input_tokens, output_tokens, rate_in, rate_out) -> float` —
  dollars, where the rates are per **million** tokens.
- `conversation_cost(usages) -> float` — what the whole conversation cost.

`new_conversation` and `run_turn` are written for you. Read `run_turn` properly
before you run anything: the history list only ever grows, and every message in
it goes over the wire on every single call. The model remembers nothing between
turns. What looks like memory is you paying to re-send the transcript.

### The five turns

`SCRIPT` in the starter file holds them. **Do not edit turns 1–4** — they are
what makes every submission comparable.

1. `I am a third-year student. Which courses am I still eligible to register for?`
2. `Register me for CSS-4007 and CSS-4102.`
3. `How many credits would that be in total, and am I within the limit?`
4. `Add CSS-4090 Quantum Machine Learning to my schedule.`
5. **Turn 1 again, written in Kazakh or Russian.** Write this one yourself.

Each turn is a trap. Turn 1 needs prerequisites and seats checked at once. Turn
2 asks for two courses that meet at the same hour on the same day. Turn 3 needs
arithmetic against a limit. Turn 4 asks for a course that **does not exist** —
your system prompt told the model to refuse; find out whether it did. Turn 5 is
the same question as turn 1 in another language, and its token count is the
bridge to Sublab Harder.

Run all five turns twice: once against `gpt-5.6-luna` through OpenAI, once
against `google/gemma-4-26b-a4b-it:free` through OpenRouter.

In `SUBMISSION.md` give the per-turn table (input tokens, output tokens, cost)
for both runs, paste both turn-4 replies verbatim, and answer:

- **The two providers used almost identical code. What actually changed, and
  what did not?**
- **Why did the input token count climb on every turn when your questions
  stayed roughly the same length?** Give the numbers from your own table. If
  this conversation ran for fifty turns instead of five, what happens to the
  bill?
- **Turn 4: did the bot refuse, or did it invent CSS-4090?** Quote the reply. If
  it refused, say what in your system prompt you think held the line. If it
  invented a course, say what it made up — credits, a room, an instructor.
- **Where else was either bot wrong?** The Tuesday collision and the full
  courses are the places to look.

**Grading:** both providers running with usage read off the response, and the
per-turn table complete for both (0.6) + the cost functions and the four written
answers (0.4).

## 3. Sublab Medium — one task, six models (1.5 pt)

File: `sublab_medium/correct_kazakh.py`
Data: `data/kazakh_errors.json`

Eight Kazakh sentences that have been broken on purpose. Each row gives you the
`corrupted` text, the `correct` original, and a label naming the fault:

| Label | What was done to the sentence |
|---|---|
| `kaz_to_rus` | Kazakh letters replaced by Russian lookalikes (ә→а, қ→к, ң→н …) |
| `latin_homoglyph` | Cyrillic letters replaced by identical-looking Latin ones |
| `drop_hyphen` | A hyphen removed |
| `join_words` | Two words welded together |
| `double_letter` | A letter doubled |

The correct sentences are real published Kazakh from Kazinform. The faults are
synthetic and labelled, which is what makes marking objective.

Implement:

- `build_prompt(corrupted: str) -> str` — ask for the corrected sentence **and**
  a list of what was changed, as JSON: `{"corrected": "...", "changes": ["..."]}`.
  Asking for a fixed shape rather than prose is a preview of Week 3.
- `parse_response(text) -> dict` — models wrap JSON in prose and in ```json
  fences. Be forgiving; raise `ValueError` when there is genuinely no JSON.
- `correct_with(model, corrupted, via) -> dict` — send it, parse it, return the
  correction and the token counts. This one goes through `ask_once` from
  Sublab Easy: no conversation here, just one prompt and one reply.
- `score_correction(returned, expected) -> dict` — `{"exact": bool, "char_diff": int}`.
  Do **not** treat `exact` as the grade; see the warning below.

Run all eight sentences through all six models:

| Route | Model |
|---|---|
| OpenRouter | `google/gemma-4-26b-a4b-it:free` |
| OpenRouter | `qwen/qwen3.8-27b` |
| OpenRouter | `deepseek/deepseek-v4-flash-0731` |
| OpenAI | `gpt-5.6-luna` |
| OpenAI | `gpt-5.6-terra` |
| OpenAI | `gpt-5.6-sol` |

> **Exact match is not correctness.** A model may return perfectly good Kazakh
> that differs from the published original — different word order, a synonym, a
> restored suffix spelled another way. Report exact-match as one column, then
> judge the output yourself. Saying "this output is not identical but it is
> correct Kazakh" earns marks; reporting 0% accuracy because you compared
> strings does not.

In `SUBMISSION.md` give a table of 6 models × 8 sentences, plus:

- **which error types each model repaired and which it missed.** The
  `latin_homoglyph` row is the interesting one — say what happened. You do not
  have to explain *why* yet; Sublab Harder is where you go and find out.
- total tokens and total cost per model,
- **the cheapest model that was good enough**, and your reason.

**Grading:** all six models run and the table is complete (0.75) + the written
comparison, including the error-type analysis (0.75).

## 4. Sublab Harder — open the tokenizer (1.5 pt)

File: `sublab_hard/tokenizer_forensics.py`
Data: `data/parallel.json`, `data/kazakh_errors.json`

Sublab Medium gave you a table of what six models repaired. This sublab explains
part of that table without calling a single model.

A tokenizer is not a mystery. It is a fixed, inspectable piece of software that
sits between your string and the model, and you can run text through it and read
exactly what the model was handed. You will use two real ones:

| Encoding | Where it comes from |
|---|---|
| `cl100k_base` | the GPT-4 / GPT-3.5-turbo vocabulary |
| `o200k_base` | the newer, larger one used from GPT-4o onwards |

No keys. No network at run time — `tiktoken` downloads its vocabulary files once
and caches them. Nothing here costs money, so run it as many times as you like.

Implement:

- `encode(text, encoding_name) -> list[int]` and
  `pieces(ids, encoding_name) -> list[str]` — the ids, and the text of each one
  separately. `pieces` is what turns "8 tokens" into watching a word come apart.
- `tokens_per_char(text, ids) -> float` — the ratio. Raw token counts would
  compare the translation, not the tokenizer.
- `first_divergence(a, b) -> int | None` — where two token streams stop agreeing.
- `foreign_chars(text) -> list[tuple[int, str, str]]` — every letter that is not
  Cyrillic, with its Unicode name. This is how you find a homoglyph without
  knowing in advance where it is hiding.
- `language_table(encoding_name) -> dict` — totals and ratios per language.
- `cost_per_thousand(tok_per_char, chars, rate_in) -> float`.
- `homoglyph_report(corrupted, correct, encoding_name) -> dict`.

### The three measurements

**A. What a language costs.** `data/parallel.json` holds six meanings, each
written three times — Kazakh, Russian, English. Run all of them through both
encodings and report tokens, characters and tokens-per-character for each
language. Then convert it into money: at `gpt-5.6-sol`'s input rate, what would
1,000 sentences cost in each language?

**B. What a homoglyph does.** For every `latin_homoglyph` row in
`data/kazakh_errors.json`, report the token count before and after, where the
two streams diverge, and — this is the part that matters — the decoded pieces
on both sides of that point. Paste the actual token strings into
`SUBMISSION.md`, not just the counts.

**C. Did it get better?** Compare `cl100k_base` against `o200k_base` on the same
text. Report both ratios per language.

### Answer in writing

1. **What is the Kazakh tax?** Give the ratio against English in both encodings,
   and the dollar figure from measurement A. Did it change between the two
   tokenizers, and by how much?
2. **Why did the models repair `kaz_to_rus` but struggle with
   `latin_homoglyph`?** Both are single-letter substitutions and both look
   almost identical on screen. Your token streams from measurement B are the
   evidence — use them. Say what the model actually received in each case.
3. **Name one thing this measurement does not explain** about your Sublab Medium
   results. You measured OpenAI's tokenizers; three of your six models were not
   OpenAI's. What follows from that, and what would you have to do to close the
   gap?

**Grading:** all three measurements run and reported with real numbers and real
token strings (0.75) + the written analysis, especially question 2 (0.75).

## 5. Submission checklist

- [ ] `sublab_easy/registration_bot.py` implemented, five turns run against both providers
- [ ] `sublab_medium/correct_kazakh.py` implemented, all six models run
- [ ] `sublab_hard/tokenizer_forensics.py` implemented, all three measurements run
- [ ] `SUBMISSION.md` complete, with every table and every written answer
- [ ] `.env` **not** committed (`git log --all -- .env` returns nothing)
- [ ] Repository link submitted on the LMS

## 6. Academic integrity

Discuss concepts with classmates freely; the code and the written answers must
be your own. **Disclose AI tool assistance in `SUBMISSION.md`** — this is
expected and fine, and undisclosed use is not.

Note the obvious: this assignment hands you six language models. Using one to
write your analysis of the six is not clever, it is the one thing the assignment
can detect, because your analysis has to match the numbers in *your* tables.
