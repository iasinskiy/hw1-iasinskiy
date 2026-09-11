import json
import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()


def build_system_prompt(catalogue: dict) -> str:
    
    student = catalogue.get("student", {})
    courses = catalogue.get("courses", [])
    rules = catalogue.get("rules", {})

    completed = student.get("completed_courses", [])
    max_credits = rules.get("max_credits", 18)

    prompt = f"""You are an academic advisor at Narxoz University helping a student register for courses.

STUDENT PROFILE:
- Completed courses: {', '.join(completed)}

REGISTRATION RULES:
- Maximum credits per semester: {max_credits}
- You MUST check prerequisites: student cannot register for a course if they haven't completed its prerequisites.
- You MUST check schedule conflicts: student cannot register for two courses that meet at the exact same time.
- You MUST check seat availability: student cannot register if remaining_seats is 0.
- STRICT RULE: You MUST REFUSE any attempt to register for courses NOT listed in the catalogue below. Do NOT invent or accept external courses under any circumstances.

COURSE CATALOGUE:
"""
    for course in courses:
        code = course.get("code", course.get("id", "N/A"))
        title = course.get("title", course.get("name", "N/A"))
        credits_num = course.get("credits", "N/A")
        schedule = course.get("schedule", course.get("time", "N/A"))
        prereqs = course.get("prerequisites", [])
        seats = course.get("remaining_seats", course.get("seats", "N/A"))

        prompt += (
            f"- {code}: {title} ({credits_num} credits) | "
            f"Time: {schedule} | Prerequisites: {prereqs} | "
            f"Seats left: {seats}\n"
        )

    return prompt.strip()


def openrouter_client() -> OpenAI:
    
    return OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=os.getenv("OPENROUTER_API_KEY"),
    )


def openai_client() -> OpenAI:
   
    return OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def chat(messages: list, model: str, via: str = "openai") -> dict:
    
    client = openrouter_client() if via == "openrouter" else openai_client()

    response = client.chat.completions.create(
        model=model,
        messages=messages,
    )

    return {
        "text": response.choices[0].message.content,
        "input_tokens": response.usage.prompt_tokens,
        "output_tokens": response.usage.completion_tokens,
        "model": model,
    }


def estimate_cost(
    input_tokens: int, output_tokens: int, rate_in: float, rate_out: float
) -> float:
    
    return (input_tokens * (rate_in / 1_000_000)) + (
        output_tokens * (rate_out / 1_000_000)
    )


def conversation_cost(usages: list, rate_in: float, rate_out: float) -> float:
   
    total_in = sum(u["input_tokens"] for u in usages)
    total_out = sum(u["output_tokens"] for u in usages)
    return estimate_cost(total_in, total_out, rate_in, rate_out)


def run_turn(messages: list, question: str, model: str, via: str) -> dict:
    
    messages.append({"role": "user", "content": question})
    res = chat(messages, model, via)
    messages.append({"role": "assistant", "content": res["text"]})
    return res


SCRIPT = [
    "I am a third-year student. Which courses am I still eligible to register for?",
    "Register me for CSS-4007 and CSS-4102.",
    "How many credits would that be in total, and am I within the limit?",
    "Add CSS-4090 Quantum Machine Learning to my schedule.",
    "На какие из доступных курсов я могу зарегистрироваться?",
]


def main():
    catalogue_path = os.path.join(
        os.path.dirname(__file__), "..", "data", "courses.json"
    )
    with open(catalogue_path, "r", encoding="utf-8") as f:
        catalogue = json.load(f)

    system_prompt = build_system_prompt(catalogue)

    # Прогон 1 через OpenRouter Free Router
    print("=== RUNNING OPENROUTER (Free Router - Model 1) ===")
    messages_free1 = [{"role": "system", "content": system_prompt}]
    usages_free1 = []

    for idx, q in enumerate(SCRIPT, 1):
        usage = run_turn(
            messages_free1,
            q,
            model="openrouter/free",
            via="openrouter",
        )
        usages_free1.append(usage)
        cost = estimate_cost(
            usage["input_tokens"], usage["output_tokens"], 0.0, 0.0
        )
        print(
            f"Turn {idx} | In: {usage['input_tokens']} | Out: {usage['output_tokens']} | Cost: ${cost:.6f}"
        )
        print(f"Bot: {usage['text']}\n" + "-" * 40)

    # Прогон 2 через OpenRouter Free Router
    print("\n=== RUNNING OPENROUTER (Free Router - Model 2) ===")
    messages_free2 = [{"role": "system", "content": system_prompt}]
    usages_free2 = []

    for idx, q in enumerate(SCRIPT, 1):
        usage = run_turn(
            messages_free2,
            q,
            model="openrouter/free",
            via="openrouter",
        )
        usages_free2.append(usage)
        cost = estimate_cost(
            usage["input_tokens"],
            usage["output_tokens"],
            0.0,
            0.0,
        )
        print(
            f"Turn {idx} | In: {usage['input_tokens']} | Out: {usage['output_tokens']} | Cost: ${cost:.6f}"
        )
        print(f"Bot: {usage['text']}\n" + "-" * 40)


if __name__ == "__main__":
    main()