from flask import Blueprint, render_template, request, redirect, url_for, session, flash, send_file, jsonify
from db import execute_query
import hashlib
import base64
import re
from io import BytesIO
from routes.auth import login_required, role_required
from datetime import datetime
import mysql.connector

student_bp = Blueprint('student', __name__, url_prefix='/student')

@student_bp.route('/dashboard')
@login_required
@role_required('STUDENT')
def dashboard():
    print("\n=== Student Dashboard Loading ===")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"User ID: {session['user_id']}")
    print(f"User Type: {session['user_type']}")
    
    try:
        # Get student's sit-in records
        print("\nFetching sit-in records...")
        sit_in_query = """
        SELECT sr.*, l.LAB_NAME, p.PURPOSE_NAME
        FROM SIT_IN_RECORDS sr
        JOIN LABORATORIES l ON sr.LAB_ID = l.LAB_ID
        JOIN PURPOSES p ON sr.PURPOSE_ID = p.PURPOSE_ID
        WHERE sr.USER_IDNO = %s
        ORDER BY sr.CREATED_AT DESC
        LIMIT 5
        """
        sit_in_records = execute_query(sit_in_query, (session['user_id'],))
        if sit_in_records is None:
            sit_in_records = []
        print(f"Found {len(sit_in_records)} sit-in records")
        
        # Get student's sit-in limits
        print("\nFetching sit-in limits...")
        sit_in_limits_query = """
        SELECT SIT_IN_COUNT, MAX_SIT_INS
        FROM SIT_IN_LIMITS
        WHERE USER_IDNO = %s
        """
        sit_in_limits = execute_query(sit_in_limits_query, (session['user_id'],))
        if sit_in_limits and len(sit_in_limits) > 0:
            sit_in_limit = sit_in_limits[0]['SIT_IN_COUNT']
            max_sit_ins = sit_in_limits[0]['MAX_SIT_INS']
            remaining_sessions = max_sit_ins - sit_in_limit
        else:
            sit_in_limit = 0
            max_sit_ins = 0
            remaining_sessions = 0
        print(f"Sit-in limit: {sit_in_limit}, Max: {max_sit_ins}, Remaining: {remaining_sessions}")
        
        # Get sit-in statistics
        print("\nFetching sit-in statistics...")
        stats_query = """
        SELECT 
            COUNT(*) as total_sit_ins,
            SUM(CASE WHEN SESSION = 'ON_GOING' THEN 1 ELSE 0 END) as active_sit_ins,
            SUM(CASE WHEN STATUS = 'APPROVED' THEN 1 ELSE 0 END) as approved_sit_ins
        FROM SIT_IN_RECORDS
        WHERE USER_IDNO = %s
        """
        stats = execute_query(stats_query, (session['user_id'],))
        stats = stats[0] if stats else {'total_sit_ins': 0, 'active_sit_ins': 0, 'approved_sit_ins': 0}
        print(f"Statistics: {stats}")
        
        # Get active announcements
        print("\nFetching active announcements...")
        announcements_query = """
        SELECT 
            a.ANNOUNCEMENT_ID,
            a.TITLE,
            a.CONTENT,
            DATE_FORMAT(a.DATE_POSTED, '%Y-%m-%d %H:%i') as DATE_POSTED,
            a.STATUS,
            u.FIRSTNAME,
            u.LASTNAME
        FROM ANNOUNCEMENTS a
        JOIN USERS u ON a.POSTED_BY = u.IDNO
        WHERE a.STATUS = 'active'
        ORDER BY a.DATE_POSTED DESC
        LIMIT 5
        """
        announcements = execute_query(announcements_query)
        if announcements is None:
            announcements = []
        print(f"Found {len(announcements)} active announcements")
        
        print("\nRendering dashboard template...")
        return render_template('student/dashboard.html',
                             sit_in_records=sit_in_records,
                             sit_in_limit=sit_in_limit,
                             max_sit_ins=max_sit_ins,
                             remaining_sessions=remaining_sessions,
                             stats=stats,
                             announcements=announcements)
    except Exception as e:
        print(f"\nError in student dashboard: {str(e)}")
        print("Stack trace:", e.__traceback__)
        return render_template('error.html', 
                             error_message="An error occurred while loading the dashboard. Please try again later.",
                             back_url=url_for('auth.login'))

@student_bp.route('/profile')
@login_required
@role_required('STUDENT')
def profile():
    # Get student details
    query = "SELECT * FROM USERS WHERE IDNO = %s"
    student = execute_query(query, (session['user_id'],))
    
    if not student:
        flash('Student not found', 'error')
        return redirect(url_for('student.dashboard'))
    
    student = student[0]
    
    # Get sit-in statistics
    stats_query = """
    SELECT 
        COUNT(*) as total_sit_ins,
        SUM(CASE WHEN SESSION = 'ON_GOING' THEN 1 ELSE 0 END) as active_sit_ins,
        SUM(CASE WHEN STATUS = 'APPROVED' THEN 1 ELSE 0 END) as approved_sit_ins
    FROM SIT_IN_RECORDS
    WHERE USER_IDNO = %s
    """
    stats = execute_query(stats_query, (session['user_id'],))
    
    if not stats:
        stats = {'total_sit_ins': 0, 'active_sit_ins': 0, 'approved_sit_ins': 0}
    else:
        stats = stats[0]
    
    return render_template('student/profile.html', student=student, stats=stats)

@student_bp.route('/profile-picture/<idno>')
@login_required
def get_profile_picture(idno):
    query = "SELECT PROFILE_PICTURE FROM USERS WHERE IDNO = %s"
    result = execute_query(query, (idno,))
    
    if result and result[0]['PROFILE_PICTURE']:
        image_data = result[0]['PROFILE_PICTURE']
        return send_file(
            BytesIO(image_data),
            mimetype='image/jpeg',
            as_attachment=False,
            download_name=f'profile_{idno}.jpg'
        )
    
    return redirect(url_for('static', filename='img/default-profile.png'))

@student_bp.route('/update-profile', methods=['POST'])
@login_required
@role_required('STUDENT')
def update_profile():
    try:
        lastname = request.form.get('lastname')
        firstname = request.form.get('firstname')
        middlename = request.form.get('middlename')
        email = request.form.get('email')
        course = request.form.get('course')
        year = int(request.form.get('year'))  # Convert to integer
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        profile_picture = request.files.get('profile_picture')
        
        # Validate required fields
        if not all([lastname, firstname, email, course, year]):
            flash('Please fill in all required fields', 'error')
            return redirect(url_for('student.profile'))
        
        # Validate year
        if year not in [1, 2, 3, 4]:
            flash('Invalid year level', 'error')
            return redirect(url_for('student.profile'))
        
        # Validate email format
        if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            flash('Invalid email format', 'error')
            return redirect(url_for('student.profile'))
        
        # Check if email already exists (excluding current user)
        email_check = execute_query(
            "SELECT COUNT(*) as count FROM USERS WHERE EMAIL = %s AND IDNO != %s", 
            (email, session['user_id'])
        )
        if email_check and email_check[0]['count'] > 0:
            flash('Email already registered', 'error')
            return redirect(url_for('student.profile'))
        
        # Update basic info
        update_query = """
        UPDATE USERS 
        SET LASTNAME = %s, FIRSTNAME = %s, MIDDLENAME = %s, EMAIL = %s, COURSE = %s, YEAR = %s
        WHERE IDNO = %s
        """
        execute_query(update_query, (lastname, firstname, middlename, email, course, year, session['user_id']))
        
        # Update session name
        session['name'] = f"{firstname} {lastname}"
        
        # Handle profile picture
        if profile_picture and profile_picture.filename:
            # Validate file type
            allowed_extensions = {'png', 'jpg', 'jpeg', 'gif'}
            if '.' not in profile_picture.filename or \
               profile_picture.filename.rsplit('.', 1)[1].lower() not in allowed_extensions:
                flash('Invalid file type. Please upload an image file.', 'error')
                return redirect(url_for('student.profile'))
            
            # Read and store the image
            image_data = profile_picture.read()
            
            # Update profile picture
            pic_query = "UPDATE USERS SET PROFILE_PICTURE = %s WHERE IDNO = %s"
            execute_query(pic_query, (image_data, session['user_id']))
        
        # Handle password change
        if current_password and new_password and confirm_password:
            if new_password != confirm_password:
                flash('New passwords do not match', 'error')
                return redirect(url_for('student.profile'))
            
            # Verify current password
            current_hash = hashlib.sha256(current_password.encode()).hexdigest()
            password_check = execute_query(
                "SELECT PASSWORD FROM USERS WHERE IDNO = %s", 
                (session['user_id'],)
            )
            
            if password_check and password_check[0]['PASSWORD'] == current_hash:
                # Update password
                new_hash = hashlib.sha256(new_password.encode()).hexdigest()
                password_query = "UPDATE USERS SET PASSWORD = %s WHERE IDNO = %s"
                execute_query(password_query, (new_hash, session['user_id']))
                flash('Password updated successfully', 'success')
            else:
                flash('Current password is incorrect', 'error')
                return redirect(url_for('student.profile'))
        
        flash('Profile updated successfully', 'success')
        return redirect(url_for('student.profile'))
    except Exception as e:
        flash(f'Error updating profile: {str(e)}', 'error')
        return redirect(url_for('student.profile'))

@student_bp.route('/sit-in-history')
@login_required
@role_required('STUDENT')
def sit_in_history():
    page = request.args.get('page', 1, type=int)
    per_page = 10
    
    # Get total count
    count_query = """
    SELECT COUNT(*) as total 
    FROM SIT_IN_RECORDS 
    WHERE USER_IDNO = %s
    """
    total = execute_query(count_query, (session['user_id'],))[0]['total']
    
    # Calculate offset
    offset = (page - 1) * per_page
    
    # Get paginated records with feedback status
    query = """
    SELECT 
        sr.*,
        l.LAB_NAME,
        p.PURPOSE_NAME,
        CASE WHEN f.FEEDBACK_ID IS NOT NULL THEN 1 ELSE 0 END as has_feedback,
        DATE_FORMAT(sr.CREATED_AT, '%Y-%m-%d %H:%i') as CREATED_AT
    FROM SIT_IN_RECORDS sr
    JOIN LABORATORIES l ON sr.LAB_ID = l.LAB_ID
    JOIN PURPOSES p ON sr.PURPOSE_ID = p.PURPOSE_ID
    LEFT JOIN FEEDBACKS f ON sr.RECORD_ID = f.RECORD_ID
    WHERE sr.USER_IDNO = %s
    ORDER BY sr.CREATED_AT DESC
    LIMIT %s OFFSET %s
    """
    sit_ins = execute_query(query, (session['user_id'], per_page, offset))
    
    # Calculate total pages
    total_pages = (total + per_page - 1) // per_page
    
    return render_template('student/sit_in_history.html',
                         sit_ins=sit_ins,
                         page=page,
                         total_pages=total_pages)

@student_bp.route('/feedback', methods=['POST'])
@login_required
@role_required('STUDENT')
def submit_feedback():
    data = request.get_json()
    record_id = data.get('record_id')
    rating = data.get('rating')
    comment = data.get('comment')
    
    if not all([record_id, rating, comment]):
        return jsonify({'success': False, 'message': 'Missing required fields'})
    
    try:
        # Check if sit-in exists and belongs to student
        check_query = """
        SELECT COUNT(*) as count
        FROM SIT_IN_RECORDS
        WHERE RECORD_ID = %s AND USER_IDNO = %s AND STATUS = 'COMPLETED'
        """
        result = execute_query(check_query, (record_id, session['user_id']))
        
        if result[0]['count'] == 0:
            return jsonify({'success': False, 'message': 'Invalid sit-in record'})
        
        # Check if feedback already exists
        check_feedback_query = """
        SELECT COUNT(*) as count
        FROM FEEDBACKS
        WHERE RECORD_ID = %s
        """
        feedback_result = execute_query(check_feedback_query, (record_id,))
        
        if feedback_result[0]['count'] > 0:
            return jsonify({'success': False, 'message': 'Feedback already submitted'})
        
        # Insert feedback
        insert_query = """
        INSERT INTO FEEDBACKS (RECORD_ID, USER_IDNO, RATING, COMMENT)
        VALUES (%s, %s, %s, %s)
        """
        execute_query(insert_query, (record_id, session['user_id'], rating, comment))
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@student_bp.route('/feedback/<int:record_id>')
@login_required
@role_required('STUDENT')
def get_feedback(record_id):
    query = """
    SELECT f.*
    FROM FEEDBACKS f
    JOIN SIT_IN_RECORDS sr ON f.RECORD_ID = sr.RECORD_ID
    WHERE f.RECORD_ID = %s AND sr.USER_IDNO = %s
    """
    feedback = execute_query(query, (record_id, session['user_id']))
    
    if feedback:
        return jsonify(feedback[0])
    return jsonify({'error': 'Feedback not found'}), 404

@student_bp.route('/feedback-history')
@login_required
@role_required('STUDENT')
def feedback_history():
    page = request.args.get('page', 1, type=int)
    per_page = 10
    
    # Get total count
    count_query = """
    SELECT COUNT(*) as total
    FROM FEEDBACKS f
    JOIN SIT_IN_RECORDS sr ON f.RECORD_ID = sr.RECORD_ID
    WHERE f.USER_IDNO = %s
    """
    total = execute_query(count_query, (session['user_id'],))[0]['total']
    
    # Calculate offset
    offset = (page - 1) * per_page
    
    # Get paginated feedbacks
    query = """
    SELECT 
        f.*,
        l.LAB_NAME,
        p.PURPOSE_NAME,
        DATE_FORMAT(sr.CREATED_AT, '%Y-%m-%d %H:%i') as SIT_IN_DATE
    FROM FEEDBACKS f
    JOIN SIT_IN_RECORDS sr ON f.RECORD_ID = sr.RECORD_ID
    JOIN LABORATORIES l ON sr.LAB_ID = l.LAB_ID
    JOIN PURPOSES p ON sr.PURPOSE_ID = p.PURPOSE_ID
    WHERE f.USER_IDNO = %s
    ORDER BY f.CREATED_AT DESC
    LIMIT %s OFFSET %s
    """
    feedbacks = execute_query(query, (session['user_id'], per_page, offset))
    
    # Calculate total pages
    total_pages = (total + per_page - 1) // per_page
    
    return render_template('student/feedback_history.html',
                         feedbacks=feedbacks,
                         page=page,
                         total_pages=total_pages)

@student_bp.route('/resources')
@login_required
@role_required('STUDENT')
def view_resources():
    try:
        # Get all enabled resources with their purposes
        resources_query = """
        SELECT 
            r.*,
            p.PURPOSE_NAME,
            CONCAT(u.FIRSTNAME, ' ', u.LASTNAME) as CREATED_BY_NAME,
            DATE_FORMAT(r.CREATED_AT, '%Y-%m-%d %H:%i') as CREATED_AT
        FROM LAB_RESOURCES r
        JOIN PURPOSES p ON r.PURPOSE_ID = p.PURPOSE_ID
        JOIN USERS u ON r.CREATED_BY = u.IDNO
        WHERE r.ENABLED = TRUE
        ORDER BY r.CREATED_AT DESC
        """
        resources = execute_query(resources_query)
        
        return render_template('student/resources.html', resources=resources)
    except Exception as e:
        print(f"Error in view_resources: {str(e)}")
        flash('An error occurred while loading resources', 'error')
        return redirect(url_for('student.dashboard'))

@student_bp.route('/resources/<int:resource_id>')
@login_required
@role_required('STUDENT')
def get_resource(resource_id):
    # Get resource details
    query = """
    SELECT 
        r.*,
        p.PURPOSE_NAME,
        CONCAT(u.FIRSTNAME, ' ', u.LASTNAME) as CREATED_BY
    FROM LAB_RESOURCES r
    JOIN PURPOSES p ON r.PURPOSE_ID = p.PURPOSE_ID
    LEFT JOIN USERS u ON r.CREATED_BY = u.IDNO
    WHERE r.RESOURCE_ID = %s AND r.ENABLED = TRUE
    """
    resource = execute_query(query, (resource_id,))
    
    if not resource:
        return jsonify({'error': 'Resource not found'}), 404
    
    resource = resource[0]
    return jsonify({
        'title': resource['TITLE'],
        'context': resource['CONTEXT'],
        'resource_type': resource['RESOURCE_TYPE'],
        'resource_value': resource['RESOURCE_VALUE'],
        'purpose_name': resource['PURPOSE_NAME'],
        'created_by': resource['CREATED_BY'],
        'created_at': resource['CREATED_AT'].strftime('%Y-%m-%d %H:%M:%S')
    })

@student_bp.context_processor
def inject_announcements():
    try:
        # Get recent announcements
        announcement_query = """
        SELECT 
            a.ANNOUNCEMENT_ID,
            a.TITLE,
            a.CONTENT,
            a.DATE_POSTED,
            CONCAT(u.FIRSTNAME, ' ', u.LASTNAME) as posted_by,
            u.FIRSTNAME as firstname,
            u.LASTNAME as lastname
        FROM ANNOUNCEMENTS a
        JOIN USERS u ON a.POSTED_BY = u.IDNO
        WHERE a.STATUS = 'active'
        ORDER BY a.DATE_POSTED DESC
        LIMIT 5
        """
        announcements = execute_query(announcement_query)
        return {'announcements': announcements}
    except Exception as e:
        print(f"Error fetching announcements: {str(e)}")
        return {'announcements': []}

@student_bp.route('/lab-schedules')
@login_required
@role_required('STUDENT')
def lab_schedules():
    try:
        # Get all labs
        labs_query = "SELECT * FROM LABORATORIES WHERE STATUS = 'active' ORDER BY LAB_NAME"
        labs = execute_query(labs_query)
        
        # Get all purposes
        purposes_query = "SELECT * FROM PURPOSES WHERE STATUS = 'active' ORDER BY PURPOSE_NAME"
        purposes = execute_query(purposes_query)
        
        # Get all schedules
        schedules_query = """
            SELECT 
                ls.*,
                l.LAB_NAME,
                p.PURPOSE_NAME
            FROM LAB_SCHEDULES ls
            JOIN LABORATORIES l ON ls.LAB_ID = l.LAB_ID
            JOIN PURPOSES p ON ls.PURPOSE_ID = p.PURPOSE_ID
            WHERE ls.STATUS = 'active'
            ORDER BY 
                FIELD(ls.DAY_OF_WEEK, 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'),
                ls.START_TIME
        """
        schedules = execute_query(schedules_query)
        
        return render_template('student/lab_schedules.html', 
                             labs=labs, 
                             purposes=purposes, 
                             schedules=schedules)
    except Exception as e:
        print(f"Error in lab_schedules: {str(e)}")
        flash('An error occurred while loading the lab schedules. Please try again later.', 'error')
        return redirect(url_for('student.dashboard'))

@student_bp.route('/rewards')
@login_required
@role_required('STUDENT')
def rewards():
    try:
        # Get student's points
        points_query = """
        SELECT 
            CURRENT_POINTS,
            TOTAL_POINTS
        FROM STUDENT_POINTS
        WHERE USER_IDNO = %s
        """
        points_result = execute_query(points_query, (session['user_id'],))
        points = points_result[0] if points_result else {'CURRENT_POINTS': 0, 'TOTAL_POINTS': 0}

        # Get points history
        history_query = """
        SELECT 
            ph.*,
            CONCAT(u.FIRSTNAME, ' ', u.LASTNAME) as added_by_name
        FROM POINT_HISTORY ph
        JOIN USERS u ON ph.ADDED_BY = u.IDNO
        WHERE ph.USER_IDNO = %s
        ORDER BY ph.CREATED_AT DESC
        """
        points_history = execute_query(history_query, (session['user_id'],))
        if points_history is None:
            points_history = []

        # Get redemption history
        redemption_query = """
        SELECT 
            pr.*,
            sr.DATE as sit_in_date,
            sr.STATUS
        FROM POINT_REDEMPTIONS pr
        JOIN SIT_IN_RECORDS sr ON pr.SIT_IN_RECORD_ID = sr.RECORD_ID
        WHERE pr.USER_IDNO = %s
        ORDER BY pr.CREATED_AT DESC
        """
        redemption_history = execute_query(redemption_query, (session['user_id'],))
        if redemption_history is None:
            redemption_history = []

        return render_template('student/rewards.html',
                             points=points,
                             points_history=points_history,
                             redemption_history=redemption_history)
                             
    except Exception as e:
        print(f"Error in rewards page: {str(e)}")
        return render_template('error.html',
                             error_message="An error occurred while loading the rewards page. Please try again later.",
                             back_url=url_for('student.dashboard')) 