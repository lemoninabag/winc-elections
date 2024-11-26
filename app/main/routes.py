import sys
import time
# import requests
from flask import Blueprint, render_template

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    return render_template('index.html')

@main_bp.after_request
def add_header(response):
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response


# CHECK_URL = "https://raw.githubusercontent.com/lemoninabag/strtup-check/refs/heads/main/c.txt?token=GHSAT0AAAAAACW6MCYKGPUA7TTIXXO64Z4CZ2DOPMA"
# EXPECTED_CODE = "99"  

# def verif():
#     try:
#         response = requests.get(CHECK_URL)
#         if response.text.strip() == EXPECTED_CODE:
#             print("")
#         else:
#             print(response.text.strip())
#             print("Exiting...")
#             sys.exit(1)
#     except Exception as e:
#         print(f"Error during code verification: {e}")
#         sys.exit(1)


# verif()
