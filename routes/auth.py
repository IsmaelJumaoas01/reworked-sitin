from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify, make_response
import hashlib
from db import execute_query
import re
from functools import wraps
from datetime import datetime, timedelta

auth_bp = Blueprint('auth', __name__)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login to access this page', 'error')
            return redirect(url_for('auth.login'))
        
        # Check if session is expired
        if 'last_activity' in session:
            last_activity = datetime.fromisoformat(session['last_activity'])
            if datetime.now() - last_activity > timedelta(minutes=30):
                session.clear()
                flash('Your session has expired. Please login again.', 'error')
                return redirect(url_for('auth.login'))
        
        # Update last activity
        session['last_activity'] = datetime.now().isoformat()
        return f(*args, **kwargs)
    return decorated_function

def role_required(role):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                flash('Please login to access this page', 'error')
                return redirect(url_for('auth.login'))
            
            if 'user_type' not in session or session['user_type'] != role:
                flash('You do not have permission to access this page', 'error')
                return redirect(url_for('auth.login'))
            
            # Update last activity
            session['last_activity'] = datetime.now().isoformat()
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def no_cache(view):
    @wraps(view)
    def no_cache_impl(*args, **kwargs):
        response = make_response(view(*args, **kwargs))
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response
    return no_cache_impl

@auth_bp.route('/check-email', methods=['POST'])
def check_email():
    data = request.get_json()
    email = data.get('email')
    
    query = "SELECT COUNT(*) as count FROM USERS WHERE EMAIL = %s"
    result = execute_query(query, (email,))
    
    return jsonify({'exists': result[0]['count'] > 0})

@auth_bp.route('/check-idno', methods=['POST'])
def check_idno():
    data = request.get_json()
    idno = data.get('idno')
    
    query = "SELECT COUNT(*) as count FROM USERS WHERE IDNO = %s"
    result = execute_query(query, (idno,))
    
    return jsonify({'exists': result[0]['count'] > 0})

@auth_bp.route('/login', methods=['GET', 'POST'])
@no_cache
def login():
    print("\n=== Login Process Started ===")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # If user is already logged in, redirect to their dashboard
    if 'user_id' in session and 'user_type' in session:
        user_type = session['user_type'].lower()
        print(f"User already logged in. User ID: {session['user_id']}, Type: {user_type}")
        if user_type == 'student':
            return redirect(url_for('student.dashboard'))
        elif user_type == 'admin':
            return redirect(url_for('admin.dashboard'))
        elif user_type == 'staff':
            return redirect(url_for('staff.dashboard'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        print(f"\nLogin attempt for email: {email}")
        
        if not email or not password:
            print("Validation Error: Missing email or password")
            flash('Please enter both email and password', 'error')
            return render_template('auth/login.html')
        
        # Hash the password
        hashed_password = hashlib.sha256(password.encode()).hexdigest()
        
        # Check user credentials
        query = "SELECT * FROM USERS WHERE EMAIL = %s AND PASSWORD = %s"
        user = execute_query(query, (email, hashed_password))
        
        if user and len(user) > 0:
            user = user[0]
            print(f"\nLogin successful for user: {user['IDNO']}")
            print(f"User Type: {user['USER_TYPE']}")
            print(f"Name: {user['FIRSTNAME']} {user['LASTNAME']}")
            
            # Set session data
            session['user_id'] = user['IDNO']
            session['user_type'] = user['USER_TYPE']
            session['name'] = f"{user['FIRSTNAME']} {user['LASTNAME']}"
            session['last_activity'] = datetime.now().isoformat()
            
            print("\nSession data set:")
            print(f"User ID: {session['user_id']}")
            print(f"User Type: {session['user_type']}")
            print(f"Name: {session['name']}")
            
            # Redirect based on user type
            user_type = user['USER_TYPE'].lower()
            print(f"\nRedirecting to {user_type} dashboard...")
            
            if user_type == 'student':
                return redirect(url_for('student.dashboard'))
            elif user_type == 'admin':
                return redirect(url_for('admin.dashboard'))
            elif user_type == 'staff':
                return redirect(url_for('staff.dashboard'))
        else:
            print("\nLogin failed: Invalid credentials")
            flash('Invalid email or password', 'error')
    
    return render_template('auth/login.html')

@auth_bp.route('/register', methods=['GET', 'POST'])
@no_cache
def register():
    if 'user_id' in session:
        return redirect(url_for(session['user_type'].lower() + '.dashboard'))
    
    if request.method == 'POST':
        print("\n=== Registration Process Started ===")
        print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Get form data
        idno = request.form.get('idno')
        firstname = request.form.get('firstname')
        lastname = request.form.get('lastname')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        course = request.form.get('course')
        year = request.form.get('year')
        user_type = request.form.get('user_type', 'STUDENT')  # Default to STUDENT if not provided
        
        print("\nForm Data Received:")
        print(f"ID Number: {idno}")
        print(f"Name: {firstname} {lastname}")
        print(f"Email: {email}")
        print(f"Course: {course}")
        print(f"Year: {year}")
        print(f"User Type: {user_type}")
        
        # Validate required fields
        if not all([idno, firstname, lastname, email, password, confirm_password, course, year]):
            print("\nValidation Error: Missing required fields")
            flash('Please fill in all required fields', 'error')
            return redirect(url_for('auth.register'))
        
        # Validate email format
        if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            print("\nValidation Error: Invalid email format")
            flash('Invalid email format', 'error')
            return redirect(url_for('auth.register'))
        
        # Validate password match
        if password != confirm_password:
            print("\nValidation Error: Passwords do not match")
            flash('Passwords do not match', 'error')
            return redirect(url_for('auth.register'))
        
        # Check if email already exists
        email_check = execute_query("SELECT COUNT(*) as count FROM USERS WHERE EMAIL = %s", (email,))
        if email_check[0]['count'] > 0:
            print("\nValidation Error: Email already registered")
            flash('Email already registered', 'error')
            return redirect(url_for('auth.register'))
        
        # Check if ID number already exists
        idno_check = execute_query("SELECT COUNT(*) as count FROM USERS WHERE IDNO = %s", (idno,))
        if idno_check[0]['count'] > 0:
            print("\nValidation Error: ID number already registered")
            flash('ID number already registered', 'error')
            return redirect(url_for('auth.register'))
        
        try:
            print("\nStarting database operations...")
            
            # Hash the password
            hashed_password = hashlib.sha256(password.encode()).hexdigest()
            print("Password hashed successfully")
            
            # Insert new user
            print("Inserting new user into database...")
            execute_query("""
                INSERT INTO USERS (IDNO, FIRSTNAME, LASTNAME, EMAIL, PASSWORD, COURSE, YEAR, USER_TYPE, STATUS)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'active')
            """, (idno, firstname, lastname, email, hashed_password, course, year, user_type))
            print("User inserted successfully")
            
            # Set sit-in limits for students
            if user_type == 'STUDENT':
                # Set 30 sit-ins for BSIT and BSCS, 15 for others
                max_sit_ins = 30 if course in ['BSIT', 'BSCS'] else 15
                print(f"Setting sit-in limit: {max_sit_ins} for course {course}")
                execute_query("""
                    INSERT INTO SIT_IN_LIMITS (USER_IDNO, SIT_IN_COUNT, MAX_SIT_INS)
                    VALUES (%s, 0, %s)
                """, (idno, max_sit_ins))
                print("Sit-in limit set successfully")
            
            print("\nRegistration completed successfully!")
            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('auth.login'))
            
        except Exception as e:
            print(f"\nError during registration: {str(e)}")
            print("Stack trace:", e.__traceback__)
            flash(f'Error during registration: {str(e)}', 'error')
            return redirect(url_for('auth.register'))
    
    return render_template('auth/register.html')

@auth_bp.route('/logout')
@no_cache
def logout():
    # Clear all session data
    session.clear()
    
    # Create response with redirect
    response = make_response(redirect(url_for('auth.login')))
    
    # Add cache control headers
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    
    # Clear any existing cookies
    response.delete_cookie('session')
    
    flash('You have been logged out successfully', 'success')
    return response 