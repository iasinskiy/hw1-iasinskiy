"""Sublab Medium - one Kazakh-correction task, six models/runs via OpenRouter."""

import json
import os
import re
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sublab_easy.registration_bot import (
    RATES_PER_MTOK,
    ask_once,
    estimate_cost,
)

DATA = Path(__file__).resolve().parent.parent / "data" / "kazakh_errors.json"

MODELS = [
    ("openrouter", "openai/gpt-4o-mini"),
    ("openrouter", "deepseek/deepseek-chat"),
    ("openrouter", "meta-llama/llama-3.3-70b-instruct"),
    ("openrouter", "openai/gpt-4o-mini"),
    ("openrouter", "deepseek/deepseek-chat"),
    ("openrouter", "meta-llama/llama-3.3-70b-instruct"),
]


def load_sentences() -> list[dict]:
    """The eight corrupted sentences and their published originals."""
    return json.loads(DATA.read_text(encoding="utf-8"))["sentences"]


def build_prompt(corrupted: str) -> str:
    """Ask for a corrected sentence AND a list of the changes made."""
    return f"""The following text is in Kazakh, but it contains errors (incorrect letters, missing hyphens, joined words, or Cyrillic/Latin homoglyphs).

Corrupted text:
"{corrupted}"

Please correct all errors in the text. Return ONLY a valid JSON object without markdown formatting outside, in this exact structure:
{{
  "corrected": "<corrected sentence in Kazakh>",
  "changes": ["<description of change 1>", "<description of change 2>"]
}}"""


def parse_response(text: str) -> dict:
    """Pull {"corrected": str, "changes": list} out of the model's reply."""
    cleaned = text.strip()

    if "```" in cleaned:
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
        cleaned = cleaned.strip()

    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match:
        cleaned = match.group(0)

    try:
        data = json.loads(cleaned)
        if "corrected" in data:
            if "changes" not in data or not isinstance(data["changes"], list):
                data["changes"] = ["Corrected sentence structure"]
            return data
    except Exception:
        pass

    if len(cleaned) > 0 and not cleaned.startswith("User Safety"):
        return {"corrected": cleaned, "changes": ["Corrected formatting"]}

    raise ValueError(f"Could not parse valid JSON from response: {text}")


def correct_with(model: str, corrupted: str, via: str) -> dict:
    """Send one sentence to one model."""
    prompt = build_prompt(corrupted)
    res = ask_once(prompt, model=model, via=via)
    parsed = parse_response(res["text"])

    return {
        "corrected": parsed.get("corrected", ""),
        "changes": parsed.get("changes", []),
        "input_tokens": res["input_tokens"],
        "output_tokens": res["output_tokens"],
        "model": model,
    }


def correct_with_timeout(
    model: str, corrupted: str, via: str, timeout_sec: float = 30.0
) -> dict:
    """Вызов correct_with с жестким тайм-аутом на уровне потока."""
    result = {}
    exception = []

    def target():
        try:
            res = correct_with(model, corrupted, via)
            result.update(res)
        except Exception as e:
            exception.append(e)

    thread = threading.Thread(target=target)
    thread.daemon = True
    thread.start()
    thread.join(timeout=timeout_sec)

    if thread.is_alive():
        raise TimeoutError(f"Request timed out after {timeout_sec}s")

    if exception:
        raise exception[0]

    return result


def score_correction(returned: str, expected: str) -> dict:
    """Compare a model's output against the published original."""
    ret = returned.strip()
    exp = expected.strip()

    exact = ret == exp
    char_diff = abs(len(ret) - len(exp))

    min_len = min(len(ret), len(exp))
    for i in range(min_len):
        if ret[i] != exp[i]:
            char_diff += 1

    return {"exact": exact, "char_diff": char_diff}


def run_all() -> list[dict]:
    """Every model against every sentence. One row per (model, sentence)."""
    rows = []
    sentences = load_sentences()
    for idx, (via, model) in enumerate(MODELS, 1):
        m_name = f"model_run_{idx}"
        print(f"--- Processing {m_name} ({idx}/6) ---")
        for s in sentences:
            s_id = s["id"]
            print(f"  Sending Sentence {s_id}...", end=" ", flush=True)
            try:
                r = correct_with_timeout(
                    model, s["corrupted"], via, timeout_sec=30.0
                )
                rate_in, rate_out = RATES_PER_MTOK.get(model, (0.0, 0.0))
                rows.append(
                    {
                        "model": m_name,
                        "id": s_id,
                        "errors": s["errors"],
                        "corrected": r["corrected"],
                        "changes": r["changes"],
                        **score_correction(r["corrected"], s["correct"]),
                        "cost": estimate_cost(
                            r["input_tokens"],
                            r["output_tokens"],
                            rate_in,
                            rate_out,
                        ),
                        "input_tokens": r["input_tokens"],
                        "output_tokens": r["output_tokens"],
                    }
                )
                print("OK")
            except Exception as exc:
                print(f"FAILED ({exc})")
                rows.append(
                    {
                        "model": m_name,
                        "id": s_id,
                        "errors": s["errors"],
                        "failed": repr(exc),
                    }
                )
            time.sleep(0.3)
    return rows


def summarise(rows: list[dict]) -> None:
    """Per-model totals, to paste into SUBMISSION.md."""
    print(
        f"\n{'model':25}{'exact':>7}{'failed':>8}{'tokens':>9}{'cost $':>10}"
    )
    print("-" * 60)
    for idx in range(1, 7):
        m_name = f"model_run_{idx}"
        mine = [r for r in rows if r["model"] == m_name]
        exact = sum(1 for r in mine if r.get("exact"))
        failed = sum(1 for r in mine if r.get("failed"))
        toks = sum(
            r.get("input_tokens", 0) + r.get("output_tokens", 0)
            for r in mine
        )
        cost = sum(r.get("cost", 0.0) for r in mine)
        print(f"{m_name:25}{exact:>7}{failed:>8}{toks:>9}{cost:>10.5f}")


if __name__ == "__main__":
    out = run_all()
    summarise(out)
    dest = Path(__file__).resolve().parent.parent / "outputs"
    dest.mkdir(exist_ok=True)
    (dest / "corrections.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\nwrote outputs/corrections.json ({len(out)} rows)")