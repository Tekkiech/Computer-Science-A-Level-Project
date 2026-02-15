import difflib
import json
import os
import re
import sys
import unicodedata
from typing import Optional

# rapidfuzz is an optional dependency that provides higher-quality fuzzy
# matching for short text answers (it handles token ordering and small edits
# more gracefully). If it's not installed the program will still run using
# Python's built-in difflib.
try:
    from rapidfuzz import fuzz  # type: ignore

    _HAS_RAPIDFUZZ = True
except Exception:
    # Keep a safe fallback so the rest of the code can check the flag and use
    # difflib when necessary.
    fuzz = None
    _HAS_RAPIDFUZZ = False

# -------------------------------
# Project configuration
# -------------------------------
# Directory containing the per-subject question JSON files and the filename
# used to persist a student's performance between sessions.
QUESTIONS_DIR = "questions"
PERFORMANCE_FILE = "performance.json"

# Supported qualification levels and the subjects available in the question
# bank. These strings are used to construct filenames such as
# 'ALevel_Computer_Science.json'.
LEVELS = ["GCSE", "ALevel"]
SUBJECTS = [
    "Maths",
    "Further_Maths",
    "Physics",
    "Biology",
    "Chemistry",
    "Computer_Science",
]


# -------------------------------
# Small UI helpers
# -------------------------------
def clear_screen():
    """Clear the terminal so the text UI remains tidy.

    This function is intentionally simple and cross-platform (Windows vs POSIX).
    It makes the CLI feel a little cleaner during a live demo or coursework
    run-through.
    """
    os.system("cls" if os.name == "nt" else "clear")


# -------------------------------
# File handling helpers
# -------------------------------
def load_questions(level, subject):
    """Load the question list for the given level and subject.

    Expects files named like "<level>_<subject>.json" inside the questions
    directory. If the file is missing an empty list is returned so the caller
    can handle the condition without exceptions during a demo.
    """
    filename = f"{level}_{subject}.json"
    path = os.path.join(QUESTIONS_DIR, filename)
    if not os.path.exists(path):
        print(f"Error: {filename} not found in {QUESTIONS_DIR}")
        return []
    with open(path, "r") as file:
        return json.load(file)


def load_performance():
    """Read stored performance data from disk.

    The performance file stores how many questions the student attempted and
    how many they answered correctly per topic. If the file is missing or
    empty we return an empty dictionary so the app starts fresh. If the JSON is
    corrupted we warn and also return an empty dataset — this is simpler than
    attempting to repair the file for a small coursework project.
    """
    if not os.path.exists(PERFORMANCE_FILE):
        return {}
    try:
        with open(PERFORMANCE_FILE, "r") as file:
            content = file.read().strip()
            if not content:
                return {}
            return json.loads(content)
    except json.JSONDecodeError:
        print("Warning: performance.json is corrupted. Starting fresh.\n")
        return {}


def save_performance(performance):
    """Persist performance data as pretty JSON for easy inspection."""
    with open(PERFORMANCE_FILE, "w") as file:
        json.dump(performance, file, indent=4)


# -------------------------------
# CLI utility functions
# -------------------------------
def choose_option(options, prompt, allow_back=False):
    """Show a numbered menu and return the selected option.

    This helper keeps the input method consistent and simple so the UI is
    straightforward to follow during marking/demonstration. If `allow_back` is
    True a 'Go back' option is included for nested menus.
    """
    while True:
        print("\n" + prompt)
        for i, option in enumerate(options, 1):
            print(f"{i}. {option.replace('_', ' ')}")
        extra = 0
        if allow_back:
            extra = 1
            print(f"{len(options) + 1}. Go back")
        print(f"{len(options) + 1 + extra}. Exit")

        choice = input("Enter number: ").strip()
        if choice.isdigit():
            choice = int(choice)
            if 1 <= choice <= len(options):
                return options[choice - 1]
            elif allow_back and choice == len(options) + 1:
                return "BACK"
            elif choice == len(options) + 1 + extra:
                print("Exiting program. Goodbye!")
                sys.exit()
        print("Invalid input. Please try again.")


def get_accuracy(data):
    """Return the accuracy (correct/attempted) as a fraction 0..1."""
    if data["attempted"] == 0:
        return 0
    return data["correct"] / data["attempted"]


# -------------------------------
# Quiz logic and answer matching
# -------------------------------
def ask_question(question, performance, key):
    """Ask a single question, accept flexible answers and update performance.

    The matching logic is intentionally forgiving to make revision sessions
    smoother for students: it normalises case and punctuation, accepts small
    word-number variants (e.g. 'three' vs '3'), handles option letters
    ('A', 'a)') and applies a conservative fuzzy-match threshold for minor
    typos or spelling differences.

    For a larger system these helpers would be extracted to a utility module
    with unit tests, but for the coursework project we keep them local and
    readable within this function.
    """

    # --- Local normalisation helpers ---
    def normalize_text(s: str) -> str:
        """Normalise a string to a lower, ascii-ish form suitable for comparison.

        - Applies Unicode NFKC normalisation
        - Converts to lowercase
        - Replaces common typographic quotes
        - Removes non-alphanumeric characters (except spaces)
        - Collapses whitespace
        """
        if s is None:
            return ""
        s = str(s)
        s = unicodedata.normalize("NFKC", s)
        s = s.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
        s = s.strip().lower()
        s = re.sub(r"[^0-9a-z\s]", " ", s)
        s = re.sub(r"\s+", " ", s).strip()
        return s

    def normalize_option(s: str) -> str:
        """Extract a canonical token from short option-style answers.

        Examples:
          - "A.", "a)" -> "a"
          - "1." -> "1"

        This helps match student input for multiple-choice style answers.
        """
        s = normalize_text(s)
        if not s:
            return ""
        parts = s.split()
        first = parts[0]
        m = re.match(r"^([a-zA-Z0-9])[\.\)]?$", first)
        if m:
            return m.group(1)
        return s

    # small word->number mapping for common number-words (expandable)
    _WORD_NUMS = {
        "zero": 0,
        "one": 1,
        "two": 2,
        "three": 3,
        "four": 4,
        "five": 5,
        "six": 6,
        "seven": 7,
        "eight": 8,
        "nine": 9,
        "ten": 10,
        "eleven": 11,
        "twelve": 12,
        "thirteen": 13,
        "fourteen": 14,
        "fifteen": 15,
        "sixteen": 16,
        "seventeen": 17,
        "eighteen": 18,
        "nineteen": 19,
        "twenty": 20,
        "thirty": 30,
        "forty": 40,
        "fifty": 50,
        "sixty": 60,
        "seventy": 70,
        "eighty": 80,
        "ninety": 90,
    }

    def word_number_to_int(s: str) -> Optional[int]:
        """Convert small spelled-out numbers (e.g. 'twenty one') to an int.

        Returns None if the text cannot be parsed as a simple word-number.
        """
        s = normalize_text(s)
        if not s:
            return None
        parts = s.split()
        total = 0
        i = 0
        while i < len(parts):
            w = parts[i]
            if w in _WORD_NUMS:
                val = _WORD_NUMS[w]
                # handle constructs like "twenty one"
                if (
                    val >= 20
                    and i + 1 < len(parts)
                    and parts[i + 1] in _WORD_NUMS
                    and _WORD_NUMS[parts[i + 1]] < 10
                ):
                    total += val + _WORD_NUMS[parts[i + 1]]
                    i += 2
                    continue
                total += val
                i += 1
            else:
                return None
        return total

    def is_numeric(s: str) -> Optional[float]:
        """Try to interpret a string as a numeric value.

        Accepts plain digits (including floats) and small spelled-out numbers.
        """
        s_norm = normalize_text(s)
        if not s_norm:
            return None
        try:
            return float(s_norm)
        except ValueError:
            pass
        wn = word_number_to_int(s_norm)
        if wn is not None:
            return float(wn)
        return None

    def _fuzzy_ratio(a: str, b: str) -> float:
        """Return a similarity score between 0 and 100 for two strings.

        Prefer rapidfuzz.token_sort_ratio when available; otherwise fall back
        to difflib's SequenceMatcher scaled to 0..100.
        """
        try:
            if (
                _HAS_RAPIDFUZZ
                and fuzz is not None
                and hasattr(fuzz, "token_sort_ratio")
            ):
                score = fuzz.token_sort_ratio(a, b)
                return float(score)
        except Exception:
            # If rapidfuzz fails for any reason, we'll quietly fall back.
            pass
        return difflib.SequenceMatcher(None, a, b).ratio() * 100.0

    # --- End local helpers ---

    topic = question["topic"]
    correct_answer = question["answer"]

    # Accept either a single canonical answer or a list of acceptable answers
    # (useful to include synonyms, abbreviations or alternate phrasings).
    if isinstance(correct_answer, list):
        correct_answers_raw = correct_answer
    else:
        correct_answers_raw = [correct_answer]

    user_answer_raw = input("\n" + question["question"] + " ")
    user_norm = normalize_text(user_answer_raw)
    user_option = normalize_option(user_answer_raw)

    # Ensure the performance tracking structure exists for this topic.
    if topic not in performance[key]:
        performance[key][topic] = {"attempted": 0, "correct": 0}

    performance[key][topic]["attempted"] += 1

    accepted = False
    matched = None
    fuzzy_threshold = 88.0  # conservative default for short answers

    for ca_raw in correct_answers_raw:
        ca_norm = normalize_text(ca_raw)
        ca_option = normalize_option(ca_raw)

        # 1) exact normalized match (case / punctuation removed)
        if user_norm and ca_norm and user_norm == ca_norm:
            accepted = True
            matched = ca_raw
            break

        # 2) option letter/number equivalence for multiple-choice style answers
        if user_option and ca_option and user_option == ca_option:
            accepted = True
            matched = ca_raw
            break

        # 3) numeric matching: allow 'three' <-> '3' comparisons
        ua_num = is_numeric(user_answer_raw)
        ca_num = is_numeric(ca_raw)
        if ua_num is not None and ca_num is not None:
            if abs(ua_num - ca_num) < 1e-9:
                accepted = True
                matched = ca_raw
                break

        # 4) containment: allow short correct tokens inside a longer student reply
        if ca_norm and ca_norm in user_norm:
            accepted = True
            matched = ca_raw
            break

        # 5) conservative fuzzy match to catch minor typos / small differences
        if ca_norm and user_norm:
            score = _fuzzy_ratio(user_norm, ca_norm)
            if score >= fuzzy_threshold:
                accepted = True
                matched = ca_raw
                break

    if accepted:
        # Friendly feedback that shows which stored answer was accepted. This
        # makes it clearer during testing and marking why an answer matched.
        if matched:
            print(f"✅ Correct! (accepted: {matched})\n")
        else:
            print("✅ Correct!\n")
        performance[key][topic]["correct"] += 1
    else:
        # When marking incorrect, display the canonical accepted answers so the
        # learner can see what was expected and learn from the feedback.
        display_correct = ", ".join(str(a) for a in correct_answers_raw)
        print(f"❌ Incorrect. Correct answer: {display_correct}\n")


# -------------------------------
# Performance reporting
# -------------------------------
def view_performance(performance):
    """Print a compact, human-readable summary of recorded performance.

    The report is grouped by the level_subject key (e.g. 'ALevel_Computer_Science')
    and shows per-topic accuracy. This simple reporting is suitable for a
    coursework demo where a teacher or student needs a quick overview.
    """
    clear_screen()
    if not performance:
        print("\nNo performance data found.\n")
        input("Press Enter to return to main menu...")
        return

    print("\nAll Recorded Performance:\n------------------------")
    for key, topics in performance.items():
        print(f"\n{key.replace('_', ' ')}:")
        for topic, stats in topics.items():
            accuracy = get_accuracy(stats) * 100
            print(
                f"  {topic}: {accuracy:.1f}% correct ({stats['correct']}/{stats['attempted']})"
            )
    print("\nEnd of performance data.\n")
    input("Press Enter to return to main menu...")


# -------------------------------
# Main menu and control flow
# -------------------------------
def main_menu():
    """Top-level menu for students to start quizzes and view performance.

    The interface is intentionally minimal and text-based so it is easy to
    understand and mark for A-Level coursework. It guides the student through
    choosing qualification level, subject and running a quiz session.
    """
    performance = load_performance()

    while True:
        clear_screen()
        print("=== Adaptive Revision & Quiz System ===\n")
        print("Main Menu:")
        print("1. Start Quiz")
        print("2. View Performance")
        print("3. Exit")

        choice = input("\nEnter number: ").strip()
        if choice == "1":
            start_quiz(performance)
        elif choice == "2":
            view_performance(performance)
        elif choice == "3":
            print("Exiting program. Goodbye!")
            sys.exit()
        else:
            print("Invalid input. Please try again.\n")


def start_quiz(performance):
    """Run a quiz session for a chosen level and subject.

    This function collects the user's level and subject choices, loads the
    relevant questions, runs each question and saves the updated performance
    at the end of the session.
    """
    clear_screen()
    level = choose_option(LEVELS, "Choose qualification level:", allow_back=True)
    if level == "BACK":
        return

    clear_screen()
    subject = choose_option(SUBJECTS, "Choose subject:", allow_back=True)
    if subject == "BACK":
        return

    key = f"{level}_{subject}"
    if key not in performance:
        performance[key] = {}

    questions = load_questions(level, subject)
    if not questions:
        print("No questions found for this subject/level. Returning to main menu.\n")
        input("Press Enter to continue...")
        return

    print(f"\nStarting quiz: {level} {subject.replace('_', ' ')}\n")

    for question in questions:
        ask_question(question, performance, key)

    save_performance(performance)
    print("\n--- Session Summary ---")
    show_summary(performance[key])
    input("\nPress Enter to return to main menu...")


def show_summary(data):
    """Print a short topic-by-topic accuracy summary for the session."""
    for topic, stats in data.items():
        accuracy = get_accuracy(stats) * 100
        print(
            f"{topic}: {accuracy:.1f}% correct ({stats['correct']}/{stats['attempted']})"
        )


# -------------------------------
# Script entry point
# -------------------------------
if __name__ == "__main__":
    main_menu()
