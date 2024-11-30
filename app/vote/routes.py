import csv
from datetime import datetime
from pytz import timezone
from app.session_manager import active_sessions
from flask import Blueprint, render_template, request, session, redirect, url_for, flash

vote_bp = Blueprint('vote', __name__)

uae_tz = timezone('Asia/Dubai')

# VOTING_START = datetime(2024, 11, 28, 10, 29)
VOTING_END = uae_tz.localize(datetime(2024, 12, 1, 14, 0))

positions = ['President', 'Vice President', 'Secretary', 'Treasurer', 'Events & Cultural Activities Coordinator', 
            'Media Coordinator', 'Sports Coordinator', 'Career Service Coordinator', 'UoB Representative', 'Pearson Representative', 
            'ATHE Representative', 'Northwood Representative']

@vote_bp.route('/', methods = ['GET', 'POST'])
def vote():

    message = ""
    if 'user' not in session or session.get('session_id') != active_sessions.get(session['user']):
        return redirect(url_for('auth.login'))

    current_time = datetime.now(uae_tz)

    # if current_time < VOTING_START:
    #     flash("Voting has not yet started.")
    #     return redirect(url_for('main.index'))

    if current_time > VOTING_END:
        flash("Voting has ended. Thank you for participating.")
        return redirect(url_for('main.index'))

    username = session['user']
    student_name = session.get('student_name')
    has_voted = False

    candidates = {position: [] for position in positions}
    selected_candidates = {position: None for position in positions}  

    with open('nominees.csv', 'r', encoding='utf-8-sig') as file:
        reader = csv.DictReader(file)
        for row in reader:
            if row['position'] in candidates:
                candidates[row['position']].append(row)

    with open('voters.csv', 'r') as voters_file:
        reader = csv.DictReader(voters_file)
        for row in reader:
            if row['username'] == username:
                is_verified = row.get('is_verified') == 'True'
                has_voted = row.get('is_voted') == 'True'
                break
    if not is_verified:
        return redirect(url_for('auth.authenticate'))


    if request.method == 'POST':
        votes = {}
        for position in positions:
            selected_candidate = request.form.get(position)
            if selected_candidate:
                votes[position] = selected_candidate
                selected_candidates[position] = selected_candidate

        if len(votes) == len(positions):  
            update_nominee_votes(votes)
            update_isVoted(session['user'])
            session.pop('votes', None)
            session.pop('user', None)
            return redirect(url_for('vote.confirmation'))
        else:
            message = "Please vote for all positions before submitting."

    if has_voted:
        return "You have already voted. Thank you!"
    
    return render_template('vote.html', positions=positions, candidates=candidates, 
                        student_name=student_name, selected_candidates=selected_candidates, message=message)


@vote_bp.route('/confirmation', methods = ['GET', 'POST'])
def confirmation():
    if 'user' not in session or session.get('session_id') != active_sessions.get(session['user']):
        session.clear()
        flash("Session invalid or expired. Please log in again.", "error")
        return redirect(url_for('auth.login'))

    # Proceed to confirmation only if the session is valid
    votes = session.get('votes', {})

    if len(votes) != len(positions):
        return f"You must vote for all positions before submitting. (Voted for {votes} out of {len(positions)})"

    if request.method == 'POST':
        update_nominee_votes(votes)
        update_isVoted(session['user'])

        # Clear the session after processing the vote
        session.pop('votes', None)
        session.pop('user', None)

        return "Vote successfully submitted!"

    return render_template('confirmation.html', votes=votes)

@vote_bp.route('/results')
def results():
    nominees_by_position = {}

    with open('nominees.csv', mode = 'r', encoding='utf-8-sig') as file:
        csv_reader = csv.DictReader(file)
        for row in csv_reader:
            position = row['position']
            name = row['nominee']
            votes = int(row['votes'])

            if position not in nominees_by_position:
                nominees_by_position[position] = []

            nominees_by_position[position].append({'name': name, 'votes': votes})

    winners = {}
    for position, nominees in nominees_by_position.items():
        sorted_nominees = sorted(nominees, key = lambda x: x['votes'], reverse = True)
        winners[position] = sorted_nominees[0]  

    return render_template('results.html', winners = winners, nominees_by_position = nominees_by_position)

def update_nominee_votes(votes):
    nominees = []
    with open('nominees.csv', 'r', encoding='utf-8-sig') as file:
        reader = csv.DictReader(file)
        for row in reader:
            nominee_name = row['nominee']
            print(row['nominee'], row['votes'])
            if nominee_name in votes.values():
                row['votes'] = str(int(row.get('votes', 0)) + 1)
            nominees.append(row)

    with open('nominees.csv', 'w', newline = '', encoding='utf-8-sig') as file:
        fieldnames = ['position', 'nominee', 'program', 'year', 'image', 'votes']
        writer = csv.DictWriter(file, fieldnames = fieldnames)
        writer.writeheader()
        writer.writerows(nominees)

def update_isVoted(username):
    users = []
    with open('voters.csv', 'r') as file:
        reader = csv.DictReader(file)
        for row in reader:
            if row['username'] == username:
                row['is_voted'] = 'True'
            users.append(row)

    with open('voters.csv', 'w', newline = '') as file:
        fieldnames = ['username', 'email', 'password', 'is_verified', 'is_voted']
        writer = csv.DictWriter(file, fieldnames = fieldnames)
        writer.writeheader()
        writer.writerows(users)

def read_candidates():
    candidates = {}
    with open('./nominees.csv') as csvfile:  # specify the correct path to your CSV
        reader = csv.DictReader(csvfile)
        for row in reader:
            position = row['position']
            if position not in candidates:
                candidates[position] = []
            candidates[position].append(row)
    return candidates

@vote_bp.route('/candidates')
def candidates():
    candidates_data = read_candidates()
    return render_template('candidates.html', candidates=candidates_data)
