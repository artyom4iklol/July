PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS students (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL CHECK (length(trim(name)) > 0),
    level TEXT NOT NULL DEFAULT '',
    goals TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS lessons (
    id INTEGER PRIMARY KEY,
    student_id INTEGER NOT NULL REFERENCES students(id),
    topic TEXT NOT NULL CHECK (length(trim(topic)) > 0),
    lesson_date TEXT NOT NULL,
    analysis TEXT NOT NULL,
    plan TEXT NOT NULL DEFAULT '',
    questions TEXT NOT NULL DEFAULT '',
    lesson_notes TEXT NOT NULL DEFAULT '',
    answers TEXT NOT NULL DEFAULT '',
    result TEXT NOT NULL DEFAULT '',
    next_steps TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'analysis'
        CHECK (status IN ('analysis', 'prepared', 'held', 'completed'))
);

CREATE INDEX IF NOT EXISTS lessons_student_date
    ON lessons(student_id, lesson_date DESC, id DESC);
