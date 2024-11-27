import os
import csv
import random
import bcrypt
import smtplib
from app.auth.routes import logout
from email.mime.text import MIMEText
from datetime import datetime, timedelta
from app.session_manager import active_sessions
from flask import Blueprint, request, render_template, redirect, url_for, flash, session

def send_email(recipient_email, confirmation_code):
    sender_address = os.getenv("EMAIL_ADDRESS") 
    password = os.getenv("EMAIL_PASSWORD")
    message = f"Please confirm your account to register as a voter.\n\nYour confirmation code is: {confirmation_code}"
    msg = MIMEText(message)
    msg["Subject"] = "Verify your account - WINC Student Council Elections 2024"
    msg["From"] = sender_address
    msg["To"] = recipient_email

    try:
        with smtplib.SMTP("mail.boltonac.ae", 587) as server:
            server.starttls()
            server.login(sender_address, password)
            server.sendmail(sender_address, recipient_email, msg.as_string())
    except Exception as e:
        print("Error sending email:", e)


register_bp = Blueprint('register', __name__)

@register_bp.route('/', methods=['GET', 'POST'])
def register():
    logout()
    error_message = None  
    
    if request.method == 'POST':
        email = request.form['email']
        username = request.form['username']
        password = request.form['password']

        if len(password) < 6:
            error_message = "Password must be at least 6 characters long."
        else:
            password = password.encode('utf-8')  


            with open('voters.csv', mode='r') as file:
                csv_reader = csv.DictReader(file)
                for row in csv_reader:
                    if row['username'] == username:
                        error_message = "Username already registered. Please log in."
                        break
                    if row['email'] == email:
                        error_message = "Email already registered. Please log in."
                        break

            if not error_message:  
                student_name = None
                student_email = None  
                
                with open('student_data.csv', mode='r') as file:
                    csv_reader = csv.DictReader(file)
                    for row in csv_reader:
                        if row['username'] == username:
                            student_name = row['name']
                            student_email = row['email']  
                            break

                if not student_name:
                    error_message = "Username not found in student records."
                else:
                    if student_email and student_email != email:
                        error_message = "Please use your registered email."
                    
                    if not error_message:
                        session['student_name'] = student_name

                        hashed_pass = bcrypt.hashpw(password, bcrypt.gensalt())

                        confirmation_code = random.randint(1000, 9999)
                        session['confirmation_code'] = confirmation_code
                        session['confirmation_expiration'] = (datetime.now() + timedelta(hours=1)).isoformat()
                        session['resend_time'] = (datetime.now() + timedelta(minutes=2)).isoformat()

                        with open('voters.csv', mode='a', newline='') as file:
                            writer = csv.writer(file)
                            writer.writerow([username, email, hashed_pass, False, False])

                        session['user'] = username
                        session['email'] = email

                        send_email(email, confirmation_code)
                        return redirect(url_for('auth.authenticate'))
    
    return render_template('login.html', error_message=error_message)
