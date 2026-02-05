import json
import os

# -------------------------------
# Constants
# -------------------------------

QUESTIONS_DIR = "questions"
PERFORMANCE_FILE = "performance.json"

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
# File Handling
# -------------------------------


def load_questions(level, subject):
    filename = f"{level}_{subject}.json"
    path = os.path.join(QUESTIONS_DIR, filename)
    if not os.path.exists(path):
        print(f"Error: {filename} not found in {QUESTIONS_DIR}")
        return []
    with open(path, "r") as file:
        return json.load(file)


def load_performance():
    if not os.path.exists(PERFORMANCE_FILE):
        return {}
    try:
        with open(PERFORMANCE_FILE, "r") as file:
            content = file.read().strip()
            if not content:  # file is empty
                return {}
            return json.loads(content)
    except json.JSONDecodeError:
        print("Warning: performance.json is corrupted or invalid. Starting fresh.")
        return {}


def save_performance(performance):
    with open(PERFORMANCE_FILE, "w") as file:
        json.dump(performance, file, indent=4)


# -------------------------------
# Utility Functions
# -------------------------------


def choose_option(options, prompt):
    while True:
        print(prompt)
        for i, option in enumerate(options, 1):
            print(f"{i}. {option.replace('_', ' ')}")
        choice = input("Enter number: ")
        if choice.isdigit():
            choice = int(choice)
            if 1 <= choice <= len(options):
                return options[choice - 1]
        print("Invalid input. Please try again.\n")


def get_accuracy(data):
    if data["attempted"] == 0:
        return 0
    return data["correct"] / data["attempted"]


# -------------------------------
# Quiz Logic
# -------------------------------


def ask_question(question, performance, key):
    topic = question["topic"]
    correct_answer = question["answer"]

    # support multiple keyword answers
    if isinstance(correct_answer, list):
        correct_answer = [a.lower().strip() for a in correct_answer]
    else:
        correct_answer = [correct_answer.lower().strip()]

    user_answer = input(question["question"] + " ").lower().strip()

    if topic not in performance[key]:
        performance[key][topic] = {"attempted": 0, "correct": 0}

    performance[key][topic]["attempted"] += 1

    if any(ans in user_answer for ans in correct_answer):
        print("✅ Correct!\n")
        performance[key][topic]["correct"] += 1
    else:
        print(f"❌ Incorrect. Correct answer: {', '.join(correct_answer)}\n")


# -------------------------------
# Summary
# -------------------------------


def show_summary(data):
    print("\nSession Summary")
    print("----------------")
    for topic, stats in data.items():
        accuracy = get_accuracy(stats) * 100
        print(f"{topic}: {accuracy:.1f}% correct")


# -------------------------------
# Main Program
# -------------------------------


def main():
    print("Adaptive Revision & Quiz System")
    print("-------------------------------\n")

    performance = load_performance()

    level = choose_option(LEVELS, "Choose qualification level:")
    subject = choose_option(SUBJECTS, "Choose subject:")

    key = f"{level}_{subject}"

    if key not in performance:
        performance[key] = {}

    questions = load_questions(level, subject)
    if not questions:
        print("No questions found for this subject/level. Exiting.")
        return

    print(f"\nStarting quiz: {level} {subject.replace('_', ' ')}\n")

    for question in questions:
        ask_question(question, performance, key)

    save_performance(performance)
    show_summary(performance[key])


# -------------------------------
# Run Program
# -------------------------------

if __name__ == "__main__":
    main()
