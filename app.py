from flask import Flask, render_template, request, redirect, session, send_file
import sqlite3, os, uuid
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib import colors
import qrcode
import io
from datetime import datetime

app = Flask(__name__)
app.secret_key = "secret"

UPLOAD_FOLDER = "static/uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def get_db():
    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    return conn

# LOGIN
@app.route('/', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        db = get_db()
        user = db.execute(
            "SELECT * FROM users WHERE sr_code=? AND password=?",
            (request.form['sr_code'], request.form['password'])
        ).fetchone()

        if user:
            session['user'] = dict(user)
            return redirect('/dashboard')

    return render_template('login.html')

#CREATE EVENT 
@app.route('/create_event', methods=['GET', 'POST'])
def create_event():

    if 'user' not in session:
        return redirect('/')

    if request.method == 'GET':
        return render_template('create_event.html')

    db = get_db()

    #  YEAR LEVELS 
    year_levels = ",".join(request.form.getlist('year_levels'))

    #  ORGANIZER 
    organizer = request.form['organizer']
    if organizer == "OTHERS":
        organizer = request.form.get('organizer_custom', '')

    #  FILES 
    poster = request.files.get('poster')
    icon = request.files.get('icon')

    poster_path = ""
    icon_path = ""

    os.makedirs("static/uploads", exist_ok=True)

    if poster and poster.filename:
        poster_path = f"static/uploads/{poster.filename}"
        poster.save(poster_path)

    if icon and icon.filename:
        icon_path = f"static/uploads/{icon.filename}"
        icon.save(icon_path)

    #  INSERT
    db.execute("""
        INSERT INTO events (
            event_name,
            organizer,
            venue,
            price,
            event_date,
            capacity,
            event_type,
            year_levels,
            department,
            program,
            short_desc,
            long_desc,
            poster,
            icon
        )
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        request.form['event_name'],
        organizer,
        request.form.get('venue', ''),
        request.form.get('price', 0),
        request.form['event_date'],
        request.form['capacity'],
        request.form['event_type'],
        year_levels,
        request.form.get('department', ''),
        request.form.get('program', ''),
        request.form.get('short_desc', ''),
        request.form.get('long_desc', ''),
        poster_path,
        icon_path
    ))

    db.commit()
    return redirect('/dashboard')

# CATALOG
@app.route('/catalog')
def catalog():
    db = get_db()
    events = db.execute("SELECT * FROM events").fetchall()
    return render_template('catalog.html', events=events)

# EVENT DETAILS
@app.route('/event/<int:event_id>')
def event_details(event_id):
    db = get_db()
    event = db.execute("SELECT * FROM events WHERE event_id=?", (event_id,)).fetchone()
    return render_template('event_details.html', event=event)

# JOIN EVENT
@app.route('/join/<int:event_id>')
def join_event(event_id):
    db = get_db()
    user_id = session['user']['user_id']

    count = db.execute("SELECT COUNT(*) as c FROM registrations WHERE event_id=?", (event_id,)).fetchone()['c']
    capacity = db.execute("SELECT capacity FROM events WHERE event_id=?", (event_id,)).fetchone()['capacity']

    if count >= capacity:
        return "Event Full!"

    existing = db.execute("SELECT * FROM registrations WHERE user_id=? AND event_id=?", (user_id, event_id)).fetchone()
    if existing:
        return redirect(f"/ticket/{existing['qr_code']}")

    qr = f"EVT_{event_id}_USR_{user_id}"

    db.execute("INSERT INTO registrations (user_id, event_id, qr_code) VALUES (?,?,?)",
               (user_id, event_id, qr))
    db.commit()

    return redirect(f"/ticket/{qr}")

# DASHBOARD
@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect('/')

    db = get_db()

    current_date = datetime.now().strftime("%Y-%m-%d") 

    # ADMIN DASHBOARD
    if session['user']['role'] == 'admin':

        events = db.execute("""
            SELECT e.*, COUNT(r.reg_id) as total
            FROM events e
            LEFT JOIN registrations r ON e.event_id = r.event_id
            GROUP BY e.event_id
        """).fetchall()

        return render_template('dashboard.html',
                               events=events,
                               role='admin',
                               current_date=current_date)  

    # STUDENT DASHBOARD
    events = db.execute("SELECT * FROM events").fetchall()

    return render_template('dashboard.html',
                           events=events,
                           role='student',
                           current_date=current_date)  

# HISTORY
@app.route('/history')
def history():
    db = get_db()
    data = db.execute("""
        SELECT e.*, r.qr_code
        FROM registrations r
        JOIN events e ON e.event_id = r.event_id
        WHERE r.user_id=?
    """, (session['user']['user_id'],)).fetchall()

    return render_template('history.html', data=data)

# MANAGE EVENTS
@app.route('/manage_events')
def manage_events():
    db = get_db()
    events = db.execute("""
        SELECT e.*, COUNT(r.reg_id) as total
        FROM events e
        LEFT JOIN registrations r ON e.event_id = r.event_id
        GROUP BY e.event_id
    """).fetchall()

    return render_template('manage_events.html', events=events)

# TICKET (WITH QR IMAGE)
@app.route('/ticket/<qr>')
def ticket(qr):
    db = get_db()

    data = db.execute("""
        SELECT r.qr_code, e.*
        FROM registrations r
        JOIN events e ON e.event_id = r.event_id
        WHERE r.qr_code=?
    """, (qr,)).fetchone()

    # generate QR image
    qr_path = f"static/uploads/{qr}.png"
    qr_img = qrcode.make(qr)
    qr_img.save(qr_path)

    return render_template('ticket.html', data=data, qr_img=f"uploads/{qr}.png")

# LOGOUT
@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

@app.route('/ticket_pdf/<qr>')
def ticket_pdf(qr):
    db = get_db()

    #  GET REGISTRATION + EVENT 
    data = db.execute("""
        SELECT r.qr_code, r.user_id, e.*
        FROM registrations r
        JOIN events e ON e.event_id = r.event_id
        WHERE r.qr_code=?
    """, (qr,)).fetchone()

    if not data:
        return "Ticket not found", 404

    #  GET USER 
    user = db.execute("""
        SELECT name, sr_code
        FROM users
        WHERE user_id=?
    """, (data['user_id'],)).fetchone()

    file_path = f"static/uploads/ticket_{qr}.pdf"

    if not os.path.exists(file_path):
        c = canvas.Canvas(file_path, pagesize=letter)
        width, height = letter

        #  HEADER 
        c.setFillColor(colors.HexColor("#111827"))
        c.rect(0, height - 90, width, 90, fill=1)

        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 18)
        c.drawString(40, height - 55, "EVENT TICKET")

        c.setFont("Helvetica", 9)
        c.drawString(40, height - 75, "Bring this ticket for entry validation")

        c.setFillColor(colors.black)

        #  LOGO 
        if data['icon'] and os.path.exists(data['icon']):
            c.drawImage(data['icon'], width - 120, height - 80, 60, 60, mask='auto')

        #  MAIN BOX 
        c.rect(40, 140, width - 80, 420, fill=0)

        #  TEAR LINE 
        c.setDash(6, 4)
        c.line(width / 2, 140, width / 2, 560)
        c.setDash()

        #  QR 
        qr_path = f"static/uploads/{qr}.png"
        if os.path.exists(qr_path):
            c.drawImage(qr_path, 70, 300, 170, 170)
        else:
            c.drawString(70, 300, "QR NOT FOUND")

        c.setFont("Helvetica-Bold", 9)
        c.drawString(110, 285, "SCAN QR FOR ENTRY")

        #  RIGHT SIDE 
        x = width / 2 + 30

        c.setFont("Helvetica-Bold", 14)
        c.drawString(x, 520, data['event_name'])

        c.setFont("Helvetica", 11)
        c.drawString(x, 490, f"Date: {data['event_date']}")
        c.drawString(x, 470, f"Venue: {data['venue']}")
        c.drawString(x, 450, f"Organizer: {data['organizer']}")

        #  ATTENDEE 
        c.setFont("Helvetica-Bold", 11)
        c.drawString(x, 410, "ATTENDEE DETAILS")

        c.setFont("Helvetica", 10)

        dept = data['department'] if 'department' in data.keys() else 'N/A'
        prog = data['program'] if 'program' in data.keys() else 'N/A'

        if user:
            c.drawString(x, 390, f"Name: {user['name']}")
            c.drawString(x, 370, f"SR Code: {user['sr_code']}")
        else:
            c.drawString(x, 390, "Name: N/A")
            c.drawString(x, 370, "SR Code: N/A")

        c.drawString(x, 350, f"Department: {dept}")
        c.drawString(x, 330, f"Program: {prog}")

        #  TICKET ID 
        c.setFont("Helvetica-Bold", 10)
        c.drawString(x + 10, 300, "TICKET ID")

        c.setFont("Helvetica", 9)
        c.drawString(x + 10, 285, qr)

        #  FOOTER 
        c.setFont("Helvetica-Oblique", 8)
        c.drawString(40, 110, "This ticket is valid for one-time entry only. Do not duplicate.")

        c.save()

    return send_file(file_path, as_attachment=True)

@app.route('/delete_event/<int:event_id>')
def delete_event(event_id):
    if 'user' not in session:
        return redirect('/')

    db = get_db()

    if session['user']['role'] != 'admin':
        return "Unauthorized", 403

    db.execute("DELETE FROM events WHERE event_id=?", (event_id,))
    db.execute("DELETE FROM registrations WHERE event_id=?", (event_id,))
    db.commit()

    return redirect('/manage_events')

@app.route('/edit_event/<int:event_id>', methods=['GET', 'POST'])
def edit_event(event_id):
    if 'user' not in session:
        return redirect('/')

    db = get_db()

    if session['user']['role'] != 'admin':
        return "Unauthorized", 403

    event = db.execute(
        "SELECT * FROM events WHERE event_id=?",
        (event_id,)
    ).fetchone()

    if request.method == 'GET':
        return render_template('edit_event.html', event=event)

    #  UPDATE EVENT 
    db.execute("""
        UPDATE events SET
            event_name=?,
            organizer=?,
            venue=?,
            price=?,
            event_date=?,
            capacity=?,
            event_type=?,
            department=?,
            program=?,
            short_desc=?,
            long_desc=?
        WHERE event_id=?
    """, (
        request.form['event_name'],
        request.form['organizer'],
        request.form.get('venue', ''),
        request.form.get('price', 0),
        request.form['event_date'],
        request.form['capacity'],
        request.form['event_type'],
        request.form.get('department', ''),
        request.form.get('program', ''),
        request.form.get('short_desc', ''),
        request.form.get('long_desc', ''),
        event_id
    ))

    db.commit()

    return redirect('/manage_events')

if __name__ == '__main__':
    app.run(debug=True)
