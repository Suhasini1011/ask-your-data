"""Run every test question through the assistant, compare with the known answer, and report accuracy.
Run with: python evaluate.py"""
import json
import time
from decimal import Decimal

from assistant import ask


def numbers_in(row):
    return [float(v) for v in row if isinstance(v, (int, float, Decimal)) and not isinstance(v, bool)]


def grade(test, result):
    """Return (passed, what the assistant gave)."""
    kind = test["kind"]

    if kind == "refuse":
        refused = result["error"] is not None and not result["rows"]
        return refused, (result["error"] or "answered instead of refusing")[:80]

    if result["error"] or not result["rows"]:
        return False, (result["error"] or "no rows")[:80]

    first_row = result["rows"][0]

    if kind == "text":
        values = [str(v).strip().lower() for v in first_row]
        return test["expected"].lower() in values, ", ".join(values)[:80]

    values = numbers_in(first_row)
    for value in values:
        if abs(value - test["expected"]) <= test["tolerance"]:
            return True, f"{value:g}"
        # A percentage given as a fraction (0.0679 instead of 6.79) is the same answer
        if kind == "percent" and abs(value * 100 - test["expected"]) <= test["tolerance"]:
            return True, f"{value:g} (as a fraction)"
    return False, ", ".join(f"{v:g}" for v in values)[:80] or "no number"


def main():
    tests = json.load(open("eval_questions.json"))
    rows = []
    passed_count = 0

    for number, test in enumerate(tests, start=1):
        result = ask(test["question"])
        passed, got = grade(test, result)
        passed_count += passed
        print(f"{number:>2}. {'PASS' if passed else 'FAIL'}  {test['question']}\n    expected {test['expected']}, got {got}")
        rows.append((number, test, passed, got, result))
        time.sleep(2)  # stay well inside the free API rate limit

    accuracy = 100 * passed_count / len(tests)
    print(f"\nAccuracy: {passed_count} of {len(tests)} ({accuracy:.0f}%)")

    with open("eval_results.md", "w") as f:
        f.write(f"# Evaluation results\n\n**Accuracy: {passed_count} of {len(tests)} ({accuracy:.0f}%)**\n\n")
        f.write("| # | Question | Expected | Got | Result |\n|---|---|---|---|---|\n")
        for number, test, passed, got, _ in rows:
            f.write(f"| {number} | {test['question']} | {test['expected']} | {got} | {'Pass' if passed else 'Fail'} |\n")
        f.write("\n## SQL for each question\n")
        for number, test, passed, got, result in rows:
            f.write(f"\n### {number}. {test['question']}\n\n```sql\n{result['sql'] or '(no query)'}\n```\n")
    print("Saved eval_results.md")


if __name__ == "__main__":
    main()
