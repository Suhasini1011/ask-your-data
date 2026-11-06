"""Ask your data: turns a plain-English question into SQL, checks it, runs it read-only, and returns the result."""
import json
import os
import re
import sys
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

SCHEMA_NOTES = (Path(__file__).parent / "schema_notes.md").read_text()
MAX_ROWS = 500

SYSTEM_PROMPT = f"""You are a careful data analyst who writes PostgreSQL queries.
You answer questions about an eCommerce database described below. It is your only source of truth.

{SCHEMA_NOTES}

How to answer:
- Write exactly ONE read-only query: a SELECT, or a WITH ... SELECT. Never write anything that changes data.
- Use only tables in the analytics schema, always written as analytics.table_name.
- Follow the business rules above exactly.
- Round percentages and averages to 2 decimal places, and give columns clear names.
- If the question lists rows (top 10, by state, and so on), sort sensibly and add a LIMIT of 50 or less.
- If the database cannot answer the question, do not guess: say so.

Reply with JSON only, in one of these two forms:
{{"sql": "<the query>", "explanation": "<one sentence on how the query answers the question>"}}
{{"cannot_answer": "<short reason>"}}"""

BLOCKED_WORDS = r"\b(insert|update|delete|merge|drop|alter|create|grant|revoke|truncate|copy)\b"


def ask_llm(messages):
    client = OpenAI(api_key=os.getenv("GROQ_API_KEY"), base_url="https://api.groq.com/openai/v1")
    response = client.chat.completions.create(
        model=os.getenv("LLM_MODEL", "openai/gpt-oss-120b"),
        temperature=0,
        messages=messages,
    )
    return response.choices[0].message.content


def parse_reply(text):
    """Pull the JSON object out of the model's reply, even if it is wrapped in other text."""
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError("The model did not reply with JSON.")
    return json.loads(match.group(0))


def check_sql(sql):
    """Return a list of problems. Empty list means the query passed every check."""
    problems = []
    cleaned = re.sub(r"--[^\n]*", "", sql).strip().rstrip(";").strip()
    lowered = cleaned.lower()
    if ";" in cleaned:
        problems.append("more than one statement")
    if not (lowered.startswith("select") or lowered.startswith("with")):
        problems.append("not a SELECT query")
    blocked = re.findall(BLOCKED_WORDS, lowered)
    if blocked:
        problems.append("contains blocked words: " + ", ".join(sorted(set(blocked))))
    if re.search(r"\b(staging|pg_catalog|information_schema)\b|\bpg_", lowered):
        problems.append("uses tables outside the analytics schema")
    return problems, cleaned


def run_sql(sql):
    """Run the query as the read-only user and return column names and rows."""
    with psycopg.connect(
        host=os.getenv("DB_HOST"),
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        sslmode="require",
        connect_timeout=20,
    ) as conn:
        conn.read_only = True
        with conn.cursor() as cur:
            cur.execute(sql)
            columns = [col.name for col in cur.description]
            rows = cur.fetchmany(MAX_ROWS)
    return columns, rows


def ask(question, max_attempts=2):
    """Question in, result out. If the query fails, the error goes back to the model for one fix."""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]
    result = {"question": question, "sql": None, "explanation": None,
              "columns": [], "rows": [], "error": None, "attempts": 0}

    for attempt in range(1, max_attempts + 1):
        result["attempts"] = attempt
        reply = ask_llm(messages)
        try:
            data = parse_reply(reply)
        except (ValueError, json.JSONDecodeError) as exc:
            result["error"] = str(exc)
            break

        if "cannot_answer" in data:
            result["error"] = "Can't answer from this data: " + data["cannot_answer"]
            break

        problems, sql = check_sql(data.get("sql", ""))
        result["sql"] = sql
        result["explanation"] = data.get("explanation")
        if problems:
            result["error"] = "Query blocked by safety checks: " + "; ".join(problems)
            break

        try:
            result["columns"], result["rows"] = run_sql(sql)
            result["error"] = None
            break
        except psycopg.OperationalError as exc:
            # Connection, login or timeout problem: not the query's fault, so don't ask the model to fix it.
            result["error"] = f"Database connection problem: {exc}".strip()
            break
        except psycopg.Error as exc:
            result["error"] = f"Database error: {exc}".strip()
            messages.append({"role": "assistant", "content": reply})
            messages.append({"role": "user", "content":
                             f"That query failed with this error:\n{exc}\nReply with a corrected query, in the same JSON format."})
    return result


if __name__ == "__main__":
    question = " ".join(sys.argv[1:]) or "How many orders were delivered late?"
    answer = ask(question)
    print("Question:", answer["question"])
    print("\nSQL:\n" + (answer["sql"] or "(none)"))
    print("\nHow:", answer["explanation"])
    if answer["error"]:
        print("\nError:", answer["error"])
    else:
        print("\n" + " | ".join(answer["columns"]))
        for row in answer["rows"][:20]:
            print(" | ".join(str(value) for value in row))
    print("\nAttempts:", answer["attempts"])
