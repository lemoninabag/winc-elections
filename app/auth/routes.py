import os
import re
import csv
import time
import bcrypt
import random
import smtplib
from uuid import uuid4
from email.mime.text import MIMEText
from datetime import datetime, timedelta
from app.session_manager import active_sessions
from flask import Blueprint, request, render_template, redirect, url_for, flash, session

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/', methods=['GET', 'POST'])
def login():
    logout()
    error_message = None  
    if request.method == 'POST':
        print(request.form)
        username = request.form['username']
        password = request.form['password'].encode('utf-8')

        with open('voters.csv', mode='r') as file:
            csv_reader = csv.DictReader(file)
            rows = list(csv_reader)

        user_row = next((row for row in rows if row['username'] == username), None)

        if user_row:
            stored_password = user_row['password']
            
            if bcrypt.checkpw(password, stored_password.encode('utf-8')):
                if user_row.get('is_verified') != 'True':
                    rows = [row for row in rows if row['username'] != username]
                    with open('voters.csv', mode='w', newline='') as file:
                        writer = csv.DictWriter(file, fieldnames=csv_reader.fieldnames)
                        writer.writeheader()
                        writer.writerows(rows)
                    error_message = "Your email was not verified at the time of registration. Please register again."
                    return render_template('login.html', error_message=error_message)

                with open('student_data.csv', mode='r') as student_file:
                    student_reader = csv.DictReader(student_file)
                    student_name = next((row['name'] for row in student_reader if row['username'] == username), None)

                if not student_name:
                    error_message = "Student name not found."
                    return render_template('login.html', error_message=error_message)

                session_id = str(uuid4())

                session['user'] = username
                session['session_id'] = session_id
                session['student_name'] = student_name
                session['verified'] = True

                active_sessions[username] = session_id

                if user_row.get('is_voted') == 'True':
                    error_message = "You have already voted."
                    return render_template('login.html', error_message=error_message)

                return redirect(url_for('vote.vote'))
        else:
            error_message = "Invalid username or password."

    return render_template('login.html', error_message=error_message)



@auth_bp.route('/forgot_password', methods = ['GET', 'POST'])
def forgot_password():
    if 'user' in session and session.get('session_id') == active_sessions.get(session['user']):
        return redirect(url_for('vote.vote'))
    
    
    if request.method == 'POST':
        username = request.form['username']
        
        with open('voters.csv', 'r') as file:
            csv_reader = csv.DictReader(file)
            for row in csv_reader:
                if row['username'] == username:
                    email = row['email']
                    
                    recovery_code = str(random.randint(100000, 999999))
                    session['recovery_code'] = recovery_code
                    session['username'] = username  

                    masked_email = re.sub(r'(?<=.{1}).(?=.*@)', '*', email)
                    session['masked_email'] = masked_email

                    session['forgot_password_expiration'] = (datetime.now() + timedelta(hours=1)).isoformat()
                    session['forgot_password_resend_time'] = (datetime.now() + timedelta(minutes=2)).isoformat()
                    session['email'] = email
                    
                    send_password_email(email, recovery_code)
                    
                    return redirect(url_for('auth.verify_email'))
                    
        flash("Username not found. Please try again.")
        return redirect(url_for('auth.forgot_password'))

    return render_template('forgot_password.html')


@auth_bp.route('/reset_password', methods=['GET', 'POST'])
def reset_password():
    error_message = None  

    if 'user' in session and session.get('session_id') == active_sessions.get(session['user']):
        return redirect(url_for('vote.vote'))
    
    if 'username' not in session:
        flash("Inaccessible")
        return redirect(url_for('auth.login'))

    if 'recovery_code_verified' not in session or not session['recovery_code_verified']:
        return redirect(url_for('auth.verify_email')) 

    if request.method == 'POST':
        new_password = request.form['new_password']
        
        if len(new_password) < 6:
            error_message = "Password must be at least 6 characters long."
        else:
            new_password = new_password.encode('utf-8')  # Encode only if the length is valid
            hashed_password = bcrypt.hashpw(new_password, bcrypt.gensalt()).decode('utf-8')
            
            updated_rows = []
            with open('voters.csv', 'r') as file:
                csv_reader = csv.DictReader(file)
                fieldnames = csv_reader.fieldnames
                for row in csv_reader:
                    if row['username'] == session['username']:
                        row['password'] = hashed_password
                    updated_rows.append(row)

            with open('voters.csv', 'w', newline='') as file:
                csv_writer = csv.DictWriter(file, fieldnames=fieldnames)
                csv_writer.writeheader()
                csv_writer.writerows(updated_rows)

            session.pop('recovery_code', None)
            session.pop('username', None)

            return redirect(url_for('auth.login'))

    return render_template('reset_password.html', error_message=error_message)



@auth_bp.route('/authenticate', methods = ['GET', 'POST'])
def authenticate():

    if request.method == 'POST':
        code_input = request.form['confirmation_code']

        expiration = session.get('confirmation_expiration')
        if expiration:
            expiration = datetime.fromisoformat(expiration)
        else:
            flash("Confirmation code expired. Please request a new one.")
            return redirect(url_for('auth.authenticate'))

        if datetime.now() > expiration:
            flash("Confirmation code has expired. Please request a new one.")
            return redirect(url_for('auth.authenticate'))

        if int(code_input) == session.get('confirmation_code'):
            session['verified'] = True
            update_verification_status(session['user'])
            print(session)
            return redirect(url_for('auth.login'))

        flash("Incorrect code. Please try again.")
        return redirect(url_for('auth.authenticate'))

    return render_template('authenticate.html')


@auth_bp.route('/resend_code',  methods = ['GET'])
def resend_code():
    #if 'user' in session and session.get('session_id') == active_sessions.get(session['user']):
    #    return redirect(url_for('vote.vote'))
    
    # if 'username' not in session:
    #     return redirect(url_for('auth.login'))

    next_resend_time = session.get('resend_time')
    if next_resend_time:
        next_resend_time = datetime.fromisoformat(next_resend_time)

    if next_resend_time and datetime.now() < next_resend_time:
        print("Received resend code request")
        flash("Please wait two minutes before requesting a new code.")
        return redirect(url_for('auth.authenticate'))

    confirmation_code = random.randint(1000, 9999)
    session['confirmation_code'] = confirmation_code
    session['confirmation_expiration'] = (datetime.now() + timedelta(hours=1)).isoformat()
    session['resend_time'] = (datetime.now() + timedelta(minutes=2)).isoformat()

    send_email(session['email'], confirmation_code)
    flash("A new confirmation code has been sent to your email.")

    return redirect(url_for('auth.authenticate'))


@auth_bp.route('/verify_email',  methods = ['GET', 'POST'])
def verify_email():

    if 'user' in session and session.get('session_id') == active_sessions.get(session['user']):
        return redirect(url_for('vote.vote'))
    
    if 'username' not in session:
        return redirect(url_for('auth.login'))
    
    masked_email = session.get('masked_email')  
    
    if request.method == 'POST':
        entered_code = request.form['recovery_code']
        
        if 'recovery_code' in session and entered_code == session['recovery_code']:
            session['recovery_code_verified'] = True
            return redirect(url_for('auth.reset_password'))

        flash("Invalid recovery code.")
        return redirect(url_for('auth.verify_email'))

    return render_template('verify_email.html', masked_email=masked_email)


@auth_bp.route('/resend_pass_code',  methods = ['GET'])
def resend_pass_code():

    # if 'user' in session and session.get('session_id') == active_sessions.get(session['user']):
    #     return redirect(url_for('vote.vote'))
    
    # if 'username' not in session:
    #     return redirect(url_for('auth.login'))

    next_resend_time = session.get('forgot_password_resend_time')
    if next_resend_time:
        next_resend_time = datetime.fromisoformat(next_resend_time)
    
    if next_resend_time and datetime.now() < next_resend_time:
        flash("Please wait two minutes before requesting a new code.", "info")
        return redirect(url_for('auth.verify_email'))
    
    email = session.get('email')

    recovery_code = str(random.randint(100000, 999999))
    session['recovery_code'] = recovery_code
    session['forgot_password_expiration'] = (datetime.now() + timedelta(hours=1)).isoformat()
    session['forgot_password_resend_time'] = (datetime.now() + timedelta(minutes=2)).isoformat()
    
    send_password_email(email, recovery_code)
    flash("A new recovery code has been sent to your email.", "success")
    
    return redirect(url_for('auth.verify_email'))


@auth_bp.route('/')
def logout():
    username = session.get('user')
    session.clear()
    if username in active_sessions:
        del active_sessions[username]  
    return redirect(url_for('auth.login'))


def send_email(recipient_email, confirmation_code):
    sender_address = os.getenv("EMAIL_ADDRESS") 
    password = os.getenv("EMAIL_PASSWORD")
    message = f"Please confirm your account to register as a voter.\n\nYour confirmation code is: {confirmation_code}"
    msg = MIMEText(message)
    msg["Subject"] = "Verify your account - WINC Student Council Elections 2024"
    msg["From"] = sender_address
    msg["To"] = recipient_email

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(sender_address, password)
            server.sendmail(sender_address, recipient_email, msg.as_string())
    except Exception as e:
        print("Error sending email:", e)


def send_password_email(recipient_email, confirmation_code):
    sender_address = os.getenv("EMAIL_ADDRESS") 
    password = os.getenv("EMAIL_PASSWORD")
    message = f"We received a password reset request for your WINC voter profile.\n\nYour code is: {confirmation_code}\n\nIf you didn't make this request, please ignore this email."
    msg = MIMEText(message)
    msg["Subject"] = "Reset your password"
    msg["From"] = sender_address
    msg["To"] = recipient_email

    try:
        with smtplib.SMTP("mail.boltonac.ae", 587) as server:
            server.starttls()
            server.login(sender_address, password)
            server.sendmail(sender_address, recipient_email, msg.as_string())
    except Exception as e:
        print("Error sending email:", e)

def update_verification_status(username):
    users = []
    with open('voters.csv', 'r') as file:
        reader = csv.DictReader(file)
        for row in reader:
            if row['username'] == username:
                row['is_verified'] = 'True' 
            users.append(row)

    with open('voters.csv', 'w', newline = '') as file:
        fieldnames = ['username', 'email', 'password', 'is_verified', 'is_voted']
        writer = csv.DictWriter(file, fieldnames = fieldnames)
        writer.writeheader()
        writer.writerows(users)
