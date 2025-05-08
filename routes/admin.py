from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify, send_file, current_app, Response
from db import execute_query
from functools import wraps
from routes.auth import login_required, role_required
import os
from datetime import datetime, timedelta
from io import BytesIO, StringIO
import csv
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
import xlsxwriter
from werkzeug.utils import secure_filename
import re
import traceback
import base64
import io

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

@admin_bp.context_processor
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
        # Convert keys to lowercase
        announcements = [{k.lower(): v for k, v in announcement.items()} for announcement in announcements]
        return {'announcements': announcements}
    except Exception as e:
        print(f"Error fetching announcements: {str(e)}")
        return {'announcements': []}

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login to access this page', 'error')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_type' not in session or session['user_type'] != 'ADMIN':
            flash('You do not have permission to access this page', 'error')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

@admin_bp.route('/dashboard')
@login_required
@role_required('ADMIN')
def dashboard():
    try:
        # Get basic statistics
        stats_query = """
        SELECT 
            (SELECT COUNT(*) FROM USERS WHERE USER_TYPE = 'STUDENT') as total_students,
            (SELECT COUNT(*) FROM SIT_IN_RECORDS WHERE SESSION = 'ON_GOING') as active_sit_ins,
            (SELECT COUNT(*) FROM LABORATORIES) as total_labs,
            (SELECT COUNT(*) FROM PURPOSES) as total_purposes,
            (SELECT COUNT(*) FROM RESERVATIONS WHERE STATUS = 'PENDING') as pending_reservations
        """
        stats = execute_query(stats_query)[0]

        # Get lab usage statistics
        lab_query = """
        SELECT l.LAB_NAME, COUNT(sr.RECORD_ID) as usage_count
        FROM LABORATORIES l
        LEFT JOIN SIT_IN_RECORDS sr ON l.LAB_ID = sr.LAB_ID
        GROUP BY l.LAB_ID, l.LAB_NAME
        ORDER BY usage_count DESC
        """
        lab_stats = execute_query(lab_query)
        lab_labels = [lab['LAB_NAME'] for lab in lab_stats]
        lab_data = [lab['usage_count'] for lab in lab_stats]

        # Get purpose usage statistics
        purpose_query = """
        SELECT p.PURPOSE_NAME as purpose_name, COUNT(s.RECORD_ID) as usage_count
        FROM PURPOSES p
        JOIN SIT_IN_RECORDS s ON p.PURPOSE_ID = s.PURPOSE_ID
        GROUP BY p.PURPOSE_NAME
        HAVING usage_count > 0
        ORDER BY usage_count DESC
        """
        purpose_stats = execute_query(purpose_query)
        purpose_labels = [purpose['purpose_name'] for purpose in purpose_stats]
        purpose_data = [purpose['usage_count'] for purpose in purpose_stats]

        # Get recent sit-ins
        sit_in_query = """
        SELECT 
            sr.RECORD_ID,
            CONCAT(u.FIRSTNAME, ' ', u.LASTNAME) as student_name,
            l.LAB_NAME as lab_name,
            p.PURPOSE_NAME as purpose_name,
            sr.DATE as date,
            sr.STATUS as status,
            DATE_FORMAT(sr.CREATED_AT, '%Y-%m-%d %H:%i:%s') as created_at
        FROM SIT_IN_RECORDS sr
        JOIN USERS u ON sr.USER_IDNO = u.IDNO
        JOIN LABORATORIES l ON sr.LAB_ID = l.LAB_ID
        JOIN PURPOSES p ON sr.PURPOSE_ID = p.PURPOSE_ID
        ORDER BY sr.CREATED_AT DESC
        LIMIT 10
        """
        recent_sit_ins = execute_query(sit_in_query)

        # Get recent feedback
        feedback_query = """
        SELECT 
            f.FEEDBACK_ID,
            f.RATING,
            COALESCE(f.COMMENT, '') as comment,
            DATE_FORMAT(f.CREATED_AT, '%Y-%m-%d %H:%i') as created_at,
            CONCAT(u.FIRSTNAME, ' ', u.LASTNAME) as student_name,
            l.LAB_NAME as lab_name,
            COALESCE(f.RATING, 0) as rating
        FROM FEEDBACKS f
        JOIN SIT_IN_RECORDS sr ON f.RECORD_ID = sr.RECORD_ID
        JOIN USERS u ON f.USER_IDNO = u.IDNO
        JOIN LABORATORIES l ON sr.LAB_ID = l.LAB_ID
        ORDER BY f.CREATED_AT DESC
        LIMIT 5
        """
        recent_feedback = execute_query(feedback_query)

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

        # Get pending reservations for alert
        pending_reservations_query = """
        SELECT 
            r.RESERVATION_ID,
            CONCAT(u.FIRSTNAME, ' ', u.LASTNAME) as student_name,
            l.LAB_NAME,
            DATE_FORMAT(r.RESERVATION_DATE, '%M %d, %Y') as formatted_date,
            DATE_FORMAT(r.TIME_IN, '%h:%i %p') as formatted_time
        FROM RESERVATIONS r
        JOIN USERS u ON r.USER_IDNO = u.IDNO
        JOIN LABORATORIES l ON r.LAB_ID = l.LAB_ID
        WHERE r.STATUS = 'PENDING'
        ORDER BY r.RESERVATION_DATE ASC, r.TIME_IN ASC
        LIMIT 5
        """
        pending_reservations = execute_query(pending_reservations_query)

        return render_template('admin/dashboard.html',
                             stats=stats,
                             lab_labels=lab_labels,
                             lab_data=lab_data,
                             purpose_labels=purpose_labels,
                             purpose_data=purpose_data,
                             recent_sit_ins=recent_sit_ins,
                             recent_feedback=recent_feedback,
                             announcements=announcements,
                             pending_reservations=pending_reservations)
    except Exception as e:
        print(f"Error in admin dashboard: {str(e)}")
        return render_template('error.html', 
                             error_message="An error occurred while loading the dashboard.",
                             back_url=url_for('auth.login'))

@admin_bp.route('/manage-students')
@login_required
@role_required('ADMIN')
def manage_students():
    try:
        page = request.args.get('page', 1, type=int)
        per_page = 10
        
        # Get total count
        count_query = "SELECT COUNT(*) as total FROM USERS WHERE USER_TYPE = 'STUDENT'"
        total = execute_query(count_query)[0]['total']
        
        # Calculate offset
        offset = (page - 1) * per_page
        
        # Get paginated students with their sit-in limits
        students_query = """
        SELECT 
            u.*,
            COALESCE(sl.SIT_IN_COUNT, 0) as SIT_IN_COUNT,
            COALESCE(sl.MAX_SIT_INS, 
                CASE 
                    WHEN u.COURSE IN ('BSIT', 'BSCS') THEN 30 
                    ELSE 15 
                END
            ) as MAX_SIT_INS
        FROM USERS u
        LEFT JOIN SIT_IN_LIMITS sl ON u.IDNO = sl.USER_IDNO
        WHERE u.USER_TYPE = 'STUDENT'
        ORDER BY u.LASTNAME, u.FIRSTNAME
        LIMIT %s OFFSET %s
        """
        students = execute_query(students_query, (per_page, offset))
        
        # Calculate total pages
        total_pages = (total + per_page - 1) // per_page
        
        return render_template('admin/manage_students.html', 
                             students=students,
                             current_page=page,
                             total_pages=total_pages)
    except Exception as e:
        print(f"Error in manage students: {str(e)}")
        flash('An error occurred while loading students', 'error')
        return redirect(url_for('admin.dashboard'))

@admin_bp.route('/labs')
@login_required
@role_required('ADMIN')
def manage_labs():
    page = request.args.get('page', 1, type=int)
    per_page = 10
    
    # Get total count
    count_query = "SELECT COUNT(*) as total FROM LABORATORIES"
    total = execute_query(count_query)[0]['total']
    
    # Calculate offset
    offset = (page - 1) * per_page
    
    # Get paginated labs with computer counts
    labs_query = """
    SELECT l.*, 
           COUNT(c.COMPUTER_ID) as total_computers,
           SUM(CASE WHEN c.STATUS = 'available' THEN 1 ELSE 0 END) as available_computers,
           SUM(CASE WHEN c.STATUS = 'in_use' THEN 1 ELSE 0 END) as in_use_computers,
           SUM(CASE WHEN c.STATUS = 'maintenance' THEN 1 ELSE 0 END) as maintenance_computers
    FROM LABORATORIES l
    LEFT JOIN COMPUTERS c ON l.LAB_ID = c.LAB_ID
    GROUP BY l.LAB_ID
    ORDER BY l.LAB_NAME
    LIMIT %s OFFSET %s
    """
    labs = execute_query(labs_query, (per_page, offset))
    
    if labs is None:
        labs = []
    
    # Calculate total pages
    total_pages = (total + per_page - 1) // per_page
    
    return render_template('admin/labs.html', 
                         labs=labs,
                         current_page=page,
                         total_pages=total_pages)

@admin_bp.route('/labs/add', methods=['POST'])
@login_required
@role_required('ADMIN')
def add_lab():
    try:
        lab_name = request.form.get('lab_name')
        computer_count = int(request.form.get('computer_count', 50))
        
        if not lab_name:
            flash('Lab name is required', 'error')
            return redirect(url_for('admin.manage_labs'))
        
        # Check if lab already exists
        check_query = "SELECT COUNT(*) as count FROM LABORATORIES WHERE LAB_NAME = %s"
        result = execute_query(check_query, (lab_name,))
        
        if result[0]['count'] > 0:
            flash('Lab already exists', 'error')
            return redirect(url_for('admin.manage_labs'))
        
        # Add new lab
        insert_query = "INSERT INTO LABORATORIES (LAB_NAME, STATUS) VALUES (%s, 'active')"
        execute_query(insert_query, (lab_name,))
        
        # Get lab ID
        lab_result = execute_query("SELECT LAB_ID FROM LABORATORIES WHERE LAB_NAME = %s", (lab_name,))
        if lab_result and len(lab_result) > 0:
            lab_id = lab_result[0]['LAB_ID']
            
            # Add computers
            for i in range(1, computer_count + 1):
                execute_query("""
                    INSERT INTO COMPUTERS (LAB_ID, COMPUTER_NUMBER, STATUS)
                    VALUES (%s, %s, 'available')
                """, (lab_id, i))
            
            flash('Lab and computers added successfully', 'success')
        else:
            flash('Error creating lab', 'error')
            
        return redirect(url_for('admin.manage_labs'))
    except Exception as e:
        print(f"Error adding lab: {str(e)}")
        flash('An error occurred while adding the lab', 'error')
        return redirect(url_for('admin.manage_labs'))

@admin_bp.route('/labs/edit/<int:lab_id>', methods=['POST'])
@login_required
@role_required('ADMIN')
def edit_lab(lab_id):
    lab_name = request.form.get('lab_name')
    status = request.form.get('status')
    
    if not lab_name:
        flash('Lab name is required', 'error')
        return redirect(url_for('admin.manage_labs'))
    
    # Check if lab already exists (excluding current lab)
    check_query = "SELECT COUNT(*) as count FROM LABORATORIES WHERE LAB_NAME = %s AND LAB_ID != %s"
    result = execute_query(check_query, (lab_name, lab_id))
    
    if result[0]['count'] > 0:
        flash('Lab already exists', 'error')
        return redirect(url_for('admin.manage_labs'))
    
    # Update lab
    update_query = "UPDATE LABORATORIES SET LAB_NAME = %s, STATUS = %s WHERE LAB_ID = %s"
    execute_query(update_query, (lab_name, status, lab_id))
    
    flash('Lab updated successfully', 'success')
    return redirect(url_for('admin.manage_labs'))

@admin_bp.route('/labs/delete/<int:lab_id>')
@login_required
@role_required('ADMIN')
def delete_lab(lab_id):
    # Check if lab is in use
    check_query = "SELECT COUNT(*) as count FROM SIT_IN_RECORDS WHERE LAB_ID = %s"
    result = execute_query(check_query, (lab_id,))
    
    if result[0]['count'] > 0:
        flash('Cannot delete lab that is in use', 'error')
        return redirect(url_for('admin.manage_labs'))
    
    # Delete computers first
    execute_query("DELETE FROM COMPUTERS WHERE LAB_ID = %s", (lab_id,))
    
    # Delete lab
    execute_query("DELETE FROM LABORATORIES WHERE LAB_ID = %s", (lab_id,))
    
    flash('Lab deleted successfully', 'success')
    return redirect(url_for('admin.manage_labs'))

@admin_bp.route('/purposes')
@login_required
@role_required('ADMIN')
def manage_purposes():
    page = request.args.get('page', 1, type=int)
    per_page = 10
    
    # Get total count
    count_query = "SELECT COUNT(*) as total FROM PURPOSES"
    total = execute_query(count_query)[0]['total']
    
    # Calculate offset
    offset = (page - 1) * per_page
    
    # Get paginated purposes
    purposes_query = """
    SELECT * FROM PURPOSES 
    ORDER BY PURPOSE_NAME
    LIMIT %s OFFSET %s
    """
    purposes = execute_query(purposes_query, (per_page, offset))
    
    # Calculate total pages
    total_pages = (total + per_page - 1) // per_page
    
    return render_template('admin/purposes.html', 
                         purposes=purposes,
                         current_page=page,
                         total_pages=total_pages)

@admin_bp.route('/purposes/add', methods=['POST'])
@login_required
@role_required('ADMIN')
def add_purpose():
    purpose_name = request.form.get('purpose_name')
    
    if not purpose_name:
        flash('Purpose name is required', 'error')
        return redirect(url_for('admin.manage_purposes'))
    
    # Check if purpose already exists
    check_query = "SELECT COUNT(*) as count FROM PURPOSES WHERE PURPOSE_NAME = %s"
    result = execute_query(check_query, (purpose_name,))
    
    if result[0]['count'] > 0:
        flash('Purpose already exists', 'error')
        return redirect(url_for('admin.manage_purposes'))
    
    # Add new purpose
    insert_query = "INSERT INTO PURPOSES (PURPOSE_NAME, STATUS) VALUES (%s, 'active')"
    execute_query(insert_query, (purpose_name,))
    
    flash('Purpose added successfully', 'success')
    return redirect(url_for('admin.manage_purposes'))

@admin_bp.route('/purposes/edit/<int:purpose_id>', methods=['POST'])
@login_required
@role_required('ADMIN')
def edit_purpose(purpose_id):
    purpose_name = request.form.get('purpose_name')
    status = request.form.get('status')
    
    if not purpose_name:
        flash('Purpose name is required', 'error')
        return redirect(url_for('admin.manage_purposes'))
    
    # Check if purpose already exists (excluding current purpose)
    check_query = "SELECT COUNT(*) as count FROM PURPOSES WHERE PURPOSE_NAME = %s AND PURPOSE_ID != %s"
    result = execute_query(check_query, (purpose_name, purpose_id))
    
    if result[0]['count'] > 0:
        flash('Purpose already exists', 'error')
        return redirect(url_for('admin.manage_purposes'))
    
    # Update purpose
    update_query = "UPDATE PURPOSES SET PURPOSE_NAME = %s, STATUS = %s WHERE PURPOSE_ID = %s"
    execute_query(update_query, (purpose_name, status, purpose_id))
    
    flash('Purpose updated successfully', 'success')
    return redirect(url_for('admin.manage_purposes'))

@admin_bp.route('/purposes/delete/<int:purpose_id>')
@login_required
@role_required('ADMIN')
def delete_purpose(purpose_id):
    # Check if purpose is in use
    check_query = "SELECT COUNT(*) as count FROM SIT_IN_RECORDS WHERE PURPOSE_ID = %s"
    result = execute_query(check_query, (purpose_id,))
    
    if result[0]['count'] > 0:
        flash('Cannot delete purpose that is in use', 'error')
        return redirect(url_for('admin.manage_purposes'))
    
    # Delete purpose
    delete_query = "DELETE FROM PURPOSES WHERE PURPOSE_ID = %s"
    execute_query(delete_query, (purpose_id,))
    
    flash('Purpose deleted successfully', 'success')
    return redirect(url_for('admin.manage_purposes'))

@admin_bp.route('/purpose/<int:purpose_id>', methods=['GET', 'POST', 'DELETE'])
@login_required
@role_required('ADMIN')
def manage_purpose(purpose_id):
    try:
        if request.method == 'GET':
            purpose = execute_query("""
                SELECT * FROM PURPOSES 
                WHERE PURPOSE_ID = %s
            """, (purpose_id,))
            
            if not purpose:
                return jsonify({'error': 'Purpose not found'}), 404
                
            return jsonify(purpose[0])
            
        elif request.method == 'POST':
            purpose_name = request.form.get('purpose_name')
            status = request.form.get('status')
            
            if not purpose_name:
                return jsonify({'success': False, 'message': 'Purpose name is required'}), 400
                
            # Check if purpose exists
            purpose_query = "SELECT * FROM PURPOSES WHERE PURPOSE_ID = %s"
            purpose = execute_query(purpose_query, (purpose_id,))
            
            if not purpose:
                return jsonify({'success': False, 'message': 'Purpose not found'}), 404
                
            # Check if purpose already exists (excluding current purpose)
            check_query = "SELECT COUNT(*) as count FROM PURPOSES WHERE PURPOSE_NAME = %s AND PURPOSE_ID != %s"
            result = execute_query(check_query, (purpose_name, purpose_id))
            
            if result[0]['count'] > 0:
                return jsonify({'success': False, 'message': 'Purpose already exists'}), 400
            
            # Update purpose
            update_query = "UPDATE PURPOSES SET PURPOSE_NAME = %s, STATUS = %s WHERE PURPOSE_ID = %s"
            execute_query(update_query, (purpose_name, status, purpose_id))
            
            return jsonify({'success': True})
            
        elif request.method == 'DELETE':
            # Check if purpose exists
            purpose_query = "SELECT * FROM PURPOSES WHERE PURPOSE_ID = %s"
            purpose = execute_query(purpose_query, (purpose_id,))
            
            if not purpose:
                return jsonify({'success': False, 'message': 'Purpose not found'}), 404
            
            # Check if purpose is in use
            check_query = "SELECT COUNT(*) as count FROM SIT_IN_RECORDS WHERE PURPOSE_ID = %s"
            result = execute_query(check_query, (purpose_id,))
            
            if result[0]['count'] > 0:
                return jsonify({'success': False, 'message': 'Cannot delete purpose that is in use'}), 400
            
            # Delete purpose
            execute_query("DELETE FROM PURPOSES WHERE PURPOSE_ID = %s", (purpose_id,))
            
            return jsonify({'success': True})
            
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@admin_bp.route('/announcement/<int:announcement_id>', methods=['GET', 'POST', 'DELETE'])
@login_required
@role_required('ADMIN')
def manage_announcement(announcement_id):
    if request.method == 'GET':
        announcement = execute_query("""
            SELECT 
                a.ANNOUNCEMENT_ID,
                a.TITLE,
                a.CONTENT,
                a.DATE_POSTED,
                a.STATUS,
                a.POSTED_BY,
                u.FIRSTNAME,
                u.LASTNAME
            FROM ANNOUNCEMENTS a
            JOIN USERS u ON a.POSTED_BY = u.IDNO
            WHERE a.ANNOUNCEMENT_ID = %s
        """, (announcement_id,))
        
        if announcement:
            return jsonify(announcement[0])
        return jsonify({'error': 'Announcement not found'}), 404
        
    elif request.method == 'POST':
        title = request.form.get('title')
        content = request.form.get('content')
        
        if not title or not content:
            return jsonify({'success': False, 'message': 'Title and content are required'})
            
        try:
            execute_query("""
                UPDATE ANNOUNCEMENTS 
                SET TITLE = %s, CONTENT = %s
                WHERE ANNOUNCEMENT_ID = %s
            """, (title, content, announcement_id))
            return jsonify({'success': True})
        except Exception as e:
            return jsonify({'success': False, 'message': str(e)})
            
    elif request.method == 'DELETE':
        try:
            execute_query("DELETE FROM ANNOUNCEMENTS WHERE ANNOUNCEMENT_ID = %s", (announcement_id,))
            return jsonify({'success': True})
        except Exception as e:
            return jsonify({'success': False, 'message': str(e)})

@admin_bp.route('/announcement/<int:announcement_id>/status', methods=['POST'])
@login_required
@role_required('ADMIN')
def toggle_announcement_status(announcement_id):
    data = request.get_json()
    new_status = data.get('status')
    
    if new_status not in ['active', 'inactive']:
        return jsonify({'success': False, 'message': 'Invalid status'})
        
    try:
        execute_query("""
            UPDATE ANNOUNCEMENTS 
            SET STATUS = %s
            WHERE ANNOUNCEMENT_ID = %s
        """, (new_status, announcement_id))
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@admin_bp.route('/manage-announcements', methods=['GET', 'POST'])
@login_required
@role_required('ADMIN')
def manage_announcements():
    if request.method == 'POST':
        title = request.form.get('title')
        content = request.form.get('content')
        
        if not title or not content:
            flash('Title and content are required', 'error')
            return redirect(url_for('admin.manage_announcements'))
            
        try:
            execute_query("""
                INSERT INTO ANNOUNCEMENTS (TITLE, CONTENT, POSTED_BY, DATE_POSTED, STATUS)
                VALUES (%s, %s, %s, NOW(), 'active')
            """, (title, content, session['user_id']))
            flash('Announcement posted successfully', 'success')
        except Exception as e:
            flash(f'Error posting announcement: {str(e)}', 'error')
            
        return redirect(url_for('admin.manage_announcements'))
    
    page = request.args.get('page', 1, type=int)
    per_page = 10
    
    # Get total count
    count_query = "SELECT COUNT(*) as total FROM ANNOUNCEMENTS"
    total = execute_query(count_query)[0]['total']
    
    # Calculate offset
    offset = (page - 1) * per_page
    
    # Get paginated announcements
    announcements = execute_query("""
        SELECT 
            a.ANNOUNCEMENT_ID,
            a.TITLE,
            a.CONTENT,
            a.DATE_POSTED,
            a.STATUS,
            u.FIRSTNAME,
            u.LASTNAME
        FROM ANNOUNCEMENTS a
        JOIN USERS u ON a.POSTED_BY = u.IDNO
        ORDER BY a.DATE_POSTED DESC
        LIMIT %s OFFSET %s
    """, (per_page, offset))
    
    # Calculate total pages
    total_pages = (total + per_page - 1) // per_page
    
    return render_template('admin/announcements.html', 
                         announcements=announcements,
                         current_page=page,
                         total_pages=total_pages)

@admin_bp.route('/student/<idno>', methods=['GET', 'POST'])
@login_required
@role_required('ADMIN')
def get_student(idno):
    try:
        # Check if user is logged in and is admin
        if 'user_id' not in session or 'user_type' not in session or session['user_type'] != 'ADMIN':
            return jsonify({'error': 'Unauthorized access'}), 401

        # Validate student ID
        if not idno or not isinstance(idno, str):
            return jsonify({'error': 'Invalid student ID'}), 400

        if request.method == 'GET':
            query = """
            SELECT 
                u.IDNO,
                u.FIRSTNAME,
                u.LASTNAME,
                u.COURSE,
                u.YEAR,
                u.EMAIL,
                u.STATUS,
                COALESCE(sl.MAX_SIT_INS - sl.SIT_IN_COUNT, 0) as remaining_sessions,
                COALESCE(sp.CURRENT_POINTS, 0) as current_points,
                COALESCE(sp.TOTAL_POINTS, 0) as total_points
            FROM USERS u
            LEFT JOIN SIT_IN_LIMITS sl ON u.IDNO = sl.USER_IDNO
            LEFT JOIN STUDENT_POINTS sp ON u.IDNO = sp.USER_IDNO
            WHERE u.IDNO = %s AND u.USER_TYPE = 'STUDENT'
            """
            student = execute_query(query, (idno,))
            
            if not student or len(student) == 0:
                return jsonify({'error': 'Student not found'}), 404
                
            return jsonify(student[0])
            
        elif request.method == 'POST':
            # Get data from request
            data = request.get_json() if request.is_json else request.form
            
            if not data:
                return jsonify({'error': 'No data provided'}), 400
                
            # Validate required fields
            required_fields = ['FIRSTNAME', 'LASTNAME', 'COURSE', 'YEAR', 'EMAIL']
            missing_fields = [field for field in required_fields if not data.get(field)]
            
            if missing_fields:
                return jsonify({
                    'error': 'Missing required fields',
                    'missing_fields': missing_fields
                }), 400
                
            # Validate year is a number
            try:
                year = int(data.get('YEAR'))
                if year < 1 or year > 4:
                    return jsonify({'error': 'Year must be between 1 and 4'}), 400
            except ValueError:
                return jsonify({'error': 'Year must be a number'}), 400
                
            # Validate email format
            email = data.get('EMAIL')
            if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
                return jsonify({'error': 'Invalid email format'}), 400
                
            # Check if student exists
            student_query = "SELECT * FROM USERS WHERE IDNO = %s AND USER_TYPE = 'STUDENT'"
            student = execute_query(student_query, (idno,))
            
            if not student:
                return jsonify({'error': 'Student not found'}), 404
                
            # Update student information
            update_query = """
            UPDATE USERS 
            SET FIRSTNAME = %s,
                LASTNAME = %s,
                COURSE = %s,
                YEAR = %s,
                EMAIL = %s
            WHERE IDNO = %s AND USER_TYPE = 'STUDENT'
            """
            execute_query(update_query, (
                data.get('FIRSTNAME'),
                data.get('LASTNAME'),
                data.get('COURSE'),
                year,
                email,
                idno
            ))
            
            # Update sit-in limits if remaining_sessions is provided
            if 'remaining_sessions' in data:
                try:
                    remaining_sessions = int(data['remaining_sessions'])
                    if remaining_sessions < 0:
                        return jsonify({'error': 'Remaining sessions cannot be negative'}), 400
                        
                    # First check if record exists
                    check_query = "SELECT COUNT(*) as count FROM SIT_IN_LIMITS WHERE USER_IDNO = %s"
                    result = execute_query(check_query, (idno,))
                    
                    if result[0]['count'] > 0:
                        # Update existing record
                        update_limits_query = """
                        UPDATE SIT_IN_LIMITS 
                        SET MAX_SIT_INS = SIT_IN_COUNT + %s
                        WHERE USER_IDNO = %s
                        """
                        execute_query(update_limits_query, (remaining_sessions, idno))
                    else:
                        # Insert new record
                        insert_limits_query = """
                        INSERT INTO SIT_IN_LIMITS (USER_IDNO, SIT_IN_COUNT, MAX_SIT_INS)
                        VALUES (%s, 0, %s)
                        """
                        execute_query(insert_limits_query, (idno, remaining_sessions))
                except ValueError:
                    return jsonify({'error': 'Remaining sessions must be a number'}), 400
            
            return jsonify({
                'success': True, 
                'message': 'Student information updated successfully'
            })
        
    except Exception as e:
        # Log the error for debugging
        current_app.logger.error(f"Error in get_student: {str(e)}")
        return jsonify({
            'error': 'Internal server error',
            'details': str(e)
        }), 500

@admin_bp.route('/student/<idno>/status', methods=['POST'])
@login_required
@role_required('ADMIN')
def toggle_student_status(idno):
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'No data provided'}), 400
            
        new_status = data.get('status')
        if not new_status:
            return jsonify({'success': False, 'message': 'Status is required'}), 400
            
        if new_status not in ['active', 'inactive']:
            return jsonify({'success': False, 'message': 'Invalid status'}), 400
            
        # Check if student exists
        student_query = "SELECT * FROM USERS WHERE IDNO = %s AND USER_TYPE = 'STUDENT'"
        student = execute_query(student_query, (idno,))
        
        if not student:
            return jsonify({'success': False, 'message': 'Student not found'}), 404
            
        # Update status
        execute_query("""
            UPDATE USERS 
            SET STATUS = %s
            WHERE IDNO = %s AND USER_TYPE = 'STUDENT'
        """, (new_status, idno))
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@admin_bp.route('/profile', methods=['GET', 'POST'])
@login_required
@admin_required
def manage_profile():
    if request.method == 'POST':
        try:
            firstname = request.form.get('firstname')
            lastname = request.form.get('lastname')
            email = request.form.get('email')
            current_password = request.form.get('current_password')
            new_password = request.form.get('new_password')
            
            # Get current user details
            user_query = "SELECT * FROM USERS WHERE IDNO = %s"
            user = execute_query(user_query, (session['user_id'],))[0]
            
            # Update basic info
            update_query = """
            UPDATE USERS 
            SET FIRSTNAME = %s, LASTNAME = %s, EMAIL = %s
            WHERE IDNO = %s
            """
            execute_query(update_query, (firstname, lastname, email, session['user_id']))
            
            # Update password if provided
            if current_password and new_password:
                if user['PASSWORD'] != current_password:
                    flash('Current password is incorrect', 'error')
                    return redirect(url_for('admin.manage_profile'))
                    
                password_query = "UPDATE USERS SET PASSWORD = %s WHERE IDNO = %s"
                execute_query(password_query, (new_password, session['user_id']))
            
            flash('Profile updated successfully', 'success')
            return redirect(url_for('admin.manage_profile'))
            
        except Exception as e:
            flash(f'Error updating profile: {str(e)}', 'error')
            return redirect(url_for('admin.manage_profile'))
    
    # Get current user details
    user_query = "SELECT * FROM USERS WHERE IDNO = %s"
    user = execute_query(user_query, (session['user_id'],))[0]
    
    return render_template('admin/profile.html', user=user)

@admin_bp.route('/profile/picture', methods=['GET', 'POST'])
@login_required
@role_required('ADMIN')
def manage_profile_picture():
    if request.method == 'GET':
        # Get profile picture from database
        query = "SELECT PROFILE_PICTURE FROM USERS WHERE IDNO = %s"
        result = execute_query(query, (session['user_id'],))
        
        if result and result[0]['PROFILE_PICTURE']:
            image_data = result[0]['PROFILE_PICTURE']
            return send_file(
                BytesIO(image_data),
                mimetype='image/jpeg',
                as_attachment=False,
                download_name=f'profile_{session["user_id"]}.jpg'
            )
        else:
            # Return default profile picture
            return send_file(os.path.join('static', 'images', 'default_profile.jpg'))
            
    elif request.method == 'POST':
        if 'profile_picture' not in request.files:
            return jsonify({'success': False, 'message': 'No file uploaded'}), 400
            
        file = request.files['profile_picture']
        
        if file.filename == '':
            return jsonify({'success': False, 'message': 'No file selected'}), 400
            
        if file and allowed_file(file.filename):
            # Read the file data
            image_data = file.read()
            
            # Update profile picture in database
            update_query = "UPDATE USERS SET PROFILE_PICTURE = %s WHERE IDNO = %s"
            execute_query(update_query, (image_data, session['user_id']))
            
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'message': 'Invalid file type'}), 400

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'png', 'jpg', 'jpeg', 'gif'}

@admin_bp.route('/lab/<int:lab_id>', methods=['GET', 'POST', 'DELETE'])
@login_required
@role_required('ADMIN')
def manage_lab(lab_id):
    try:
        if request.method == 'GET':
            # Get lab details with computer counts
            lab = execute_query("""
                SELECT 
                    l.LAB_ID,
                    l.LAB_NAME,
                    l.STATUS,
                    CAST(COUNT(c.COMPUTER_ID) AS SIGNED) as total_computers,
                    CAST(SUM(CASE WHEN c.STATUS = 'available' THEN 1 ELSE 0 END) AS SIGNED) as available_computers,
                    CAST(SUM(CASE WHEN c.STATUS = 'in_use' THEN 1 ELSE 0 END) AS SIGNED) as in_use_computers,
                    CAST(SUM(CASE WHEN c.STATUS = 'maintenance' THEN 1 ELSE 0 END) AS SIGNED) as maintenance_computers
                FROM LABORATORIES l
                LEFT JOIN COMPUTERS c ON l.LAB_ID = c.LAB_ID
                WHERE l.LAB_ID = %s
                GROUP BY l.LAB_ID, l.LAB_NAME, l.STATUS
            """, (lab_id,))
            
            if not lab or len(lab) == 0:
                return jsonify({'error': 'Lab not found'}), 404
                
            return jsonify(lab[0])
            
        elif request.method == 'POST':
            data = request.form
            lab_name = data.get('lab_name')
            status = data.get('status')
            
            if not lab_name:
                return jsonify({'success': False, 'message': 'Lab name is required'}), 400
                
            # Check if lab exists
            lab_query = "SELECT * FROM LABORATORIES WHERE LAB_ID = %s"
            lab = execute_query(lab_query, (lab_id,))
            
            if not lab or len(lab) == 0:
                return jsonify({'success': False, 'message': 'Lab not found'}), 404
                
            # Check if lab already exists (excluding current lab)
            check_query = "SELECT COUNT(*) as count FROM LABORATORIES WHERE LAB_NAME = %s AND LAB_ID != %s"
            result = execute_query(check_query, (lab_name, lab_id))
            
            if result[0]['count'] > 0:
                return jsonify({'success': False, 'message': 'Lab already exists'}), 400
            
            # Update lab
            update_query = "UPDATE LABORATORIES SET LAB_NAME = %s, STATUS = %s WHERE LAB_ID = %s"
            execute_query(update_query, (lab_name, status, lab_id))
            
            return jsonify({'success': True, 'message': 'Lab updated successfully'})
            
        elif request.method == 'DELETE':
            # Check if lab exists
            lab_query = "SELECT * FROM LABORATORIES WHERE LAB_ID = %s"
            lab = execute_query(lab_query, (lab_id,))
            
            if not lab or len(lab) == 0:
                return jsonify({'success': False, 'message': 'Lab not found'}), 404
            
            # Check if lab is in use
            check_query = "SELECT COUNT(*) as count FROM SIT_IN_RECORDS WHERE LAB_ID = %s"
            result = execute_query(check_query, (lab_id,))
            
            if result[0]['count'] > 0:
                return jsonify({'success': False, 'message': 'Cannot delete lab that is in use'}), 400
            
            # Delete computers first
            execute_query("DELETE FROM COMPUTERS WHERE LAB_ID = %s", (lab_id,))
            
            # Delete lab
            execute_query("DELETE FROM LABORATORIES WHERE LAB_ID = %s", (lab_id,))
            
            return jsonify({'success': True, 'message': 'Lab deleted successfully'})
            
    except Exception as e:
        print(f"Error in manage_lab: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

@admin_bp.route('/sit-in')
@login_required
@role_required('ADMIN')
def sit_in_management():
    try:
        # Get today's completed sit-ins
        today_query = """
        SELECT 
            sr.*,
            u.FIRSTNAME,
            u.LASTNAME,
            l.LAB_NAME,
            p.PURPOSE_NAME,
            DATE_FORMAT(sr.TIME_IN, '%h:%i %p') as formatted_time_in,
            DATE_FORMAT(sr.TIME_OUT, '%h:%i %p') as formatted_time_out,
            CASE
                WHEN sr.TIME_OUT IS NOT NULL THEN
                    TIMESTAMPDIFF(MINUTE, sr.TIME_IN, sr.TIME_OUT)
                ELSE NULL
            END as duration_minutes
        FROM SIT_IN_RECORDS sr
        JOIN USERS u ON sr.USER_IDNO = u.IDNO
        JOIN LABORATORIES l ON sr.LAB_ID = l.LAB_ID
        JOIN PURPOSES p ON sr.PURPOSE_ID = p.PURPOSE_ID
        WHERE DATE(sr.CREATED_AT) = CURDATE()
        AND sr.SESSION = 'COMPLETED'
        ORDER BY sr.CREATED_AT DESC
        """
        today_sit_ins = execute_query(today_query)

        # Format duration for each sit-in
        for sit_in in today_sit_ins:
            if sit_in['duration_minutes'] is not None:
                hours = sit_in['duration_minutes'] // 60
                minutes = sit_in['duration_minutes'] % 60
                sit_in['formatted_duration'] = f"{hours}h {minutes}m" if hours > 0 else f"{minutes}m"
            else:
                sit_in['formatted_duration'] = 'N/A'

            # Ensure time values are properly formatted
            sit_in['formatted_time_in'] = sit_in['formatted_time_in'] if sit_in['formatted_time_in'] else 'N/A'
            sit_in['formatted_time_out'] = sit_in['formatted_time_out'] if sit_in['formatted_time_out'] else 'N/A'
        
        return render_template('admin/sit_in.html', today_sit_ins=today_sit_ins)
    except Exception as e:
        print(f"Error in sit-in management: {str(e)}")
        flash('An error occurred while loading sit-in management', 'error')
        return redirect(url_for('admin.dashboard'))

@admin_bp.route('/active-sit-ins')
@login_required
@role_required('ADMIN')
def get_active_sit_ins():
    try:
        query = """
        SELECT 
            sr.RECORD_ID,
            sr.USER_IDNO,
            u.FIRSTNAME,
            u.LASTNAME,
            l.LAB_NAME,
            p.PURPOSE_NAME,
            DATE_FORMAT(sr.CREATED_AT, '%Y-%m-%d %H:%i:%s') as CREATED_AT,
            COALESCE(c.COMPUTER_NUMBER, 'Not Assigned') as COMPUTER_NUMBER
        FROM SIT_IN_RECORDS sr
        JOIN USERS u ON sr.USER_IDNO = u.IDNO
        JOIN LABORATORIES l ON sr.LAB_ID = l.LAB_ID
        JOIN PURPOSES p ON sr.PURPOSE_ID = p.PURPOSE_ID
        LEFT JOIN COMPUTERS c ON sr.COMPUTER_ID = c.COMPUTER_ID
        WHERE sr.SESSION = 'ON_GOING'
        AND DATE(sr.CREATED_AT) = CURDATE()
        ORDER BY sr.CREATED_AT DESC
        """
        sit_ins = execute_query(query)
        if sit_ins is None:
            return jsonify([])
        return jsonify(sit_ins)
    except Exception as e:
        current_app.logger.error(f"Error fetching active sit-ins: {str(e)}")
        return jsonify({'error': 'Failed to fetch active sit-ins. Please try again later.'}), 500

@admin_bp.route('/api/computers/<int:lab_id>')
@login_required
@role_required('ADMIN')
def get_available_computers(lab_id):
    try:
        query = """
        SELECT COMPUTER_ID, COMPUTER_NUMBER
        FROM COMPUTERS
        WHERE LAB_ID = %s AND STATUS = 'available'
        ORDER BY COMPUTER_NUMBER
        """
        computers = execute_query(query, (lab_id,))
        return jsonify(computers)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/start-sit-in', methods=['POST'])
@login_required
@role_required('ADMIN')
def start_sit_in():
    data = request.get_json()
    student_idno = data.get('student_idno')
    lab_id = data.get('lab_id')
    purpose_id = data.get('purpose_id')
    computer_id = data.get('computer_id')
    use_points = data.get('use_points', False)
    
    if not all([student_idno, lab_id, purpose_id, computer_id]):
        return jsonify({'success': False, 'message': 'Missing required fields'})
    
    try:
        # Get student's points and sit-in count
        student_query = """
        SELECT 
            COALESCE(sp.CURRENT_POINTS, 0) as current_points,
            COALESCE(sl.MAX_SIT_INS - sl.SIT_IN_COUNT, 0) as remaining_sessions
        FROM USERS u
        LEFT JOIN STUDENT_POINTS sp ON u.IDNO = sp.USER_IDNO
        LEFT JOIN SIT_IN_LIMITS sl ON u.IDNO = sl.USER_IDNO
        WHERE u.IDNO = %s
        """
        student_result = execute_query(student_query, (student_idno,))
        
        if not student_result:
            return jsonify({'success': False, 'message': 'Student not found'})
        
        current_points = student_result[0]['current_points']
        remaining_sessions = student_result[0]['remaining_sessions']
        
        # Check if student has enough points or remaining sessions
        if use_points:
            if current_points < 3:
                return jsonify({'success': False, 'message': 'Not enough points (3 points required)'})
        else:
            if remaining_sessions <= 0:
                return jsonify({'success': False, 'message': 'No remaining sit-in sessions'})
        
        # Check if student has an active sit-in
        active_query = """
        SELECT COUNT(*) as count
        FROM SIT_IN_RECORDS
        WHERE USER_IDNO = %s AND SESSION = 'ON_GOING'
        """
        active_result = execute_query(active_query, (student_idno,))
        
        if active_result[0]['count'] > 0:
            return jsonify({'success': False, 'message': 'Student already has an active sit-in session'})
        
        # Check if computer is available
        computer_query = """
        SELECT STATUS
        FROM COMPUTERS
        WHERE COMPUTER_ID = %s
        """
        computer_result = execute_query(computer_query, (computer_id,))
        
        if not computer_result or computer_result[0]['STATUS'] != 'available':
            return jsonify({'success': False, 'message': 'Selected computer is not available'})
        
        # Start sit-in session with current timestamp
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        insert_query = """
        INSERT INTO SIT_IN_RECORDS (
            USER_IDNO, 
            LAB_ID, 
            PURPOSE_ID, 
            COMPUTER_ID, 
            TIME_IN, 
            SESSION, 
            STATUS,
            USE_POINTS
        ) VALUES (%s, %s, %s, %s, %s, 'ON_GOING', 'APPROVED', %s)
        """
        execute_query(insert_query, (student_idno, lab_id, purpose_id, computer_id, current_time, use_points))
        
        # Update computer status
        update_computer_query = """
        UPDATE COMPUTERS
        SET STATUS = 'in_use'
        WHERE COMPUTER_ID = %s
        """
        execute_query(update_computer_query, (computer_id,))
        
        # If using points, deduct them immediately
        if use_points:
            # Deduct 3 points
            points_query = """
            UPDATE STUDENT_POINTS 
            SET CURRENT_POINTS = CURRENT_POINTS - 3
            WHERE USER_IDNO = %s
            """
            execute_query(points_query, (student_idno,))
            
            # Add to point history
            history_query = """
            INSERT INTO POINT_HISTORY (USER_IDNO, POINTS_CHANGE, REASON, ADDED_BY)
            VALUES (%s, -3, 'Points used for sit-in session', %s)
            """
            execute_query(history_query, (student_idno, session['user_id']))
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@admin_bp.route('/end-sit-in/<int:record_id>', methods=['POST'])
@login_required
@role_required('ADMIN')
def end_sit_in(record_id):
    try:
        print("\n=== Starting End Sit-in Process ===")
        data = request.get_json()
        end_option = data.get('end_option')
        print(f"End option selected: {end_option}")
        
        # Get the sit-in record
        record_query = """
        SELECT sr.USER_IDNO, sr.SESSION, sr.COMPUTER_ID, sr.USE_POINTS,
               COALESCE(sp.CURRENT_POINTS, 0) as current_points,
               COALESCE(sl.MAX_SIT_INS - sl.SIT_IN_COUNT, 0) as remaining_sessions,
               sl.SIT_IN_COUNT,
               sl.MAX_SIT_INS
        FROM SIT_IN_RECORDS sr
        LEFT JOIN STUDENT_POINTS sp ON sr.USER_IDNO = sp.USER_IDNO
        LEFT JOIN SIT_IN_LIMITS sl ON sr.USER_IDNO = sl.USER_IDNO
        WHERE sr.RECORD_ID = %s
        """
        record = execute_query(record_query, (record_id,))
        
        if not record:
            print("Error: Sit-in record not found")
            return jsonify({'success': False, 'message': 'Sit-in record not found'}), 404
        
        print("\nInitial State:")
        print(f"Student ID: {record[0]['USER_IDNO']}")
        print(f"Current Points: {record[0]['current_points']}")
        print(f"Remaining Sessions: {record[0]['remaining_sessions']}")
        print(f"Sit-in Count: {record[0]['SIT_IN_COUNT']}")
        print(f"Max Sit-ins: {record[0]['MAX_SIT_INS']}")
        
        if record[0]['SESSION'] != 'ON_GOING':
            print("Error: Session is already ended")
            return jsonify({'success': False, 'message': 'Sit-in session is already ended'}), 400
        
        current_points = record[0]['current_points']
        remaining_sessions = record[0]['remaining_sessions']
        sit_in_count = record[0]['SIT_IN_COUNT']
        max_sit_ins = record[0]['MAX_SIT_INS']
        
        if end_option in ['earn_point', 'use_session_and_point']:  # Handle both possible option values
            print("\nProcessing 'Use Session & Earn Point' option")
            
            # Check remaining sessions
            if remaining_sessions <= 0:
                print("Error: No remaining sessions available")
                return jsonify({'success': False, 'message': 'No remaining sessions available'}), 400
            
            print("Step 1: Updating sit-in count")
            # Update sit-in count
            update_count_query = """
            UPDATE SIT_IN_LIMITS
            SET SIT_IN_COUNT = SIT_IN_COUNT + 1
            WHERE USER_IDNO = %s
            """
            execute_query(update_count_query, (record[0]['USER_IDNO'],))
            print(f"Increased sit-in count by 1 (was: {sit_in_count})")
            
            print("\nStep 2: Adding point")
            # Check if student has a points record
            check_points_query = """
            SELECT COUNT(*) as count
            FROM STUDENT_POINTS
            WHERE USER_IDNO = %s
            """
            points_result = execute_query(check_points_query, (record[0]['USER_IDNO'],))
            
            if points_result[0]['count'] == 0:
                print("Creating initial points record")
                insert_points_query = """
                INSERT INTO STUDENT_POINTS (USER_IDNO, CURRENT_POINTS, TOTAL_POINTS)
                VALUES (%s, 1, 1)
                """
                execute_query(insert_points_query, (record[0]['USER_IDNO'],))
            else:
                print("Updating existing points record")
                points_query = """
                UPDATE STUDENT_POINTS 
                SET CURRENT_POINTS = CURRENT_POINTS + 1,
                    TOTAL_POINTS = TOTAL_POINTS + 1
                WHERE USER_IDNO = %s
                """
                execute_query(points_query, (record[0]['USER_IDNO'],))
            
            print("\nStep 3: Recording point history")
            history_query = """
            INSERT INTO POINT_HISTORY (USER_IDNO, POINTS_CHANGE, REASON, ADDED_BY)
            VALUES (%s, 1, 'Completed sit-in session with point reward', %s)
            """
            execute_query(history_query, (record[0]['USER_IDNO'], session['user_id']))
            
            print("\nStep 4: Checking for extra session eligibility")
            new_points = current_points + 1
            print(f"New points total: {new_points}")
            
            if new_points % 3 == 0:
                print(f"Points reached multiple of 3 ({new_points}), adding extra session")
                update_sessions_query = """
                UPDATE SIT_IN_LIMITS 
                SET SIT_IN_COUNT = SIT_IN_COUNT - 1
                WHERE USER_IDNO = %s
                """
                execute_query(update_sessions_query, (record[0]['USER_IDNO'],))
                
                history_query = """
                INSERT INTO POINT_HISTORY (USER_IDNO, POINTS_CHANGE, REASON, ADDED_BY)
                VALUES (%s, 0, 'Earned extra session for reaching %s points', %s)
                """
                execute_query(history_query, (record[0]['USER_IDNO'], new_points, session['user_id']))
                print("Extra session added")
        
        print("\nStep 5: Updating sit-in record status")
        update_query = """
        UPDATE SIT_IN_RECORDS
        SET SESSION = 'COMPLETED',
            STATUS = 'COMPLETED',
            TIME_OUT = NOW()
        WHERE RECORD_ID = %s
        """
        execute_query(update_query, (record_id,))
        
        print("\nStep 6: Updating computer status")
        update_computer_query = """
        UPDATE COMPUTERS
        SET STATUS = 'available'
        WHERE COMPUTER_ID = %s
        """
        execute_query(update_computer_query, (record[0]['COMPUTER_ID'],))
        
        print("\nStep 7: Getting updated information")
        updated_info_query = """
        SELECT 
            COALESCE(sp.CURRENT_POINTS, 0) as current_points,
            COALESCE(sl.MAX_SIT_INS - sl.SIT_IN_COUNT, 0) as remaining_sessions,
            sl.SIT_IN_COUNT as new_sit_in_count
        FROM USERS u
        LEFT JOIN STUDENT_POINTS sp ON u.IDNO = sp.USER_IDNO
        LEFT JOIN SIT_IN_LIMITS sl ON u.IDNO = sl.USER_IDNO
        WHERE u.IDNO = %s
        """
        updated_info = execute_query(updated_info_query, (record[0]['USER_IDNO'],))[0]
        
        print("\nFinal State:")
        print(f"New Current Points: {updated_info['current_points']}")
        print(f"New Remaining Sessions: {updated_info['remaining_sessions']}")
        print(f"New Sit-in Count: {updated_info['new_sit_in_count']}")
        print("=== End Sit-in Process Complete ===\n")
        
        return jsonify({
            'success': True, 
            'message': 'Sit-in session ended successfully',
            'current_points': updated_info['current_points'],
            'remaining_sessions': updated_info['remaining_sessions']
        })
    except Exception as e:
        print(f"\nERROR in end_sit_in: {str(e)}")
        print("Stack trace:")
        import traceback
        traceback.print_exc()
        print("=== End Sit-in Process Failed ===\n")
        return jsonify({'success': False, 'message': str(e)}), 500

@admin_bp.route('/sit-in-records')
@login_required
@role_required('ADMIN')
def sit_in_records():
    page = request.args.get('page', 1, type=int)
    per_page = 10
    lab_id = request.args.get('lab_id', type=int)
    purpose_id = request.args.get('purpose_id', type=int)
    
    # Build the base query
    base_query = """
    SELECT 
        sr.*,
        u.FIRSTNAME,
        u.LASTNAME,
        u.COURSE,
        u.YEAR,
        l.LAB_NAME,
        p.PURPOSE_NAME,
        DATE_FORMAT(sr.TIME_IN, '%h:%i %p') as formatted_time_in,
        DATE_FORMAT(sr.TIME_OUT, '%h:%i %p') as formatted_time_out,
        CASE
            WHEN sr.TIME_OUT IS NOT NULL THEN
                TIMESTAMPDIFF(MINUTE, sr.TIME_IN, sr.TIME_OUT)
            ELSE NULL
        END as duration_minutes
    FROM SIT_IN_RECORDS sr
    JOIN USERS u ON sr.USER_IDNO = u.IDNO
    JOIN LABORATORIES l ON sr.LAB_ID = l.LAB_ID
    JOIN PURPOSES p ON sr.PURPOSE_ID = p.PURPOSE_ID
    WHERE sr.SESSION = 'COMPLETED'
    """
    
    # Add filters if provided
    params = []
    if lab_id:
        base_query += " AND sr.LAB_ID = %s"
        params.append(lab_id)
    if purpose_id:
        base_query += " AND sr.PURPOSE_ID = %s"
        params.append(purpose_id)
    
    # Get total count with filters
    count_query = f"SELECT COUNT(*) as total FROM ({base_query}) as filtered"
    total = execute_query(count_query, tuple(params))[0]['total']
    
    # Calculate offset
    offset = (page - 1) * per_page
    
    # Add pagination and ordering
    base_query += " ORDER BY sr.CREATED_AT DESC LIMIT %s OFFSET %s"
    params.extend([per_page, offset])
    
    # Get paginated records
    records = execute_query(base_query, tuple(params))
    
    # Format duration for each record
    for record in records:
        if record['duration_minutes'] is not None:
            hours = record['duration_minutes'] // 60
            minutes = record['duration_minutes'] % 60
            record['formatted_duration'] = f"{hours}h {minutes}m" if hours > 0 else f"{minutes}m"
        else:
            record['formatted_duration'] = 'N/A'
    
    # Get all labs and purposes for filter dropdowns
    labs = execute_query("SELECT LAB_ID, LAB_NAME FROM LABORATORIES ORDER BY LAB_NAME")
    purposes = execute_query("SELECT PURPOSE_ID, PURPOSE_NAME FROM PURPOSES ORDER BY PURPOSE_NAME")
    
    # Calculate total pages
    total_pages = (total + per_page - 1) // per_page
    
    return render_template('admin/sit_in_records.html', 
                         records=records,
                         current_page=page,
                         total_pages=total_pages,
                         labs=labs,
                         purposes=purposes,
                         selected_lab=lab_id,
                         selected_purpose=purpose_id)

@admin_bp.route('/api/labs')
@login_required
@role_required('ADMIN')
def get_labs():
    try:
        query = """
        SELECT LAB_ID, LAB_NAME, STATUS
        FROM LABORATORIES
        WHERE STATUS = 'active'
        ORDER BY LAB_NAME
        """
        labs = execute_query(query)
        return jsonify(labs)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/api/purposes')
@login_required
@role_required('ADMIN')
def get_purposes():
    try:
        query = """
        SELECT PURPOSE_ID, PURPOSE_NAME, STATUS
        FROM PURPOSES
        WHERE STATUS = 'active'
        ORDER BY PURPOSE_NAME
        """
        purposes = execute_query(query)
        return jsonify(purposes)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/feedback')
@login_required
@role_required('ADMIN')
def view_feedback():
    page = request.args.get('page', 1, type=int)
    per_page = 10
    
    # Get filter parameters
    student = request.args.get('student', '')
    lab_id = request.args.get('lab', '')
    rating = request.args.get('rating', '')
    date = request.args.get('date', '')
    
    # Build query conditions
    conditions = []
    params = []
    
    if student:
        conditions.append("CONCAT(u.FIRSTNAME, ' ', u.LASTNAME) LIKE %s")
        params.append(f"%{student}%")
    
    if lab_id:
        conditions.append("sr.LAB_ID = %s")
        params.append(lab_id)
    
    if rating:
        conditions.append("f.RATING = %s")
        params.append(rating)
    
    if date:
        conditions.append("DATE(sr.CREATED_AT) = %s")
        params.append(date)
    
    where_clause = " AND ".join(conditions) if conditions else "1=1"
    
    # Get total count
    count_query = f"""
    SELECT COUNT(*) as total
    FROM FEEDBACKS f
    JOIN SIT_IN_RECORDS sr ON f.RECORD_ID = sr.RECORD_ID
    JOIN USERS u ON f.USER_IDNO = u.IDNO
    JOIN LABORATORIES l ON sr.LAB_ID = l.LAB_ID
    JOIN PURPOSES p ON sr.PURPOSE_ID = p.PURPOSE_ID
    WHERE {where_clause}
    """
    total = execute_query(count_query, tuple(params))[0]['total']
    
    # Calculate offset
    offset = (page - 1) * per_page
    
    # Get paginated feedbacks
    query = f"""
    SELECT 
        f.*,
        CONCAT(u.FIRSTNAME, ' ', u.LASTNAME) as STUDENT_NAME,
        l.LAB_NAME,
        p.PURPOSE_NAME,
        DATE_FORMAT(sr.CREATED_AT, '%Y-%m-%d %H:%i') as SIT_IN_DATE
    FROM FEEDBACKS f
    JOIN SIT_IN_RECORDS sr ON f.RECORD_ID = sr.RECORD_ID
    JOIN USERS u ON f.USER_IDNO = u.IDNO
    JOIN LABORATORIES l ON sr.LAB_ID = l.LAB_ID
    JOIN PURPOSES p ON sr.PURPOSE_ID = p.PURPOSE_ID
    WHERE {where_clause}
    ORDER BY f.CREATED_AT DESC
    LIMIT %s OFFSET %s
    """
    feedbacks = execute_query(query, tuple(params + [per_page, offset]))
    
    # Get labs for filter
    labs_query = "SELECT * FROM LABORATORIES WHERE STATUS = 'active' ORDER BY LAB_NAME"
    labs = execute_query(labs_query)
    
    # Calculate total pages
    total_pages = (total + per_page - 1) // per_page
    
    return render_template('admin/feedback.html',
                         feedbacks=feedbacks,
                         labs=labs,
                         page=page,
                         total_pages=total_pages)

@admin_bp.route('/download_report/<report_type>/<format>')
@login_required
@role_required('ADMIN')
def download_report(report_type, format):
    try:
        if report_type == 'lab_usage':
            query = """
                SELECT l.LAB_NAME AS lab_name, COUNT(s.RECORD_ID) as usage_count
                FROM LABORATORIES l
                LEFT JOIN SIT_IN_RECORDS s ON l.LAB_ID = s.LAB_ID
                WHERE s.SESSION = 'COMPLETED'
                GROUP BY l.LAB_NAME
                ORDER BY usage_count DESC
            """
            headers = ['Lab Name', 'Usage Count']
            filename = 'lab_usage_report'
            
        elif report_type == 'purpose_usage':
            query = """
                SELECT p.PURPOSE_NAME AS purpose_name, COUNT(s.RECORD_ID) as usage_count
                FROM PURPOSES p
                LEFT JOIN SIT_IN_RECORDS s ON p.PURPOSE_ID = s.PURPOSE_ID
                WHERE s.SESSION = 'COMPLETED'
                GROUP BY p.PURPOSE_NAME
                ORDER BY usage_count DESC
            """
            headers = ['Purpose', 'Usage Count']
            filename = 'purpose_usage_report'
            
        elif report_type == 'sit_ins':
            query = """
                SELECT 
                    sr.RECORD_ID as record_id,
                    CONCAT(u.FIRSTNAME, ' ', u.LASTNAME) as student_name,
                    u.COURSE as course,
                    u.YEAR as year,
                    l.LAB_NAME as lab,
                    p.PURPOSE_NAME as purpose,
                    DATE_FORMAT(sr.DATE, '%Y-%m-%d') as date,
                    DATE_FORMAT(sr.TIME_IN, '%h:%i %p') as time_in,
                    DATE_FORMAT(sr.TIME_OUT, '%h:%i %p') as time_out,
                    sr.STATUS as status,
                    sr.SESSION as session
                FROM SIT_IN_RECORDS sr
                JOIN USERS u ON sr.USER_IDNO = u.IDNO
                JOIN LABORATORIES l ON sr.LAB_ID = l.LAB_ID
                JOIN PURPOSES p ON sr.PURPOSE_ID = p.PURPOSE_ID
                WHERE sr.SESSION = 'COMPLETED'
                ORDER BY sr.CREATED_AT DESC
            """
            headers = ['Record ID', 'Student Name', 'Course', 'Year', 'Lab', 'Purpose', 'Date', 'Time In', 'Time Out', 'Status', 'Session']
            filename = 'sit_in_records_report'
            
        elif report_type == 'feedback':
            query = """
                SELECT 
                    CONCAT(u.FIRSTNAME, ' ', u.LASTNAME) as student_name,
                    l.LAB_NAME as lab_name,
                    p.PURPOSE_NAME as purpose_name,
                    f.RATING as rating,
                    f.COMMENT as comment,
                    DATE_FORMAT(sr.CREATED_AT, '%Y-%m-%d %H:%i') as sit_in_date
                FROM FEEDBACKS f
                JOIN SIT_IN_RECORDS sr ON f.RECORD_ID = sr.RECORD_ID
                JOIN USERS u ON f.USER_IDNO = u.IDNO
                JOIN LABORATORIES l ON sr.LAB_ID = l.LAB_ID
                JOIN PURPOSES p ON sr.PURPOSE_ID = p.PURPOSE_ID
                WHERE sr.SESSION = 'COMPLETED'
                ORDER BY sr.CREATED_AT DESC
            """
            headers = ['Student Name', 'Lab', 'Purpose', 'Rating', 'Comment', 'Date']
            filename = 'feedback_report'
            
        else:
            return jsonify({'error': 'Invalid report type'}), 400
        
        data = execute_query(query)
        
        if format == 'csv':
            return generate_csv_report(data, headers, filename)
        elif format == 'pdf':
            return generate_pdf_report(data, headers, filename)
        elif format == 'excel':
            return generate_excel_report(data, headers, filename)
        else:
            return jsonify({'error': 'Invalid format'}), 400
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def generate_csv_report(data, headers, title):
    output = StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow(['University of Cebu Main Campus'])
    writer.writerow(['College of Computer Studies'])
    writer.writerow(['Computer Laboratory Sit-In Monitoring System'])
    
    # Add report title with filters if available
    if isinstance(title, str):
        report_title = title.replace('_', ' ').title()
        if 'lab_usage' in title:
            report_title = 'Laboratory Usage Report'
        elif 'purpose_usage' in title:
            report_title = 'Purpose Usage Statistics Report'
        elif 'sit_in' in title:
            report_title = 'Sit-In Records Report'
            # Add filter information if available
            filters = []
            if request.args.get('lab_id'):
                lab_name = execute_query("SELECT LAB_NAME FROM LABORATORIES WHERE LAB_ID = %s", 
                                      (request.args.get('lab_id'),))[0]['LAB_NAME']
                filters.append(f"Lab: {lab_name}")
            if request.args.get('purpose_id'):
                purpose_name = execute_query("SELECT PURPOSE_NAME FROM PURPOSES WHERE PURPOSE_ID = %s",
                                          (request.args.get('purpose_id'),))[0]['PURPOSE_NAME']
                filters.append(f"Purpose: {purpose_name}")
            if request.args.get('start_date'):
                filters.append(f"From: {request.args.get('start_date')}")
            if request.args.get('end_date'):
                filters.append(f"To: {request.args.get('end_date')}")
            if filters:
                report_title += f" ({' | '.join(filters)})"
        elif 'feedback' in title:
            report_title = 'Student Feedback Report'
            # Add filter information if available
            filters = []
            if request.args.get('lab'):
                lab_name = execute_query("SELECT LAB_NAME FROM LABORATORIES WHERE LAB_ID = %s",
                                      (request.args.get('lab'),))[0]['LAB_NAME']
                filters.append(f"Lab: {lab_name}")
            if request.args.get('rating'):
                filters.append(f"Rating: {request.args.get('rating')} stars")
            if request.args.get('date'):
                filters.append(f"Date: {request.args.get('date')}")
            if filters:
                report_title += f" ({' | '.join(filters)})"
    
    writer.writerow([report_title])
    
    # Add generation date
    current_datetime = datetime.now().strftime("%B %d, %Y %I:%M %p")
    writer.writerow([f'Generated on: {current_datetime}'])
    writer.writerow([])  # Empty row for spacing
    
    # Write column headers
    writer.writerow(headers)
    
    # Write data
    for row in data:
        writer.writerow([str(row.get(header.lower().replace(' ', '_'), '')) for header in headers])
    
    # Add summary if applicable
    if data:
        writer.writerow([])  # Empty row for spacing
        if 'lab_usage' in title:
            total_usage = sum(row.get('usage_count', 0) for row in data)
            writer.writerow([f'Total Laboratory Usage: {total_usage} sessions'])
        elif 'purpose_usage' in title:
            total_usage = sum(row.get('usage_count', 0) for row in data)
            writer.writerow([f'Total Purpose Usage: {total_usage} sessions'])
        elif 'feedback' in title:
            avg_rating = sum(row.get('rating', 0) for row in data) / len(data)
            writer.writerow([f'Average Rating: {avg_rating:.2f} stars'])
    
    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename={title.lower().replace(" ", "_")}.csv'}
    )

def generate_pdf_report(data, headers, title):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=50, bottomMargin=50)
    elements = []
    
    # Styles
    styles = getSampleStyleSheet()
    header_style = ParagraphStyle(
        'CustomHeader',
        parent=styles['Heading1'],
        fontSize=16,
        spaceAfter=10,
        alignment=1,  # Center alignment
        textColor=colors.HexColor('#4e73df')  # Primary blue color
    )
    
    subheader_style = ParagraphStyle(
        'SubHeader',
        parent=styles['Heading2'],
        fontSize=12,
        spaceAfter=20,
        alignment=1,
        textColor=colors.HexColor('#5a5c69')  # Secondary gray color
    )
    
    # Get current date and time
    current_datetime = datetime.now().strftime("%B %d, %Y %I:%M %p")
    
    # Add header
    elements.append(Paragraph('University of Cebu Main Campus', header_style))
    elements.append(Paragraph('College of Computer Studies', header_style))
    elements.append(Paragraph('Computer Laboratory Sit-In Monitoring System', header_style))
    
    # Add report title with filters if available
    if isinstance(title, str):
        report_title = title.replace('_', ' ').title()
        if 'lab_usage' in title:
            report_title = 'Laboratory Usage Report'
        elif 'purpose_usage' in title:
            report_title = 'Purpose Usage Statistics Report'
        elif 'sit_in' in title:
            report_title = 'Sit-In Records Report'
            # Add filter information if available
            filters = []
            if request.args.get('lab_id'):
                lab_name = execute_query("SELECT LAB_NAME FROM LABORATORIES WHERE LAB_ID = %s", 
                                      (request.args.get('lab_id'),))[0]['LAB_NAME']
                filters.append(f"Lab: {lab_name}")
            if request.args.get('purpose_id'):
                purpose_name = execute_query("SELECT PURPOSE_NAME FROM PURPOSES WHERE PURPOSE_ID = %s",
                                          (request.args.get('purpose_id'),))[0]['PURPOSE_NAME']
                filters.append(f"Purpose: {purpose_name}")
            if request.args.get('start_date'):
                filters.append(f"From: {request.args.get('start_date')}")
            if request.args.get('end_date'):
                filters.append(f"To: {request.args.get('end_date')}")
            if filters:
                report_title += f"\n({' | '.join(filters)})"
        elif 'feedback' in title:
            report_title = 'Student Feedback Report'
            # Add filter information if available
            filters = []
            if request.args.get('lab'):
                lab_name = execute_query("SELECT LAB_NAME FROM LABORATORIES WHERE LAB_ID = %s",
                                      (request.args.get('lab'),))[0]['LAB_NAME']
                filters.append(f"Lab: {lab_name}")
            if request.args.get('rating'):
                filters.append(f"Rating: {request.args.get('rating')} stars")
            if request.args.get('date'):
                filters.append(f"Date: {request.args.get('date')}")
            if filters:
                report_title += f"\n({' | '.join(filters)})"
    
    elements.append(Paragraph(report_title, header_style))
    elements.append(Paragraph(f'Generated on: {current_datetime}', subheader_style))
    elements.append(Spacer(1, 20))
    
    # Create table
    table_data = [headers]
    for row in data:
        table_data.append([str(row.get(header.lower().replace(' ', '_'), '')) for header in headers])
    
    # Calculate column widths based on content
    col_widths = []
    for i in range(len(headers)):
        max_width = max(
            [len(str(row[i])) * 7 for row in table_data] + [len(headers[i]) * 7]
        )
        col_widths.append(min(max_width, 200))  # Cap at 200 points
    
    table = Table(table_data, colWidths=col_widths)
    table.setStyle(TableStyle([
        # Header style
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4e73df')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('TOPPADDING', (0, 0), (-1, 0), 12),
        
        # Data rows style
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('ALIGN', (0, 1), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e3e6f0')),
        
        # Alternating row colors
        *[('BACKGROUND', (0, i), (-1, i), colors.HexColor('#f8f9fc'))
          for i in range(2, len(table_data), 2)],
        
        # Cell padding
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        
        # Word wrap
        ('WORDWRAP', (0, 0), (-1, -1), True),
    ]))
    
    elements.append(table)
    
    # Add summary if applicable
    if data:
        elements.append(Spacer(1, 20))
        if 'lab_usage' in title:
            total_usage = sum(row.get('usage_count', 0) for row in data)
            summary = f'Total Laboratory Usage: {total_usage} sessions'
            elements.append(Paragraph(summary, subheader_style))
        elif 'purpose_usage' in title:
            total_usage = sum(row.get('usage_count', 0) for row in data)
            summary = f'Total Purpose Usage: {total_usage} sessions'
            elements.append(Paragraph(summary, subheader_style))
        elif 'feedback' in title:
            avg_rating = sum(row.get('rating', 0) for row in data) / len(data)
            summary = f'Average Rating: {avg_rating:.2f} stars'
            elements.append(Paragraph(summary, subheader_style))
    
    doc.build(elements)
    buffer.seek(0)
    return Response(
        buffer.getvalue(),
        mimetype='application/pdf',
        headers={'Content-Disposition': f'attachment; filename={title.lower().replace(" ", "_")}.pdf'}
    )

def generate_excel_report(data, headers, title):
    output = BytesIO()
    workbook = xlsxwriter.Workbook(output)
    worksheet = workbook.add_worksheet()
    
    # Define formats
    title_format = workbook.add_format({
        'bold': True,
        'font_size': 16,
        'align': 'center',
        'valign': 'vcenter',
        'font_color': '#4e73df'
    })
    
    subtitle_format = workbook.add_format({
        'bold': True,
        'font_size': 12,
        'align': 'center',
        'valign': 'vcenter',
        'font_color': '#5a5c69'
    })
    
    header_format = workbook.add_format({
        'bold': True,
        'bg_color': '#4e73df',
        'font_color': 'white',
        'border': 1,
        'border_color': '#e3e6f0',
        'align': 'center',
        'valign': 'vcenter',
        'text_wrap': True
    })
    
    data_format = workbook.add_format({
        'border': 1,
        'border_color': '#e3e6f0',
        'align': 'center',
        'valign': 'vcenter',
        'text_wrap': True
    })
    
    alt_row_format = workbook.add_format({
        'border': 1,
        'border_color': '#e3e6f0',
        'align': 'center',
        'valign': 'vcenter',
        'bg_color': '#f8f9fc',
        'text_wrap': True
    })
    
    # Add header
    worksheet.merge_range('A1:H1', 'University of Cebu Main Campus', title_format)
    worksheet.merge_range('A2:H2', 'College of Computer Studies', title_format)
    worksheet.merge_range('A3:H3', 'Computer Laboratory Sit-In Monitoring System', title_format)
    
    # Add report title with filters if available
    if isinstance(title, str):
        report_title = title.replace('_', ' ').title()
        if 'lab_usage' in title:
            report_title = 'Laboratory Usage Report'
        elif 'purpose_usage' in title:
            report_title = 'Purpose Usage Statistics Report'
        elif 'sit_in' in title:
            report_title = 'Sit-In Records Report'
            # Add filter information if available
            filters = []
            if request.args.get('lab_id'):
                lab_name = execute_query("SELECT LAB_NAME FROM LABORATORIES WHERE LAB_ID = %s", 
                                      (request.args.get('lab_id'),))[0]['LAB_NAME']
                filters.append(f"Lab: {lab_name}")
            if request.args.get('purpose_id'):
                purpose_name = execute_query("SELECT PURPOSE_NAME FROM PURPOSES WHERE PURPOSE_ID = %s",
                                          (request.args.get('purpose_id'),))[0]['PURPOSE_NAME']
                filters.append(f"Purpose: {purpose_name}")
            if request.args.get('start_date'):
                filters.append(f"From: {request.args.get('start_date')}")
            if request.args.get('end_date'):
                filters.append(f"To: {request.args.get('end_date')}")
            if filters:
                report_title += f" ({' | '.join(filters)})"
        elif 'feedback' in title:
            report_title = 'Student Feedback Report'
            # Add filter information if available
            filters = []
            if request.args.get('lab'):
                lab_name = execute_query("SELECT LAB_NAME FROM LABORATORIES WHERE LAB_ID = %s",
                                      (request.args.get('lab'),))[0]['LAB_NAME']
                filters.append(f"Lab: {lab_name}")
            if request.args.get('rating'):
                filters.append(f"Rating: {request.args.get('rating')} stars")
            if request.args.get('date'):
                filters.append(f"Date: {request.args.get('date')}")
            if filters:
                report_title += f" ({' | '.join(filters)})"
    
    worksheet.merge_range('A4:H4', report_title, title_format)
    
    # Add generation date
    current_datetime = datetime.now().strftime("%B %d, %Y %I:%M %p")
    worksheet.merge_range('A5:H5', f'Generated on: {current_datetime}', subtitle_format)
    
    # Add column headers
    for col, header in enumerate(headers):
        worksheet.write(6, col, header, header_format)
    
    # Add data with alternating row colors
    for row, data_row in enumerate(data, start=7):
        row_format = alt_row_format if row % 2 == 0 else data_format
        for col, header in enumerate(headers):
            value = str(data_row.get(header.lower().replace(' ', '_'), ''))
            worksheet.write(row, col, value, row_format)
    
    # Add summary if applicable
    if data:
        summary_row = len(data) + 8
        if 'lab_usage' in title:
            total_usage = sum(row.get('usage_count', 0) for row in data)
            worksheet.merge_range(f'A{summary_row}:H{summary_row}', 
                               f'Total Laboratory Usage: {total_usage} sessions', 
                               subtitle_format)
        elif 'purpose_usage' in title:
            total_usage = sum(row.get('usage_count', 0) for row in data)
            worksheet.merge_range(f'A{summary_row}:H{summary_row}', 
                               f'Total Purpose Usage: {total_usage} sessions', 
                               subtitle_format)
        elif 'feedback' in title:
            avg_rating = sum(row.get('rating', 0) for row in data) / len(data)
            worksheet.merge_range(f'A{summary_row}:H{summary_row}', 
                               f'Average Rating: {avg_rating:.2f} stars', 
                               subtitle_format)
    
    # Adjust column widths
    for col, header in enumerate(headers):
        max_length = len(header)
        for row in range(len(data)):
            cell_value = str(data[row].get(header.lower().replace(' ', '_'), ''))
            max_length = max(max_length, len(cell_value))
        worksheet.set_column(col, col, min(max_length + 2, 30))  # Cap width at 30
    
    workbook.close()
    output.seek(0)
    
    return Response(
        output.getvalue(),
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers={'Content-Disposition': f'attachment; filename={title.lower().replace(" ", "_")}.xlsx'}
    )

@admin_bp.route('/api/announcements')
@login_required
def get_announcements():
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        
        # Get total count
        count_query = "SELECT COUNT(*) as total FROM ANNOUNCEMENTS WHERE STATUS = 'active'"
        total = execute_query(count_query)[0]['total']
        
        # Calculate offset
        offset = (page - 1) * per_page
        
        # Get paginated announcements
        query = """
        SELECT 
            a.ANNOUNCEMENT_ID,
            a.TITLE,
            a.CONTENT,
            a.DATE_POSTED,
            u.FIRSTNAME,
            u.LASTNAME
        FROM ANNOUNCEMENTS a
        JOIN USERS u ON a.POSTED_BY = u.IDNO
        WHERE a.STATUS = 'active'
        ORDER BY a.DATE_POSTED DESC
        LIMIT %s OFFSET %s
        """
        announcements = execute_query(query, (per_page, offset))
        
        return jsonify({
            'announcements': announcements,
            'total': total,
            'page': page,
            'per_page': per_page
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/resources', methods=['GET', 'POST'])
@login_required
@role_required('ADMIN')
def manage_resources():
    if request.method == 'POST':
        try:
            title = request.form.get('title')
            context = request.form.get('context')
            resource_type = request.form.get('resource_type')
            purpose_id = request.form.get('purpose_id')
            
            if not title or not resource_type or not purpose_id:
                return jsonify({'error': 'Missing required fields'}), 400
            
            # Handle file upload
            if resource_type == 'file':
                if 'file' not in request.files:
                    return jsonify({'error': 'No file uploaded'}), 400
                
                file = request.files['file']
                if file.filename == '':
                    return jsonify({'error': 'No file selected'}), 400
                
                # Save file and get path
                filename = secure_filename(file.filename)
                file_path = os.path.join('static', 'resources', filename)
                file.save(file_path)
                resource_value = file_path
            else:
                resource_value = request.form.get('resource_value')
                if not resource_value:
                    return jsonify({'error': 'Resource value is required'}), 400
            
            # Insert resource
            query = """
            INSERT INTO LAB_RESOURCES (TITLE, CONTEXT, RESOURCE_TYPE, RESOURCE_VALUE, PURPOSE_ID, CREATED_BY)
            VALUES (%s, %s, %s, %s, %s, %s)
            """
            resource_id = execute_query(query, (title, context, resource_type, resource_value, purpose_id, session['user_id']))
            
            return jsonify({'success': True, 'message': 'Resource added successfully'})
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    # Get all resources with their purposes
    query = """
    SELECT 
        r.*,
        p.PURPOSE_NAME,
        CONCAT(u.FIRSTNAME, ' ', u.LASTNAME) as CREATED_BY
    FROM LAB_RESOURCES r
    JOIN PURPOSES p ON r.PURPOSE_ID = p.PURPOSE_ID
    LEFT JOIN USERS u ON r.CREATED_BY = u.IDNO
    ORDER BY r.CREATED_AT DESC
    """
    resources = execute_query(query)
    
    # Get all purposes for the form
    purposes = execute_query("SELECT * FROM PURPOSES WHERE STATUS = 'active' ORDER BY PURPOSE_NAME")
    
    return render_template('admin/resources.html', resources=resources, purposes=purposes)

@admin_bp.route('/resources/<int:resource_id>')
@login_required
@role_required('ADMIN')
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
    WHERE r.RESOURCE_ID = %s
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
        'purpose_id': resource['PURPOSE_ID'],
        'purpose_name': resource['PURPOSE_NAME'],
        'created_by': resource['CREATED_BY'],
        'created_at': resource['CREATED_AT'].strftime('%Y-%m-%d %H:%M:%S'),
        'enabled': resource['ENABLED']
    })

@admin_bp.route('/resources/add', methods=['POST'])
@login_required
@role_required('ADMIN')
def add_resource():
    try:
        title = request.form.get('title')
        context = request.form.get('context')
        resource_type = request.form.get('resource_type')
        purpose_id = request.form.get('purpose_id')
        
        if not title or not resource_type or not purpose_id:
            return jsonify({'error': 'Missing required fields'}), 400
        
        # Handle file upload
        if resource_type == 'file':
            if 'file' not in request.files:
                return jsonify({'error': 'No file uploaded'}), 400
            
            file = request.files['file']
            if file.filename == '':
                return jsonify({'error': 'No file selected'}), 400
            
            # Create resources directory if it doesn't exist
            resources_dir = os.path.join('static', 'resources')
            if not os.path.exists(resources_dir):
                os.makedirs(resources_dir)
            
            # Save file and get path
            filename = secure_filename(file.filename)
            file_path = os.path.join(resources_dir, filename)
            file.save(file_path)
            resource_value = file_path
        else:
            resource_value = request.form.get('resource_value')
            if not resource_value:
                return jsonify({'error': 'Resource value is required'}), 400
        
        # Insert resource
        query = """
        INSERT INTO LAB_RESOURCES (TITLE, CONTEXT, RESOURCE_TYPE, RESOURCE_VALUE, PURPOSE_ID, CREATED_BY)
        VALUES (%s, %s, %s, %s, %s, %s)
        """
        resource_id = execute_query(query, (title, context, resource_type, resource_value, purpose_id, session['user_id']))
        
        return jsonify({'success': True, 'message': 'Resource added successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/resources/<int:resource_id>/delete', methods=['POST'])
@login_required
@role_required('ADMIN')
def delete_resource(resource_id):
    try:
        # Get resource details
        query = "SELECT * FROM LAB_RESOURCES WHERE RESOURCE_ID = %s"
        resource = execute_query(query, (resource_id,))
        
        if not resource:
            return jsonify({'error': 'Resource not found'}), 404
        
        resource = resource[0]
        
        # Delete file if exists
        if resource['RESOURCE_TYPE'] == 'file':
            file_path = resource['RESOURCE_VALUE']
            if os.path.exists(file_path):
                os.remove(file_path)
        
        # Delete resource
        execute_query("DELETE FROM LAB_RESOURCES WHERE RESOURCE_ID = %s", (resource_id,))
        
        return jsonify({'success': True, 'message': 'Resource deleted successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/resources/toggle/<int:resource_id>', methods=['POST'])
@login_required
@role_required('ADMIN')
def toggle_resource(resource_id):
    resource = execute_query("SELECT ENABLED FROM LAB_RESOURCES WHERE RESOURCE_ID=%s", (resource_id,))[0]
    new_status = not resource['ENABLED']
    execute_query("UPDATE LAB_RESOURCES SET ENABLED=%s WHERE RESOURCE_ID=%s", (new_status, resource_id))
    return redirect(url_for('admin.manage_resources')) 

@admin_bp.route('/top-participants')
@login_required
@role_required('ADMIN')
def top_participants():
    # Get top 5 participants
    top_query = """
    SELECT 
        u.IDNO, u.FIRSTNAME, u.LASTNAME, u.COURSE,
        sp.CURRENT_POINTS, sp.TOTAL_POINTS, sp.LAST_UPDATED
    FROM USERS u
    JOIN STUDENT_POINTS sp ON u.IDNO = sp.USER_IDNO
    WHERE u.USER_TYPE = 'STUDENT'
    ORDER BY sp.CURRENT_POINTS DESC
    LIMIT 5
    """
    top_participants = execute_query(top_query)

    # Get all participants
    all_query = """
    SELECT 
        u.IDNO, u.FIRSTNAME, u.LASTNAME, u.COURSE,
        sp.CURRENT_POINTS, sp.TOTAL_POINTS, sp.LAST_UPDATED
    FROM USERS u
    JOIN STUDENT_POINTS sp ON u.IDNO = sp.USER_IDNO
    WHERE u.USER_TYPE = 'STUDENT'
    ORDER BY sp.CURRENT_POINTS DESC
    """
    all_participants = execute_query(all_query)

    return render_template('admin/top_participants.html', 
                         top_participants=top_participants,
                         all_participants=all_participants)

@admin_bp.route('/point-history/<student_id>')
@login_required
@role_required('ADMIN')
def point_history(student_id):
    query = """
    SELECT 
        ph.*,
        CONCAT(u.FIRSTNAME, ' ', u.LASTNAME) as ADDED_BY_NAME
    FROM POINT_HISTORY ph
    JOIN USERS u ON ph.ADDED_BY = u.IDNO
    WHERE ph.USER_IDNO = %s
    ORDER BY ph.CREATED_AT DESC
    """
    history = execute_query(query, (student_id,))
    return jsonify({'history': history})

@admin_bp.route('/add-points', methods=['POST'])
@login_required
@role_required('ADMIN')
def add_points():
    try:
        data = request.get_json()
        student_id = data.get('student_id')
        points = data.get('points', 1)  # Default to 1 point if not specified
        reason = data.get('reason')
        record_id = data.get('record_id')

        if not all([student_id, reason]):
            return jsonify({'error': 'Missing required fields'}), 400

        # Update student points
        update_query = """
        UPDATE STUDENT_POINTS 
        SET CURRENT_POINTS = CURRENT_POINTS + %s,
            TOTAL_POINTS = TOTAL_POINTS + %s
        WHERE USER_IDNO = %s
        """
        execute_query(update_query, (points, points, student_id))

        # Add to point history
        history_query = """
        INSERT INTO POINT_HISTORY (USER_IDNO, POINTS_CHANGE, REASON, ADDED_BY)
        VALUES (%s, %s, %s, %s)
        """
        execute_query(history_query, (student_id, points, reason, session['user_id']))

        # If record_id is provided, add to point redemptions
        if record_id:
            redemption_query = """
            INSERT INTO POINT_REDEMPTIONS (USER_IDNO, SIT_IN_RECORD_ID, POINTS_USED)
            VALUES (%s, %s, %s)
            """
            execute_query(redemption_query, (student_id, record_id, points))

        return jsonify({'success': True, 'message': 'Points added successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/use-points', methods=['POST'])
@login_required
@role_required('ADMIN')
def use_points():
    try:
        data = request.get_json()
        student_id = data.get('student_id')
        sit_in_id = data.get('sit_in_id')
        points = data.get('points')

        if not all([student_id, sit_in_id, points]):
            return jsonify({'error': 'Missing required fields'}), 400

        # Check if student has enough points
        check_query = "SELECT CURRENT_POINTS FROM STUDENT_POINTS WHERE USER_IDNO = %s"
        result = execute_query(check_query, (student_id,))
        
        if not result or result[0]['CURRENT_POINTS'] < points:
            return jsonify({'error': 'Not enough points'}), 400

        # Update student points
        update_query = """
        UPDATE STUDENT_POINTS 
        SET CURRENT_POINTS = CURRENT_POINTS - %s
        WHERE USER_IDNO = %s
        """
        execute_query(update_query, (points, student_id))

        # Add to point history
        history_query = """
        INSERT INTO POINT_HISTORY (USER_IDNO, POINTS_CHANGE, REASON, ADDED_BY)
        VALUES (%s, %s, %s, %s)
        """
        execute_query(history_query, (student_id, -points, 'Points used for sit-in', session['user_id']))

        # Add to point redemptions
        redemption_query = """
        INSERT INTO POINT_REDEMPTIONS (USER_IDNO, SIT_IN_RECORD_ID, POINTS_USED)
        VALUES (%s, %s, %s)
        """
        execute_query(redemption_query, (student_id, sit_in_id, points))

        return jsonify({'success': True, 'message': 'Points used successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/lab-schedules')
@login_required
def lab_schedules():
    if session.get('user_type') not in ['ADMIN', 'STAFF']:
        return redirect(url_for('auth.login'))
        
    # Get all active laboratories
    labs = execute_query("SELECT * FROM LABORATORIES WHERE STATUS = 'active'")
    
    # Get all active purposes
    purposes = execute_query("SELECT * FROM PURPOSES WHERE STATUS = 'active'")
    
    # Get all active professors
    professors = execute_query("SELECT * FROM PROFESSORS WHERE STATUS = 'active' ORDER BY LAST_NAME, FIRST_NAME")
        
    # Get all schedules with lab and purpose names
    schedules = execute_query("""
        SELECT ls.*, l.LAB_NAME, p.PURPOSE_NAME, 
               CONCAT(prof.LAST_NAME, ', ', prof.FIRST_NAME, ' ', COALESCE(prof.MIDDLE_NAME, '')) as PROFESSOR_NAME
        FROM LAB_SCHEDULES ls
        JOIN LABORATORIES l ON ls.LAB_ID = l.LAB_ID
        JOIN PURPOSES p ON ls.PURPOSE_ID = p.PURPOSE_ID
        JOIN PROFESSORS prof ON ls.PROFESSOR_ID = prof.PROFESSOR_ID
        ORDER BY ls.DAY_OF_WEEK, ls.START_TIME
    """)
    
    return render_template('admin/lab_schedules.html', 
                         labs=labs, 
                         purposes=purposes, 
                         professors=professors,
                         schedules=schedules)

@admin_bp.route('/lab-schedules/add', methods=['POST'])
@login_required
def add_lab_schedule():
    if session.get('user_type') not in ['ADMIN', 'STAFF']:
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.get_json()
    
    # Validate required fields
    required_fields = ['lab_id', 'purpose_id', 'professor_id', 'day', 'start_time', 'end_time']
    for field in required_fields:
        if field not in data:
            return jsonify({'error': f'Missing required field: {field}'}), 400
    
    # Check for schedule conflicts
    conflict_check = execute_query("""
        SELECT ls.*, l.LAB_NAME, p.PURPOSE_NAME, CONCAT(pr.FIRST_NAME, ' ', pr.LAST_NAME) as PROFESSOR_NAME
        FROM LAB_SCHEDULES ls
        JOIN LABORATORIES l ON ls.LAB_ID = l.LAB_ID
        JOIN PURPOSES p ON ls.PURPOSE_ID = p.PURPOSE_ID
        JOIN PROFESSORS pr ON ls.PROFESSOR_ID = pr.PROFESSOR_ID
        WHERE ls.LAB_ID = %s
        AND ls.DAY_OF_WEEK = %s
        AND (
            (ls.START_TIME <= %s AND ls.END_TIME > %s)
            OR (ls.START_TIME < %s AND ls.END_TIME >= %s)
            OR (ls.START_TIME >= %s AND ls.END_TIME <= %s)
        )
    """, (data['lab_id'], data['day'], data['start_time'], data['start_time'], 
          data['end_time'], data['end_time'], data['start_time'], data['end_time']))
    
    if conflict_check and len(conflict_check) > 0:
        conflicting_schedule = conflict_check[0]
        return jsonify({
            'error': 'Schedule conflict',
            'conflicting_schedule': {
                'lab_name': conflicting_schedule['LAB_NAME'],
                'purpose': conflicting_schedule['PURPOSE_NAME'],
                'professor': conflicting_schedule['PROFESSOR_NAME'],
                'day': conflicting_schedule['DAY_OF_WEEK'],
                'start_time': str(conflicting_schedule['START_TIME']),
                'end_time': str(conflicting_schedule['END_TIME'])
            }
        }), 400
    
    # Check for professor schedule conflicts
    professor_conflict = execute_query("""
        SELECT ls.*, l.LAB_NAME, p.PURPOSE_NAME, CONCAT(pr.FIRST_NAME, ' ', pr.LAST_NAME) as PROFESSOR_NAME
        FROM LAB_SCHEDULES ls
        JOIN LABORATORIES l ON ls.LAB_ID = l.LAB_ID
        JOIN PURPOSES p ON ls.PURPOSE_ID = p.PURPOSE_ID
        JOIN PROFESSORS pr ON ls.PROFESSOR_ID = pr.PROFESSOR_ID
        WHERE ls.PROFESSOR_ID = %s
        AND ls.DAY_OF_WEEK = %s
        AND (
            (ls.START_TIME <= %s AND ls.END_TIME > %s)
            OR (ls.START_TIME < %s AND ls.END_TIME >= %s)
            OR (ls.START_TIME >= %s AND ls.END_TIME <= %s)
        )
    """, (data['professor_id'], data['day'], data['start_time'], data['start_time'],
          data['end_time'], data['end_time'], data['start_time'], data['end_time']))
        
    if professor_conflict and len(professor_conflict) > 0:
        conflicting_schedule = professor_conflict[0]
        return jsonify({
            'error': 'Professor schedule conflict',
            'conflicting_schedule': {
                'lab_name': conflicting_schedule['LAB_NAME'],
                'purpose': conflicting_schedule['PURPOSE_NAME'],
                'professor': conflicting_schedule['PROFESSOR_NAME'],
                'day': conflicting_schedule['DAY_OF_WEEK'],
                'start_time': str(conflicting_schedule['START_TIME']),
                'end_time': str(conflicting_schedule['END_TIME'])
            }
        }), 400
    
    # Insert new schedule
    result = execute_query("""
        INSERT INTO LAB_SCHEDULES 
        (LAB_ID, PURPOSE_ID, PROFESSOR_ID, DAY_OF_WEEK, START_TIME, END_TIME, STATUS)
        VALUES (%s, %s, %s, %s, %s, %s, 'active')
    """, (data['lab_id'], data['purpose_id'], data['professor_id'], 
          data['day'], data['start_time'], data['end_time']))
        
    if result:
        return jsonify({'message': 'Schedule added successfully'})
    else:
        return jsonify({'error': 'Failed to add schedule'}), 500

@admin_bp.route('/lab-schedules/<int:schedule_id>', methods=['PUT'])
@login_required
def update_lab_schedule(schedule_id):
    try:
        data = request.get_json()
        required_fields = ['purpose_id', 'professor_id']
        
        # Check if all required fields are present
        if not all(field in data for field in required_fields):
            return jsonify({'error': 'Missing required fields'}), 400
            
        # Check if schedule exists
        schedule = execute_query("""
            SELECT * FROM LAB_SCHEDULES 
            WHERE SCHEDULE_ID = %s
        """, (schedule_id,))
        
        if not schedule:
            return jsonify({'error': 'Schedule not found'}), 404
            
        schedule = schedule[0]  # Get the first (and should be only) result
        
        # Check for professor schedule conflicts
        conflict_check = execute_query("""
            SELECT COUNT(*) as count
            FROM LAB_SCHEDULES
            WHERE PROFESSOR_ID = %s
            AND SCHEDULE_ID != %s
            AND DAY_OF_WEEK = %s
            AND (
                (START_TIME <= %s AND END_TIME > %s)
                OR (START_TIME < %s AND END_TIME >= %s)
                OR (START_TIME >= %s AND END_TIME <= %s)
            )
        """, (
            data['professor_id'],
            schedule_id,
            schedule['DAY_OF_WEEK'],
            schedule['START_TIME'],
            schedule['START_TIME'],
            schedule['END_TIME'],
            schedule['END_TIME'],
            schedule['START_TIME'],
            schedule['END_TIME']
        ))
        
        if conflict_check and conflict_check[0]['count'] > 0:
            return jsonify({'error': 'Professor has a conflicting schedule'}), 400
            
        # Update the schedule
        result = execute_query("""
            UPDATE LAB_SCHEDULES
            SET PURPOSE_ID = %s,
                PROFESSOR_ID = %s
            WHERE SCHEDULE_ID = %s
        """, (data['purpose_id'], data['professor_id'], schedule_id))
        
        if result is None:
            return jsonify({'error': 'Failed to update schedule'}), 500
            
        return jsonify({'message': 'Schedule updated successfully'})
        
    except Exception as e:
        print(f"Error updating schedule: {str(e)}")
        return jsonify({'error': 'Failed to update schedule'}), 500

@admin_bp.route('/lab-schedules/delete/<int:schedule_id>', methods=['DELETE'])
@login_required
@role_required('ADMIN')
def delete_lab_schedule(schedule_id):
    try:
        # Check if schedule exists
        check_query = "SELECT COUNT(*) as count FROM LAB_SCHEDULES WHERE SCHEDULE_ID = %s"
        result = execute_query(check_query, (schedule_id,))
        
        if result[0]['count'] == 0:
            return jsonify({'success': False, 'message': 'Schedule not found'}), 404
        
        # Delete schedule
        delete_query = "DELETE FROM LAB_SCHEDULES WHERE SCHEDULE_ID = %s"
        execute_query(delete_query, (schedule_id,))
        
        return jsonify({'success': True, 'message': 'Schedule deleted successfully'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@admin_bp.route('/lab-schedules/available-slots')
@login_required
@role_required('ADMIN')
def get_available_slots():
    try:
        print("\n=== Available Slots Request ===")
        print("Request received at:", datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        
        lab_id = request.args.get('lab_id')
        day = request.args.get('day')
        
        print(f"Received request for lab_id: {lab_id}, day: {day}")
        
        # Define all possible time slots
        all_slots = [
            ('07:30:00', '08:30:00'),  # 1 hour
            ('08:30:00', '09:30:00'),  # 1 hour
            ('09:30:00', '10:30:00'),  # 1 hour
            ('10:30:00', '11:30:00'),  # 1 hour
            ('11:30:00', '12:30:00'),  # 1 hour
            ('13:00:00', '14:00:00'),  # 1 hour
            ('14:00:00', '15:00:00'),  # 1 hour
            ('15:00:00', '16:00:00'),  # 1 hour
            ('16:00:00', '17:00:00'),  # 1 hour
            ('17:00:00', '18:00:00'),  # 1 hour
            ('18:00:00', '19:00:00'),  # 1 hour
            ('19:00:00', '20:00:00'),  # 1 hour
            ('20:00:00', '21:00:00'),  # 1 hour
            ('21:00:00', '22:00:00'),  # 1 hour
            # 1.5 hour slots
            ('07:30:00', '09:00:00'),  # 1.5 hours
            ('09:00:00', '10:30:00'),  # 1.5 hours
            ('10:30:00', '12:00:00'),  # 1.5 hours
            ('13:00:00', '14:30:00'),  # 1.5 hours
            ('14:30:00', '16:00:00'),  # 1.5 hours
            ('16:00:00', '17:30:00'),  # 1.5 hours
            ('17:30:00', '19:00:00'),  # 1.5 hours
            ('19:00:00', '20:30:00'),  # 1.5 hours
            ('20:30:00', '22:00:00'),  # 1.5 hours
            # 2 hour slots
            ('07:30:00', '09:30:00'),  # 2 hours
            ('09:30:00', '11:30:00'),  # 2 hours
            ('13:00:00', '15:00:00'),  # 2 hours
            ('15:00:00', '17:00:00'),  # 2 hours
            ('17:00:00', '19:00:00'),  # 2 hours
            ('19:00:00', '21:00:00')   # 2 hours
        ]
        
        print(f"Total possible time slots: {len(all_slots)}")
        
        if not lab_id or not day:
            print("No lab or day selected, returning all possible slots")
            available_slots = [{
                'START_TIME': start,
                'END_TIME': end,
                'DURATION': (datetime.strptime(end, '%H:%M:%S') - datetime.strptime(start, '%H:%M:%S')).total_seconds() / 3600
            } for start, end in all_slots]
            
            print(f"Returning {len(available_slots)} available slots")
            print("=== End of Available Slots Request ===\n")
            
            return jsonify({
                'success': True,
                'available_slots': available_slots
            })
        
        # Get booked slots for the selected lab and day
        query = """
            SELECT START_TIME, END_TIME 
            FROM LAB_SCHEDULES 
            WHERE LAB_ID = %s 
            AND DAY_OF_WEEK = %s 
            AND STATUS = 'active'
        """
        booked_slots = execute_query(query, (lab_id, day))
        print(f"Found {len(booked_slots)} booked slots")
        
        # Filter out booked slots
        available_slots = []
        for slot in all_slots:
            is_available = True
            for booked in booked_slots:
                # Convert times to datetime objects for comparison
                slot_start = datetime.strptime(slot[0], '%H:%M:%S').time()
                slot_end = datetime.strptime(slot[1], '%H:%M:%S').time()
                booked_start = datetime.strptime(booked['START_TIME'], '%H:%M:%S').time()
                booked_end = datetime.strptime(booked['END_TIME'], '%H:%M:%S').time()
                
                # Check for overlap
                if (slot_start < booked_end and slot_end > booked_start):
                    is_available = False
                    break
            
            if is_available:
                # Calculate duration in hours
                slot_start = datetime.strptime(slot[0], '%H:%M:%S')
                slot_end = datetime.strptime(slot[1], '%H:%M:%S')
                duration = (slot_end - slot_start).total_seconds() / 3600
                available_slots.append({
                    'START_TIME': slot[0],
                    'END_TIME': slot[1],
                    'DURATION': duration
                })
        
        print(f"Found {len(available_slots)} available slots")
        print("Available slots:", available_slots)
        print("=== End of Available Slots Request ===\n")
        
        return jsonify({
            'success': True,
            'available_slots': available_slots
        })
    except Exception as e:
        print(f"\nError in get_available_slots: {str(e)}")
        print("Stack trace:", traceback.format_exc())
        print("=== End of Available Slots Request (Error) ===\n")
        return jsonify({
            'success': False,
            'message': 'Failed to get available time slots'
        }), 500

@admin_bp.route('/reset-all-sit-ins', methods=['POST'])
@login_required
@role_required('ADMIN')
def reset_all_sit_ins():
    try:
        # Get all students
        students_query = """
        SELECT u.IDNO, u.COURSE
        FROM USERS u
        WHERE u.USER_TYPE = 'STUDENT'
        AND u.STATUS = 'active'
        """
        students = execute_query(students_query)
        
        # Reset sit-in counts for each student
        for student in students:
            max_sit_ins = 30 if student['COURSE'] in ['BSIT', 'BSCS'] else 15
            update_query = """
            UPDATE SIT_IN_LIMITS
            SET SIT_IN_COUNT = 0,
                MAX_SIT_INS = %s
            WHERE USER_IDNO = %s
            """
            execute_query(update_query, (max_sit_ins, student['IDNO']))
        
        return jsonify({'success': True, 'message': 'All sit-in counts have been reset'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@admin_bp.route('/reset-student-sit-ins/<idno>', methods=['POST'])
@login_required
@role_required('ADMIN')
def reset_student_sit_ins(idno):
    try:
        # Get student's course
        student_query = """
        SELECT COURSE
        FROM USERS
        WHERE IDNO = %s
        AND USER_TYPE = 'STUDENT'
        """
        student = execute_query(student_query, (idno,))
        
        if not student:
            return jsonify({'success': False, 'message': 'Student not found'}), 404
        
        # Determine max sit-ins based on course
        max_sit_ins = 30 if student[0]['COURSE'] in ['BSIT', 'BSCS'] else 15
        
        # Reset sit-in count
        update_query = """
        UPDATE SIT_IN_LIMITS
        SET SIT_IN_COUNT = 0,
            MAX_SIT_INS = %s
        WHERE USER_IDNO = %s
        """
        execute_query(update_query, (max_sit_ins, idno))
        
        return jsonify({'success': True, 'message': 'Student sit-in count has been reset'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@admin_bp.route('/get-available-time-slots')
@login_required
@role_required('ADMIN')
def get_available_time_slots():
    try:
        print("\n=== Get Available Time Slots Request ===")
        print("Request received at:", datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        
        lab_id = request.args.get('lab_id')
        day = request.args.get('day')
        
        print(f"Received request for lab_id: {lab_id}, day: {day}")
        
        # Get all booked slots for the lab and day
        booked_slots = execute_query("""
            SELECT START_TIME, END_TIME
            FROM LAB_SCHEDULES
            WHERE LAB_ID = %s
            AND DAY_OF_WEEK = %s
            AND STATUS = 'active'
        """, (lab_id, day))
        
        print(f"Found {len(booked_slots)} booked slots")
        
        # Define all possible time slots
        all_slots = [
            ('07:30:00', '08:30:00'),  # 1 hour
            ('08:30:00', '09:30:00'),  # 1 hour
            ('09:30:00', '10:30:00'),  # 1 hour
            ('10:30:00', '11:30:00'),  # 1 hour
            ('11:30:00', '12:30:00'),  # 1 hour
            ('13:00:00', '14:00:00'),  # 1 hour
            ('14:00:00', '15:00:00'),  # 1 hour
            ('15:00:00', '16:00:00'),  # 1 hour
            ('16:00:00', '17:00:00'),  # 1 hour
            ('17:00:00', '18:00:00'),  # 1 hour
            ('18:00:00', '19:00:00'),  # 1 hour
            ('19:00:00', '20:00:00'),  # 1 hour
            ('20:00:00', '21:00:00'),  # 1 hour
            ('21:00:00', '22:00:00'),  # 1 hour
            # 1.5 hour slots
            ('07:30:00', '09:00:00'),  # 1.5 hours
            ('09:00:00', '10:30:00'),  # 1.5 hours
            ('10:30:00', '12:00:00'),  # 1.5 hours
            ('13:00:00', '14:30:00'),  # 1.5 hours
            ('14:30:00', '16:00:00'),  # 1.5 hours
            ('16:00:00', '17:30:00'),  # 1.5 hours
            ('17:30:00', '19:00:00'),  # 1.5 hours
            ('19:00:00', '20:30:00'),  # 1.5 hours
            ('20:30:00', '22:00:00'),  # 1.5 hours
            # 2 hour slots
            ('07:30:00', '09:30:00'),  # 2 hours
            ('09:30:00', '11:30:00'),  # 2 hours
            ('13:00:00', '15:00:00'),  # 2 hours
            ('15:00:00', '17:00:00'),  # 2 hours
            ('17:00:00', '19:00:00'),  # 2 hours
            ('19:00:00', '21:00:00')   # 2 hours
        ]
        
        print(f"Total possible time slots: {len(all_slots)}")
        
        available_slots = []
        for slot in all_slots:
            is_available = True
            slot_start = datetime.strptime(slot[0], '%H:%M:%S').time()
            slot_end = datetime.strptime(slot[1], '%H:%M:%S').time()
            
            for booked in booked_slots:
                booked_start = datetime.strptime(str(booked['START_TIME']), '%H:%M:%S').time()
                booked_end = datetime.strptime(str(booked['END_TIME']), '%H:%M:%S').time()
                
                # Check for overlap
                if (slot_start < booked_end and slot_end > booked_start):
                    is_available = False
                    break
            
            if is_available:
                # Calculate duration in hours
                slot_start_dt = datetime.strptime(slot[0], '%H:%M:%S')
                slot_end_dt = datetime.strptime(slot[1], '%H:%M:%S')
                duration = (slot_end_dt - slot_start_dt).total_seconds() / 3600
                
                available_slots.append({
                    'START_TIME': slot[0],
                    'END_TIME': slot[1],
                    'DURATION': duration
                })
        
        print(f"Found {len(available_slots)} available slots")
        if available_slots:
            print("Available slots:")
            for slot in available_slots:
                print(f"- {slot['START_TIME']} to {slot['END_TIME']} ({slot['DURATION']} hours)")
        
        print("=== End of Get Available Time Slots Request ===\n")
        
        return jsonify({
            'success': True,
            'available_slots': available_slots
        })
        
    except Exception as e:
        print(f"Error in get_available_time_slots: {str(e)}")
        return jsonify({
            'success': False,
            'message': str(e),
            'available_slots': []
        }), 500

@admin_bp.route('/get-all-time-slots')
@login_required
@role_required('ADMIN')
def get_all_time_slots():
    try:
        # Get all time slots from the database
        query = """
            SELECT DISTINCT START_TIME, END_TIME 
            FROM LAB_SCHEDULES 
            WHERE STATUS = 'active'
            ORDER BY START_TIME, END_TIME
        """
        time_slots = execute_query(query)
        
        if not time_slots:
            return jsonify({
                'success': True,
                'time_slots': []
            })
        
        return jsonify({
            'success': True,
            'time_slots': time_slots
        })
    except Exception as e:
        print(f"Error getting time slots: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'Failed to get time slots'
        }), 500

@admin_bp.route('/lab-schedules/add')
@login_required
@role_required('ADMIN')
def add_lab_schedule_page():
    try:
        print("\n=== Add Lab Schedule Page Request ===")
        print("Request received at:", datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        print("User accessing page:", session.get('user_id'))
        
        # Get all labs
        labs_query = "SELECT * FROM LABORATORIES WHERE STATUS = 'active'"
        labs = execute_query(labs_query)
        print(f"Found {len(labs)} active labs")
        print("Labs:", [lab['LAB_NAME'] for lab in labs])
        
        # Get all purposes
        purposes_query = "SELECT * FROM PURPOSES WHERE STATUS = 'active'"
        purposes = execute_query(purposes_query)
        print(f"Found {len(purposes)} active purposes")
        print("Purposes:", [purpose['PURPOSE_NAME'] for purpose in purposes])
        
        # Get all professors
        professors_query = "SELECT * FROM PROFESSORS WHERE STATUS = 'active'"
        professors = execute_query(professors_query)
        # Format professor names
        for prof in professors:
            prof['PROFESSOR_NAME'] = f"{prof['LAST_NAME']}, {prof['FIRST_NAME']} {prof['MIDDLE_NAME'] if prof['MIDDLE_NAME'] else ''}"
        print(f"Found {len(professors)} active professors")
        print("Professors:", [prof['PROFESSOR_NAME'] for prof in professors])
        
        print("Rendering template: admin/add_lab_schedule.html")
        print("=== End of Add Lab Schedule Page Request ===\n")
        
        return render_template('admin/add_lab_schedule.html', 
                             labs=labs, 
                             purposes=purposes,
                             professors=professors)
    except Exception as e:
        print(f"\nError in add_lab_schedule_page: {str(e)}")
        print("Stack trace:", traceback.format_exc())
        flash('Error loading add schedule page', 'error')
        return redirect(url_for('admin.lab_schedules'))

@admin_bp.route('/computer-control')
@login_required
@role_required('ADMIN')
def computer_control():
    # Get all active laboratories
    laboratories = execute_query("""
        SELECT * FROM LABORATORIES 
        WHERE STATUS = 'active' 
        ORDER BY LAB_NAME
    """)
    return render_template('admin/computer_control.html', laboratories=laboratories)

@admin_bp.route('/labs/<int:lab_id>')
@login_required
@role_required('ADMIN')
def get_lab_info(lab_id):
    try:
        # Get lab information with computer counts
        query = """
        SELECT 
            l.*,
            COUNT(c.COMPUTER_ID) as total_computers,
            SUM(CASE WHEN c.STATUS = 'available' THEN 1 ELSE 0 END) as available_computers,
            SUM(CASE WHEN c.STATUS = 'in_use' THEN 1 ELSE 0 END) as in_use_computers,
            SUM(CASE WHEN c.STATUS = 'maintenance' THEN 1 ELSE 0 END) as maintenance_computers
        FROM LABORATORIES l
        LEFT JOIN COMPUTERS c ON l.LAB_ID = c.LAB_ID
        WHERE l.LAB_ID = %s
        GROUP BY l.LAB_ID, l.LAB_NAME, l.STATUS, l.CREATED_AT
        """
        lab = execute_query(query, (lab_id,))
        
        if not lab:
            return jsonify({'error': 'Laboratory not found'}), 404
        
        # Convert Decimal values to integers
        lab_data = lab[0]
        lab_data['total_computers'] = int(lab_data['total_computers'])
        lab_data['available_computers'] = int(lab_data['available_computers'])
        lab_data['in_use_computers'] = int(lab_data['in_use_computers'])
        lab_data['maintenance_computers'] = int(lab_data['maintenance_computers'])
        
        return jsonify(lab_data)
    except Exception as e:
        print(f"Error in get_lab_info: {str(e)}")
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/labs/<int:lab_id>/computers')
@login_required
@role_required('ADMIN')
def get_lab_computers(lab_id):
    # Get all computers in the lab
    computers = execute_query("""
        SELECT * FROM COMPUTERS 
        WHERE LAB_ID = %s 
        ORDER BY COMPUTER_NUMBER
    """, (lab_id,))
    
    return jsonify(computers)

@admin_bp.route('/computers/update-status', methods=['POST'])
@login_required
@role_required('ADMIN')
def update_computer_status():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
            
        computer_id = data.get('computer_id')
        status = data.get('status')
        
        if not computer_id or not status:
            return jsonify({'error': 'Missing required fields'}), 400
        
        # Update computer status
        execute_query("""
            UPDATE COMPUTERS 
            SET STATUS = %s
            WHERE COMPUTER_ID = %s
        """, (status, computer_id))
        
        return jsonify({'success': True, 'message': 'Computer status updated successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/labs/<int:lab_id>/enable-all', methods=['POST'])
@login_required
@role_required('ADMIN')
def enable_all_computers(lab_id):
    try:
        # Update all computers in the lab to available
        execute_query("""
            UPDATE COMPUTERS 
            SET STATUS = 'available' 
            WHERE LAB_ID = %s
        """, (lab_id,))
        
        return jsonify({'success': True, 'message': 'All computers enabled successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/labs/<int:lab_id>/disable-all', methods=['POST'])
@login_required
@role_required('ADMIN')
def disable_all_computers(lab_id):
    try:
        # Update all computers in the lab to maintenance
        execute_query("""
            UPDATE COMPUTERS 
            SET STATUS = 'maintenance' 
            WHERE LAB_ID = %s
        """, (lab_id,))
        
        return jsonify({'success': True, 'message': 'All computers disabled successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/resources/upload', methods=['POST'])
@login_required
def upload_resource():
    if request.method == 'POST':
        try:
            title = request.form.get('title')
            context = request.form.get('context')
            resource_type = request.form.get('resource_type')
            purpose_id = request.form.get('purpose_id')
            
            if not all([title, resource_type, purpose_id]):
                return jsonify({'success': False, 'error': 'Missing required fields'})
            
            # Handle different resource types
            if resource_type in ['file', 'image']:
                if 'file' not in request.files:
                    return jsonify({'success': False, 'error': 'No file uploaded'})
                
                file = request.files['file']
                if file.filename == '':
                    return jsonify({'success': False, 'error': 'No file selected'})
                
                # Read file content
                file_content = file.read()
                file_name = secure_filename(file.filename)
                file_type = file.content_type
                
                # Insert into database with file content
                query = """
                    INSERT INTO LAB_RESOURCES 
                    (TITLE, CONTEXT, RESOURCE_TYPE, RESOURCE_FILE, FILE_NAME, FILE_TYPE, PURPOSE_ID, CREATED_BY)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """
                execute_query(query, (
                    title, context, resource_type, file_content, 
                    file_name, file_type, purpose_id, session['user_id']
                ))
                
            else:  # For text and link types
                resource_value = request.form.get('resource_value')
                if not resource_value:
                    return jsonify({'success': False, 'error': 'Resource value is required'})
                
                query = """
                    INSERT INTO LAB_RESOURCES 
                    (TITLE, CONTEXT, RESOURCE_TYPE, RESOURCE_VALUE, PURPOSE_ID, CREATED_BY)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """
                execute_query(query, (
                    title, context, resource_type, resource_value, 
                    purpose_id, session['user_id']
                ))
            
            return jsonify({'success': True})
            
        except Exception as e:
            print(f"Error uploading resource: {str(e)}")
            return jsonify({'success': False, 'error': str(e)})

@admin_bp.route('/resources/<int:resource_id>/file')
@login_required
def get_resource_file(resource_id):
    try:
        query = """
            SELECT RESOURCE_FILE, FILE_NAME, FILE_TYPE 
            FROM LAB_RESOURCES 
            WHERE RESOURCE_ID = %s AND RESOURCE_TYPE IN ('file', 'image')
        """
        result = execute_query(query, (resource_id,))
        
        if not result or not result[0]['RESOURCE_FILE']:
            return jsonify({'success': False, 'error': 'File not found'}), 404
        
        file_data = result[0]
        return send_file(
            io.BytesIO(file_data['RESOURCE_FILE']),
            mimetype=file_data['FILE_TYPE'],
            as_attachment=True,
            download_name=file_data['FILE_NAME']
        )
        
    except Exception as e:
        print(f"Error retrieving file: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@admin_bp.route('/resources/<int:resource_id>/view')
@login_required
def view_resource_file(resource_id):
    try:
        query = """
            SELECT RESOURCE_FILE, FILE_NAME, FILE_TYPE 
            FROM LAB_RESOURCES 
            WHERE RESOURCE_ID = %s AND RESOURCE_TYPE IN ('file', 'image')
        """
        result = execute_query(query, (resource_id,))
        
        if not result or not result[0]['RESOURCE_FILE']:
            return jsonify({'success': False, 'error': 'File not found'}), 404
        
        file_data = result[0]
        return send_file(
            io.BytesIO(file_data['RESOURCE_FILE']),
            mimetype=file_data['FILE_TYPE'],
            as_attachment=False,
            download_name=file_data['FILE_NAME']
        )
        
    except Exception as e:
        print(f"Error retrieving file: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@admin_bp.route('/resources/<int:resource_id>/edit', methods=['POST'])
@login_required
@role_required('ADMIN')
def update_resource(resource_id):
    try:
        title = request.form.get('title')
        context = request.form.get('context')
        resource_type = request.form.get('resource_type')
        purpose_id = request.form.get('purpose_id')
        enabled = request.form.get('enabled') == 'on'
        
        if not title or not resource_type or not purpose_id:
            return jsonify({'error': 'Missing required fields'}), 400
        
        # Get current resource
        current_query = "SELECT * FROM LAB_RESOURCES WHERE RESOURCE_ID = %s"
        current_resource = execute_query(current_query, (resource_id,))
        
        if not current_resource:
            return jsonify({'error': 'Resource not found'}), 404
        
        current_resource = current_resource[0]
        
        # Handle file upload
        if resource_type in ['file', 'image'] and 'file' in request.files:
            file = request.files['file']
            if file.filename != '':
                # Read new file content
                file_content = file.read()
                file_name = secure_filename(file.filename)
                file_type = file.content_type
                
                # Update with new file
                query = """
                UPDATE LAB_RESOURCES 
                SET TITLE = %s, CONTEXT = %s, RESOURCE_TYPE = %s, 
                    RESOURCE_FILE = %s, FILE_NAME = %s, FILE_TYPE = %s,
                    PURPOSE_ID = %s, ENABLED = %s
                WHERE RESOURCE_ID = %s
                """
                execute_query(query, (
                    title, context, resource_type, file_content,
                    file_name, file_type, purpose_id, enabled, resource_id
                ))
            else:
                # Keep existing file
                query = """
                UPDATE LAB_RESOURCES 
                SET TITLE = %s, CONTEXT = %s, RESOURCE_TYPE = %s,
                    PURPOSE_ID = %s, ENABLED = %s
                WHERE RESOURCE_ID = %s
                """
                execute_query(query, (
                    title, context, resource_type, purpose_id, enabled, resource_id
                ))
        else:
            # For non-file resources
            resource_value = request.form.get('resource_value')
            if not resource_value:
                return jsonify({'error': 'Resource value is required'}), 400
            
            query = """
            UPDATE LAB_RESOURCES 
            SET TITLE = %s, CONTEXT = %s, RESOURCE_TYPE = %s,
                RESOURCE_VALUE = %s, PURPOSE_ID = %s, ENABLED = %s
            WHERE RESOURCE_ID = %s
            """
            execute_query(query, (
                title, context, resource_type, resource_value,
                purpose_id, enabled, resource_id
            ))
        
        return jsonify({'success': True, 'message': 'Resource updated successfully'})
    except Exception as e:
        print(f"Error updating resource: {str(e)}")
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/professors')
@login_required
@role_required('ADMIN')
def manage_professors():
    if session.get('user_type') not in ['ADMIN', 'STAFF']:
        return redirect(url_for('auth.login'))
    
    # Get all professors
    professors = execute_query("""
        SELECT * FROM PROFESSORS 
        ORDER BY LAST_NAME, FIRST_NAME
    """)
    
    return render_template('admin/professors.html', professors=professors)

@admin_bp.route('/professors/add', methods=['POST'])
@login_required
@role_required('ADMIN')
def add_professor():
    if session.get('user_type') not in ['ADMIN', 'STAFF']:
        return jsonify({'success': False, 'message': 'Unauthorized access'})
    
    try:
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        middle_name = request.form.get('middle_name', '')
        
        if not first_name or not last_name:
            return jsonify({'success': False, 'message': 'First name and last name are required'})
        
        # Insert new professor
        execute_query("""
            INSERT INTO PROFESSORS (FIRST_NAME, LAST_NAME, MIDDLE_NAME, STATUS)
            VALUES (%s, %s, %s, 'active')
        """, (first_name, last_name, middle_name))
        
        return jsonify({'success': True, 'message': 'Professor added successfully'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@admin_bp.route('/professors/edit/<int:professor_id>', methods=['POST'])
@login_required
@role_required('ADMIN')
def edit_professor(professor_id):
    if session.get('user_type') not in ['ADMIN', 'STAFF']:
        return jsonify({'success': False, 'message': 'Unauthorized access'})
    
    try:
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        middle_name = request.form.get('middle_name', '')
        status = request.form.get('status', 'active')
        
        if not first_name or not last_name:
            return jsonify({'success': False, 'message': 'First name and last name are required'})
        
        # Update professor
        execute_query("""
            UPDATE PROFESSORS 
            SET FIRST_NAME = %s, LAST_NAME = %s, MIDDLE_NAME = %s, STATUS = %s
            WHERE PROFESSOR_ID = %s
        """, (first_name, last_name, middle_name, status, professor_id))
        
        return jsonify({'success': True, 'message': 'Professor updated successfully'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@admin_bp.route('/professors/delete/<int:professor_id>', methods=['POST'])
@login_required
@role_required('ADMIN')
def delete_professor(professor_id):
    if session.get('user_type') not in ['ADMIN', 'STAFF']:
        return jsonify({'success': False, 'message': 'Unauthorized access'})
    
    try:
        # Check if professor is assigned to any schedules
        schedules = execute_query("""
            SELECT COUNT(*) as count 
            FROM LAB_SCHEDULES 
            WHERE PROFESSOR_ID = %s
        """, (professor_id,))
        
        if schedules and schedules[0]['count'] > 0:
            return jsonify({
                'success': False, 
                'message': 'Cannot delete professor. They are assigned to existing schedules.'
            })
        
        # Delete professor
        execute_query("""
            DELETE FROM PROFESSORS 
            WHERE PROFESSOR_ID = %s
        """, (professor_id,))
        
        return jsonify({'success': True, 'message': 'Professor deleted successfully'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@admin_bp.route('/handle-reservation/<int:reservation_id>/<action>', methods=['POST'])
@login_required
@role_required('ADMIN')
def handle_reservation(reservation_id, action):
    try:
        if action not in ['approve', 'deny']:
            return jsonify({'error': 'Invalid action'}), 400
            
        status = 'APPROVED' if action == 'approve' else 'DENIED'
        
        # Get reservation details first
        reservation = execute_query("""
            SELECT r.*, u.COURSE, u.YEAR,
                   COALESCE(sp.CURRENT_POINTS, 0) as current_points,
                   COALESCE(sl.MAX_SIT_INS - sl.SIT_IN_COUNT, 0) as remaining_sessions
            FROM RESERVATIONS r
            JOIN USERS u ON r.USER_IDNO = u.IDNO
            LEFT JOIN STUDENT_POINTS sp ON r.USER_IDNO = sp.USER_IDNO
            LEFT JOIN SIT_IN_LIMITS sl ON r.USER_IDNO = sl.USER_IDNO
            WHERE r.RESERVATION_ID = %s
        """, (reservation_id,))
        
        if not reservation:
            return jsonify({'error': 'Reservation not found'}), 404
            
        reservation = reservation[0]
        
        # Check if student has enough points/sessions before approving
        if status == 'APPROVED':
            if reservation.get('USE_POINTS'):
                if reservation['current_points'] < 3:
                    return jsonify({
                        'error': 'Student does not have enough points for this reservation'
                    }), 400
            else:
                if reservation['remaining_sessions'] <= 0:
                    return jsonify({
                        'error': 'Student does not have any remaining sit-in sessions'
                    }), 400
        
        # Update reservation status
        execute_query("""
            UPDATE RESERVATIONS 
            SET STATUS = %s,
                UPDATED_AT = NOW()
            WHERE RESERVATION_ID = %s
        """, (status, reservation_id))
        
        if status == 'APPROVED':
            # Check if the reservation time has already started
            current_time = datetime.now()
            reservation_datetime = datetime.combine(
                reservation['RESERVATION_DATE'],
                datetime.strptime(str(reservation['TIME_IN']), '%H:%M:%S').time()
            )
            
            # Set initial sit-in status based on time
            sit_in_status = 'APPROVED'
            sit_in_session = 'ON_GOING'
            
            # Create sit-in record
            sit_in_query = """
            INSERT INTO SIT_IN_RECORDS (
                USER_IDNO, LAB_ID, COMPUTER_ID, PURPOSE_ID,
                DATE, TIME_IN, STATUS, SESSION, USE_POINTS,
                CREATED_AT
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
            """
            execute_query(sit_in_query, (
                reservation['USER_IDNO'],
                reservation['LAB_ID'],
                reservation['COMPUTER_ID'],
                reservation['PURPOSE_ID'],
                reservation['RESERVATION_DATE'],
                reservation['TIME_IN'],
                sit_in_status,
                sit_in_session,
                reservation.get('USE_POINTS', False)
            ))
            
            # Handle points or sit-in count immediately upon approval
            if reservation.get('USE_POINTS'):
                # Deduct points
                execute_query("""
                    UPDATE STUDENT_POINTS
                    SET CURRENT_POINTS = CURRENT_POINTS - 3
                    WHERE USER_IDNO = %s
                """, (reservation['USER_IDNO'],))
                
                # Add to point history
                execute_query("""
                    INSERT INTO POINT_HISTORY (USER_IDNO, POINTS_CHANGE, REASON, ADDED_BY)
                    VALUES (%s, -3, 'Points used for reservation', %s)
                """, (reservation['USER_IDNO'], session['user_id']))
            else:
                # Increment sit-in count
                execute_query("""
                    UPDATE SIT_IN_LIMITS
                    SET SIT_IN_COUNT = SIT_IN_COUNT + 1
                    WHERE USER_IDNO = %s
                """, (reservation['USER_IDNO'],))
            
            # Update computer status
            execute_query("""
                UPDATE COMPUTERS
                SET STATUS = 'in_use'
                WHERE COMPUTER_ID = %s
            """, (reservation['COMPUTER_ID'],))
        
        return jsonify({
            'success': True,
            'message': f'Reservation {status.lower()} successfully'
        })
        
    except Exception as e:
        print(f"Error in handle_reservation: {str(e)}")
        return jsonify({'error': 'An error occurred while processing the reservation'}), 500

@admin_bp.route('/reservations')
@login_required
@role_required('ADMIN')
def manage_reservations():
    try:
        # Get filter parameters
        status = request.args.get('status', 'all')
        date = request.args.get('date')
        lab_id = request.args.get('lab_id')
        
        # Base query conditions
        conditions = []
        params = []
        
        if status != 'all':
            conditions.append("r.STATUS = %s")
            params.append(status)
            
        if date:
            conditions.append("r.RESERVATION_DATE = %s")
            params.append(date)
            
        if lab_id:
            conditions.append("r.LAB_ID = %s")
            params.append(lab_id)
            
        # Build the WHERE clause
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        
        # Get pending reservations
        pending_query = f"""
        SELECT 
            r.*,
            l.LAB_NAME,
            p.PURPOSE_NAME,
            c.COMPUTER_NUMBER,
            u.FIRSTNAME,
            u.LASTNAME,
            u.COURSE,
            u.YEAR,
            DATE_FORMAT(r.CREATED_AT, '%Y-%m-%d %H:%i') as CREATED_TIME,
            DATE_FORMAT(r.TIME_IN, '%h:%i %p') as FORMATTED_TIME
        FROM RESERVATIONS r
        JOIN LABORATORIES l ON r.LAB_ID = l.LAB_ID
        JOIN PURPOSES p ON r.PURPOSE_ID = p.PURPOSE_ID
        JOIN COMPUTERS c ON r.COMPUTER_ID = c.COMPUTER_ID
        JOIN USERS u ON r.USER_IDNO = u.IDNO
        WHERE {where_clause} AND r.STATUS = 'PENDING'
        ORDER BY r.RESERVATION_DATE ASC, r.TIME_IN ASC
        """
        pending_reservations = execute_query(pending_query, tuple(params))
        
        # Get completed reservations (approved/denied)
        completed_query = f"""
        SELECT 
            r.*,
            l.LAB_NAME,
            p.PURPOSE_NAME,
            c.COMPUTER_NUMBER,
            u.FIRSTNAME,
            u.LASTNAME,
            u.COURSE,
            u.YEAR,
            DATE_FORMAT(r.CREATED_AT, '%Y-%m-%d %H:%i') as CREATED_TIME,
            DATE_FORMAT(r.TIME_IN, '%h:%i %p') as FORMATTED_TIME
        FROM RESERVATIONS r
        JOIN LABORATORIES l ON r.LAB_ID = l.LAB_ID
        JOIN PURPOSES p ON r.PURPOSE_ID = p.PURPOSE_ID
        JOIN COMPUTERS c ON r.COMPUTER_ID = c.COMPUTER_ID
        JOIN USERS u ON r.USER_IDNO = u.IDNO
        WHERE {where_clause} AND r.STATUS IN ('APPROVED', 'DENIED')
        ORDER BY r.UPDATED_AT DESC
        """
        completed_reservations = execute_query(completed_query, tuple(params))
        
        # Get labs for filter
        labs = execute_query("SELECT * FROM LABORATORIES WHERE STATUS = 'active' ORDER BY LAB_NAME")
        
        return render_template('admin/reservations.html',
                             pending_reservations=pending_reservations,
                             completed_reservations=completed_reservations,
                             labs=labs,
                             current_status=status,
                             current_date=date,
                             current_lab=lab_id)
                             
    except Exception as e:
        print(f"Error in manage_reservations: {str(e)}")
        flash('An error occurred while loading reservations', 'error')
        return redirect(url_for('admin.dashboard'))