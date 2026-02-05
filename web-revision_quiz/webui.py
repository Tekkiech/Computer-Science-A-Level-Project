import json
import os

from flask import Flask, redirect, render_template, request, url_for
from main import ask_question, load_performance, load_questions, save_performance

app = Flask(__name__)

PERFORMANCE_FILE = "performance.json"


# -------------------------------
# Load performance
# -------------------------------
def load_perf():
    if not os.path.exists(PERFORMANCE_FILE):
        return {}
    with open(PERFORMANCE_FILE, "r") as f:
        content = f.read().strip()
        return json.loads(content) if content else {}


# -------------------------------
# Web Routes
# -------------------------------
@app.route("/")
def index():
    return """
        <h1>Revision Quiz</h1>
        <a href='/quiz'>Start Quiz</a> |
        <a href='/performance'>View Performance</a>
    """


@app.route("/quiz", methods=["GET", "POST"])
def quiz():
    level = "GCSE"  # You could add dropdowns in templates to select level/subject
    subject = "Maths"
    questions = load_questions(level, subject)
    performance = load_perf()
    key = f"{level}_{subject}"
    if key not in performance:
        performance[key] = {}

    if request.method == "POST":
        q_index = int(request.form["q_index"])
        user_answer = request.form["answer"]
        # Wrap CLI ask_question for web use
        question = questions[q_index]
        topic = question["topic"]
        correct_answer = question["answer"]
        if isinstance(correct_answer, list):
            correct_answer = [a.lower().strip() for a in correct_answer]
        else:
            correct_answer = [correct_answer.lower().strip()]
        if topic not in performance[key]:
            performance[key][topic] = {"attempted": 0, "correct": 0}
        performance[key][topic]["attempted"] += 1
        if any(ans in user_answer.lower().strip() for ans in correct_answer):
            performance[key][topic]["correct"] += 1

        save_performance(performance)

        next_q = q_index + 1
        if next_q >= len(questions):
            return redirect(url_for("summary", key=key))
        return redirect(url_for("quiz", q_index=next_q))

    # GET request
    q_index = int(request.args.get("q_index", 0))
    question = questions[q_index]
    return f"""
        <h2>Question {q_index + 1} of {len(questions)}</h2>
        <p>{question["question"]}</p>
        <form method='POST'>
            <input type='hidden' name='q_index' value='{q_index}'>
            <input type='text' name='answer' autofocus>
            <button type='submit'>Submit</button>
        </form>
        <p><a href='/'>Exit Quiz</a></p>
    """


@app.route("/summary/<key>")
def summary(key):
    performance = load_perf()
    if key not in performance:
        return "<p>No performance data for this quiz.</p><a href='/'>Back</a>"
    html = "<h1>Quiz Summary</h1>"
    for topic, stats in performance[key].items():
        attempted = stats["attempted"]
        correct = stats["correct"]
        accuracy = (correct / attempted) * 100 if attempted else 0
        html += f"<p>{topic}: {accuracy:.1f}% correct ({correct}/{attempted})</p>"
    html += "<p><a href='/'>Back to Main Menu</a></p>"
    return html


@app.route("/performance")
def performance():
    performance = load_perf()
    html = "<h1>All Performance</h1>"
    for key, topics in performance.items():
        html += f"<h2>{key.replace('_', ' ')}</h2>"
        for topic, stats in topics.items():
            attempted = stats["attempted"]
            correct = stats["correct"]
            accuracy = (correct / attempted) * 100 if attempted else 0
            html += f"<p>{topic}: {accuracy:.1f}% ({correct}/{attempted})</p>"
    html += "<p><a href='/'>Back</a></p>"
    return html


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
