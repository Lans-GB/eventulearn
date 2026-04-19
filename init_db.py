import sqlite3

conn = sqlite3.connect("database.db")
cur = conn.cursor()

# USERS TABLE (CREATE IF NOT EXISTS)

cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    sr_code TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    role TEXT DEFAULT 'student',
    year_level TEXT
)
""")

# department
try:
    cur.execute("ALTER TABLE users ADD COLUMN department TEXT")
except:
    pass

# program
try:
    cur.execute("ALTER TABLE users ADD COLUMN program TEXT")
except:
    pass

# EVENTS TABLE

cur.execute("""
CREATE TABLE IF NOT EXISTS events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_name TEXT,
    organizer TEXT,
    venue TEXT,
    price REAL,
    event_date TEXT,
    capacity INTEGER,
    event_type TEXT,
    year_levels TEXT,
    department TEXT,
    program TEXT,
    short_desc TEXT,
    long_desc TEXT,
    poster TEXT,
    icon TEXT
)
""")


# REGISTRATIONS TABLE

cur.execute("""
CREATE TABLE IF NOT EXISTS registrations (
    reg_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    event_id INTEGER NOT NULL,
    qr_code TEXT UNIQUE,
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (event_id) REFERENCES events(event_id)
)
""")

# SAMPLE USERS (UPDATED)
cur.execute("""
INSERT OR IGNORE INTO users (name, sr_code, password, role, year_level, department, program)
VALUES ('Admin', '24-34712', 'admin123', 'admin', '4th', 'CICS', 'IT')
""")

cur.execute("""
INSERT OR IGNORE INTO users (name, sr_code, password, role, year_level, department, program)
VALUES ('Student', '24-35610', 'student123', 'student', '2nd', 'CICS', 'IT')
""")

conn.commit()
conn.close()

print("Database updated successfully!")