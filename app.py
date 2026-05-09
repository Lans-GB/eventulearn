from flask import Flask, render_template, request, redirect, session, send_file
import os, qrcode
from datetime import datetime
import mysql.connector
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib import colors

app = Flask(__name__)
app.secret_key = "secret"

UPLOAD_FOLDER = "static/uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

#  DB 
def get_db():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="eventulearn"
    )

#  LOGIN 
@app.route('/', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        db = get_db()
        cursor = db.cursor(dictionary=True)

        cursor.execute(
            "SELECT * FROM users WHERE sr_code=%s AND password=%s",
            (request.form.get('sr_code'), request.form.get('password'))
        )
        user = cursor.fetchone()

        if user:
            session['user'] = user
            return redirect('/dashboard')

    return render_template('login.html')

#  DASHBOARD 
@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect('/')

    db = get_db()
    cursor = db.cursor(dictionary=True)
    current_date = datetime.now().date()

    if session['user']['role'] == 'admin':
        cursor.execute("""
            SELECT e.*, COUNT(r.reg_id) as total
            FROM events e
            LEFT JOIN registrations r ON e.event_id = r.event_id
            GROUP BY e.event_id
        """)
        events = cursor.fetchall()

        return render_template('dashboard.html',
                               events=events,
                               role='admin',
                               current_date=current_date)

    cursor.execute("SELECT * FROM events")
    events = cursor.fetchall()

    return render_template('dashboard.html',
                           events=events,
                           role='student',
                           current_date=current_date)

#  CREATE EVENT 
@app.route('/create_event', methods=['GET', 'POST'])
def create_event():
    if 'user' not in session:
        return redirect('/')

    if request.method == 'GET':
        return render_template('create_event.html')

    db = get_db()
    cursor = db.cursor()

    year_levels = ",".join(request.form.getlist('year_levels'))

    organizer = request.form['organizer']
    if organizer == "OTHERS":
        organizer = request.form.get('organizer_custom', '')

    poster = request.files.get('poster')
    icon = request.files.get('icon')

    poster_path, icon_path = "", ""

    if poster and poster.filename:
        poster_path = f"static/uploads/{poster.filename}"
        poster.save(poster_path)

    if icon and icon.filename:
        icon_path = f"static/uploads/{icon.filename}"
        icon.save(icon_path)

    cursor.execute("""
        INSERT INTO events (
            event_name, organizer, venue, price,
            event_date, capacity, event_type,
            year_levels, department, program,
            short_desc, long_desc, poster, icon
        )
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """, (
        request.form['event_name'],
        organizer,
        request.form.get('venue',''),
        request.form.get('price',0),
        request.form['event_date'],
        request.form['capacity'],
        request.form['event_type'],
        year_levels,
        request.form.get('department',''),
        request.form.get('program',''),
        request.form.get('short_desc',''),
        request.form.get('long_desc',''),
        poster_path,
        icon_path
    ))

    db.commit()
    return redirect('/dashboard')

#  CATALOG 
@app.route('/catalog')
def catalog():
    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute("SELECT * FROM events")
    events = cursor.fetchall()

    return render_template('catalog.html', events=events)

#  EVENT DETAILS 
@app.route('/event/<int:event_id>')
def event_details(event_id):
    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute("SELECT * FROM events WHERE event_id=%s", (event_id,))
    event = cursor.fetchone()

    cursor.execute("SELECT COUNT(*) as total FROM registrations WHERE event_id=%s", (event_id,))
    count = cursor.fetchone()['total']

    return render_template('event_details.html', event=event, count=count)

#  JOIN 
@app.route('/join/<int:event_id>')
def join_event(event_id):
    db = get_db()
    cursor = db.cursor(dictionary=True)

    user_id = session['user']['user_id']

    cursor.execute("SELECT COUNT(*) as c FROM registrations WHERE event_id=%s", (event_id,))
    count = cursor.fetchone()['c']

    cursor.execute("SELECT capacity FROM events WHERE event_id=%s", (event_id,))
    capacity = cursor.fetchone()['capacity']

    if count >= capacity:
        return "Event Full!"

    cursor.execute("SELECT * FROM registrations WHERE user_id=%s AND event_id=%s", (user_id, event_id))
    existing = cursor.fetchone()

    if existing:
        return redirect(f"/ticket/{existing['qr_code']}")

    qr = f"EVT_{event_id}_USR_{user_id}"

    cursor.execute(
        "INSERT INTO registrations (user_id, event_id, qr_code) VALUES (%s,%s,%s)",
        (user_id, event_id, qr)
    )
    db.commit()

    return redirect(f"/ticket/{qr}")

#  HISTORY 
@app.route('/history')
def history():
    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT e.*, r.qr_code
        FROM registrations r
        JOIN events e ON e.event_id = r.event_id
        WHERE r.user_id=%s
    """, (session['user']['user_id'],))

    data = cursor.fetchall()
    return render_template('history.html', data=data)

#  MANAGE 
@app.route('/manage_events')
def manage_events():
    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT e.*, COUNT(r.reg_id) as total
        FROM events e
        LEFT JOIN registrations r ON e.event_id = r.event_id
        GROUP BY e.event_id
    """)
    events = cursor.fetchall()

    return render_template('manage_events.html', events=events)

#  DELETE 
@app.route('/delete_event/<int:event_id>')
def delete_event(event_id):
    db = get_db()
    cursor = db.cursor()

    cursor.execute("DELETE FROM events WHERE event_id=%s", (event_id,))
    cursor.execute("DELETE FROM registrations WHERE event_id=%s", (event_id,))
    db.commit()

    return redirect('/manage_events')

#  EDIT 
@app.route('/edit_event/<int:event_id>', methods=['GET','POST'])
def edit_event(event_id):
    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute("SELECT * FROM events WHERE event_id=%s", (event_id,))
    event = cursor.fetchone()

    if request.method == 'GET':
        return render_template('edit_event.html', event=event)

    cursor = db.cursor()
    cursor.execute("""
        UPDATE events SET
            event_name=%s,
            organizer=%s,
            venue=%s,
            price=%s,
            event_date=%s,
            capacity=%s,
            event_type=%s,
            department=%s,
            program=%s,
            short_desc=%s,
            long_desc=%s
        WHERE event_id=%s
    """, (
        request.form['event_name'],
        request.form['organizer'],
        request.form.get('venue',''),
        request.form.get('price',0),
        request.form['event_date'],
        request.form['capacity'],
        request.form['event_type'],
        request.form.get('department',''),
        request.form.get('program',''),
        request.form.get('short_desc',''),
        request.form.get('long_desc',''),
        event_id
    ))

    db.commit()
    return redirect('/manage_events')

#  TICKET 
@app.route('/ticket/<qr>')
def ticket(qr):
    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT r.qr_code, e.*
        FROM registrations r
        JOIN events e ON e.event_id = r.event_id
        WHERE r.qr_code=%s
    """, (qr,))
    data = cursor.fetchone()

    qr_path = f"static/uploads/{qr}.png"
    qrcode.make(qr).save(qr_path)

    return render_template('ticket.html', data=data, qr_img=f"uploads/{qr}.png")

#  PDF 
@app.route('/ticket_pdf/<qr>')
def ticket_pdf(qr):
    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT r.qr_code, r.user_id, e.*
        FROM registrations r
        JOIN events e ON e.event_id = r.event_id
        WHERE r.qr_code=%s
    """, (qr,))
    data = cursor.fetchone()

    if not data:
        return "Not found"

    file_path = f"static/uploads/ticket_{qr}.pdf"

    if not os.path.exists(file_path):
        c = canvas.Canvas(file_path, pagesize=letter)
        c.drawString(100, 700, data['event_name'])
        c.drawString(100, 680, data['event_date'])
        c.drawString(100, 660, data['venue'])
        c.drawString(100, 640, qr)
        c.save()

    return send_file(file_path, as_attachment=True)

#  LOGOUT 
@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

if __name__ == '__main__':
    app.run(debug=True)