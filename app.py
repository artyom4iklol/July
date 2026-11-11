from datetime import date
from pathlib import Path
import hmac
import secrets
import sqlite3

from flask import Flask, abort, g, redirect, render_template, request, session, url_for


def create_app(config=None):
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=secrets.token_hex(32),
        DATABASE=Path(app.instance_path) / "july.sqlite3",
        MAX_CONTENT_LENGTH=128 * 1024,
        SESSION_COOKIE_SAMESITE="Strict",
    )
    if config:
        app.config.update(config)

    def db():
        if "db" not in g:
            g.db = sqlite3.connect(app.config["DATABASE"])
            g.db.row_factory = sqlite3.Row
            g.db.execute("PRAGMA foreign_keys = ON")
        return g.db

    @app.teardown_appcontext
    def close_db(_error):
        connection = g.pop("db", None)
        if connection is not None:
            connection.close()

    Path(app.config["DATABASE"]).parent.mkdir(parents=True, exist_ok=True)
    with app.app_context():
        db().executescript(Path(app.root_path, "schema.sql").read_text(encoding="utf-8"))

    @app.before_request
    def check_csrf():
        if request.method == "POST":
            expected = session.get("csrf")
            submitted = request.form.get("csrf", "")
            if not expected or not hmac.compare_digest(expected.encode(), submitted.encode()):
                abort(400, "Обновите страницу и отправьте форму ещё раз.")

    @app.context_processor
    def template_values():
        if "csrf" not in session:
            session["csrf"] = secrets.token_urlsafe(32)
        return {"csrf": session["csrf"], "today": date.today().isoformat()}

    def fields(*names):
        return tuple(request.form.get(name, "").strip() for name in names)

    def student_record(student_id):
        student = db().execute("SELECT * FROM students WHERE id = ?", (student_id,)).fetchone()
        if student is None:
            abort(404)
        return student

    @app.get("/")
    def index():
        students = db().execute("SELECT * FROM students ORDER BY name, id").fetchall()
        return render_template("index.html", students=students)

    @app.post("/students")
    def add_student():
        profile = fields("name", "level", "goals", "notes")
        if not profile[0]:
            abort(400, "Укажите имя ученика.")
        with db() as connection:
            cursor = connection.execute(
                "INSERT INTO students (name, level, goals, notes) VALUES (?, ?, ?, ?)", profile
            )
        return redirect(url_for("student_page", student_id=cursor.lastrowid), code=303)

    @app.route("/students/<int:student_id>", methods=["GET", "POST"])
    def student_page(student_id):
        student = student_record(student_id)
        if request.method == "POST":
            profile = fields("name", "level", "goals", "notes")
            if not profile[0]:
                abort(400, "Укажите имя ученика.")
            with db() as connection:
                connection.execute(
                    "UPDATE students SET name = ?, level = ?, goals = ?, notes = ? WHERE id = ?",
                    (*profile, student_id),
                )
            return redirect(url_for("student_page", student_id=student_id), code=303)
        lessons = db().execute(
            "SELECT * FROM lessons WHERE student_id = ? ORDER BY lesson_date DESC, id DESC",
            (student_id,),
        ).fetchall()
        latest = next((lesson for lesson in lessons if lesson["status"] == "completed"), None)
        return render_template("student.html", student=student, lessons=lessons, latest=latest)

    @app.post("/students/<int:student_id>/lessons")
    def add_lesson(student_id):
        student_record(student_id)
        topic, lesson_date, analysis = fields("topic", "lesson_date", "analysis")
        if not topic or not analysis:
            abort(400, "Укажите тему и запишите анализ перед занятием.")
        try:
            lesson_date = date.fromisoformat(lesson_date).isoformat()
        except ValueError:
            abort(400, "Укажите корректную дату занятия.")
        with db() as connection:
            cursor = connection.execute(
                "INSERT INTO lessons (student_id, topic, lesson_date, analysis) VALUES (?, ?, ?, ?)",
                (student_id, topic, lesson_date, analysis),
            )
        return redirect(url_for("lesson_page", lesson_id=cursor.lastrowid), code=303)

    stages = {
        "analysis": ("prepared", ("plan", "questions"), ("plan", "questions")),
        "prepared": ("held", ("lesson_notes",), ()),
        "held": ("completed", ("answers", "result", "next_steps"), ("answers", "result")),
    }

    @app.route("/lessons/<int:lesson_id>", methods=["GET", "POST"])
    def lesson_page(lesson_id):
        lesson = db().execute("SELECT * FROM lessons WHERE id = ?", (lesson_id,)).fetchone()
        if lesson is None:
            abort(404)
        if request.method == "POST":
            status = lesson["status"]
            if status not in stages or request.form.get("status") != status:
                abort(409, "Этап занятия уже изменился. Откройте карточку заново.")
            next_status, names, required = stages[status]
            values = dict(zip(names, fields(*names)))
            if any(not values[name] for name in required):
                abort(400, "Заполните обязательные поля.")
            assignments = ", ".join(f"{name} = ?" for name in names)
            with db() as connection:
                cursor = connection.execute(
                    f"UPDATE lessons SET {assignments}, status = ? WHERE id = ? AND status = ?",
                    (*values.values(), next_status, lesson_id, status),
                )
                if cursor.rowcount != 1:
                    abort(409, "Этап занятия уже изменился. Откройте карточку заново.")
            return redirect(url_for("lesson_page", lesson_id=lesson_id), code=303)
        student = student_record(lesson["student_id"])
        return render_template("lesson.html", lesson=lesson, student=student)

    @app.errorhandler(400)
    @app.errorhandler(404)
    @app.errorhandler(409)
    def error_page(error):
        return render_template("error.html", error=error), error.code

    return app
