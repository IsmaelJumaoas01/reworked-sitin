from flask import Blueprint, render_template, request, redirect, url_for, session, flash, send_file, jsonify, Response
from db import execute_query
from functools import wraps
from routes.auth import login_required, role_required
import os
from io import BytesIO, StringIO
import csv
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
import xlsxwriter
from werkzeug.utils import secure_filename
from datetime import datetime

staff_bp = Blueprint('staff', __name__)

@staff_bp.route('/staff/dashboard')
def dashboard():
    if 'user_id' not in session or session['user_type'] != 'STAFF':
        return redirect(url_for('auth.login'))
    
    try:
        # Get basic statistics
        stats_query = """
        SELECT 
            (SELECT COUNT(*) FROM USERS WHERE USER_TYPE = 'STUDENT') as total_students,
            (SELECT COUNT(*) FROM SIT_IN_RECORDS WHERE SESSION = 'ON_GOING') as active_sit_ins,
            (SELECT COUNT(*) FROM LABORATORIES) as total_labs,
            (SELECT COUNT(*) FROM PURPOSES) as total_purposes
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
        SELECT p.PURPOSE_NAME, COUNT(sr.RECORD_ID) as usage_count
        FROM PURPOSES p
        LEFT JOIN SIT_IN_RECORDS sr ON p.PURPOSE_ID = sr.PURPOSE_ID
        GROUP BY p.PURPOSE_ID, p.PURPOSE_NAME
        ORDER BY usage_count DESC
        """
        purpose_stats = execute_query(purpose_query)
        purpose_labels = [purpose['PURPOSE_NAME'] for purpose in purpose_stats]
        purpose_data = [purpose['usage_count'] for purpose in purpose_stats]

        # Get recent sit-ins
        sit_in_query = """
        SELECT 
            sr.RECORD_ID,
            CONCAT(u.FIRSTNAME, ' ', u.LASTNAME) as student_name,
            l.LAB_NAME as lab_name,
            p.PURPOSE_NAME as purpose_name,
            sr.DATE as date,
            sr.STATUS as status
        FROM SIT_IN_RECORDS sr
        JOIN USERS u ON sr.USER_IDNO = u.IDNO
        JOIN LABORATORIES l ON sr.LAB_ID = l.LAB_ID
        JOIN PURPOSES p ON sr.PURPOSE_ID = p.PURPOSE_ID
        ORDER BY sr.CREATED_AT DESC
        LIMIT 10
        """
        recent_sit_ins = execute_query(sit_in_query)

        return render_template('staff/dashboard.html',
                             stats=stats,
                             lab_labels=lab_labels,
                             lab_data=lab_data,
                             purpose_labels=purpose_labels,
                             purpose_data=purpose_data,
                             recent_sit_ins=recent_sit_ins)
    except Exception as e:
        print(f"Error in staff dashboard: {str(e)}")
        return render_template('error.html', 
                             error_message="An error occurred while loading the dashboard.",
                             back_url=url_for('auth.login'))

@staff_bp.route('/staff/manage-sit-ins')
def manage_sit_ins():
    if 'user_id' not in session or session['user_type'] != 'STAFF':
        return redirect(url_for('auth.login'))
    
    # Get all sit-in requests
    sit_ins_query = """
    SELECT sr.*, u.FIRSTNAME, u.LASTNAME, l.LAB_NAME, p.PURPOSE_NAME 
    FROM SIT_IN_RECORDS sr
    JOIN USERS u ON sr.USER_IDNO = u.IDNO
    JOIN LABORATORIES l ON sr.LAB_ID = l.LAB_ID
    JOIN PURPOSES p ON sr.PURPOSE_ID = p.PURPOSE_ID
    ORDER BY sr.DATE DESC
    """
    sit_ins = execute_query(sit_ins_query)
    
    return render_template('staff/manage_sit_ins.html', sit_ins=sit_ins)

@staff_bp.route('/staff/approve-sit-in/<int:record_id>')
def approve_sit_in(record_id):
    if 'user_id' not in session or session['user_type'] != 'STAFF':
        return redirect(url_for('auth.login'))
    
    # Update sit-in status
    query = "UPDATE SIT_IN_RECORDS SET STATUS = 'APPROVED', SESSION = 'ON_GOING' WHERE RECORD_ID = %s"
    result = execute_query(query, (record_id,))
    
    if result:
        # Update sit-in count for student
        update_count_query = """
        UPDATE SIT_IN_LIMITS 
        SET SIT_IN_COUNT = SIT_IN_COUNT + 1 
        WHERE USER_IDNO = (SELECT USER_IDNO FROM SIT_IN_RECORDS WHERE RECORD_ID = %s)
        """
        execute_query(update_count_query, (record_id,))
        flash('Sit-in request approved successfully', 'success')
    else:
        flash('Failed to approve sit-in request', 'error')
    
    return redirect(url_for('staff.manage_sit_ins'))

@staff_bp.route('/staff/deny-sit-in/<int:record_id>')
def deny_sit_in(record_id):
    if 'user_id' not in session or session['user_type'] != 'STAFF':
        return redirect(url_for('auth.login'))
    
    # Update sit-in status
    query = "UPDATE SIT_IN_RECORDS SET STATUS = 'DENIED' WHERE RECORD_ID = %s"
    result = execute_query(query, (record_id,))
    
    if result:
        flash('Sit-in request denied successfully', 'success')
    else:
        flash('Failed to deny sit-in request', 'error')
    
    return redirect(url_for('staff.manage_sit_ins'))

@staff_bp.route('/staff/end-sit-in/<int:record_id>')
@login_required
@role_required('STAFF')
def end_sit_in_session(record_id):
    if 'user_id' not in session or session['user_type'] != 'STAFF':
        return redirect(url_for('auth.login'))
    
    # Update sit-in session status
    query = "UPDATE SIT_IN_RECORDS SET SESSION = 'ENDED' WHERE RECORD_ID = %s"
    result = execute_query(query, (record_id,))
    
    if result:
        flash('Sit-in session ended successfully', 'success')
    else:
        flash('Failed to end sit-in session', 'error')
    
    return redirect(url_for('staff.manage_sit_ins'))

@staff_bp.route('/staff/end-sit-in/<int:record_id>', methods=['POST'])
@login_required
@role_required('STAFF')
def end_sit_in(record_id):
    try:
        # Get the sit-in record
        record_query = """
        SELECT USER_IDNO, SESSION, COMPUTER_ID
        FROM SIT_IN_RECORDS
        WHERE RECORD_ID = %s
        """
        record = execute_query(record_query, (record_id,))
        
        if not record:
            return jsonify({'success': False, 'message': 'Sit-in record not found'}), 404
        
        if record[0]['SESSION'] != 'ON_GOING':
            return jsonify({'success': False, 'message': 'Sit-in session is already ended'}), 400
        
        # Update sit-in session status
        update_query = """
        UPDATE SIT_IN_RECORDS
        SET SESSION = 'COMPLETED',
            STATUS = 'COMPLETED',
            TIME_OUT = NOW()
        WHERE RECORD_ID = %s
        """
        execute_query(update_query, (record_id,))
        
        # Update sit-in count for the student
        update_count_query = """
        UPDATE SIT_IN_LIMITS
        SET SIT_IN_COUNT = SIT_IN_COUNT + 1
        WHERE USER_IDNO = %s
        """
        execute_query(update_count_query, (record[0]['USER_IDNO']))
        
        # Check if student has a record in STUDENT_POINTS
        check_points_query = """
        SELECT COUNT(*) as count
        FROM STUDENT_POINTS
        WHERE USER_IDNO = %s
        """
        points_result = execute_query(check_points_query, (record[0]['USER_IDNO'],))
        
        if points_result[0]['count'] == 0:
            # Create initial record if it doesn't exist
            insert_points_query = """
            INSERT INTO STUDENT_POINTS (USER_IDNO, CURRENT_POINTS, TOTAL_POINTS)
            VALUES (%s, 1, 1)
            """
            execute_query(insert_points_query, (record[0]['USER_IDNO'],))
        else:
            # Update existing record
            points_query = """
            UPDATE STUDENT_POINTS 
            SET CURRENT_POINTS = CURRENT_POINTS + 1,
                TOTAL_POINTS = TOTAL_POINTS + 1
            WHERE USER_IDNO = %s
            """
            execute_query(points_query, (record[0]['USER_IDNO'],))
        
        # Add to point history
        history_query = """
        INSERT INTO POINT_HISTORY (USER_IDNO, POINTS_CHANGE, REASON, ADDED_BY)
        VALUES (%s, 1, 'Completed sit-in session', %s)
        """
        execute_query(history_query, (record[0]['USER_IDNO'], session['user_id']))
        
        # Update computer status back to available
        update_computer_query = """
        UPDATE COMPUTERS
        SET STATUS = 'available'
        WHERE COMPUTER_ID = %s
        """
        execute_query(update_computer_query, (record[0]['COMPUTER_ID'],))
        
        return jsonify({'success': True, 'message': 'Sit-in session ended successfully'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@staff_bp.route('/profile/picture', methods=['GET', 'POST'])
@login_required
@role_required('STAFF')
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

@staff_bp.route('/staff/sit-in')
@login_required
@role_required('STAFF')
def sit_in_management():
    try:
        # Get today's sit-ins
        today_query = """
        SELECT 
            sr.*,
            u.FIRSTNAME,
            u.LASTNAME,
            l.LAB_NAME,
            p.PURPOSE_NAME
        FROM SIT_IN_RECORDS sr
        JOIN USERS u ON sr.USER_IDNO = u.IDNO
        JOIN LABORATORIES l ON sr.LAB_ID = l.LAB_ID
        JOIN PURPOSES p ON sr.PURPOSE_ID = p.PURPOSE_ID
        WHERE DATE(sr.CREATED_AT) = CURDATE()
        ORDER BY sr.CREATED_AT DESC
        """
        today_sit_ins = execute_query(today_query)
        
        return render_template('staff/sit_in.html', today_sit_ins=today_sit_ins)
    except Exception as e:
        print(f"Error in sit-in management: {str(e)}")
        flash('An error occurred while loading sit-in management', 'error')
        return redirect(url_for('staff.dashboard'))

@staff_bp.route('/staff/active-sit-ins')
@login_required
@role_required('STAFF')
def get_active_sit_ins():
    query = """
    SELECT sr.*, u.FIRSTNAME, u.LASTNAME, l.LAB_NAME, p.PURPOSE_NAME
    FROM SIT_IN_RECORDS sr
    JOIN USERS u ON sr.USER_IDNO = u.IDNO
    JOIN LABORATORIES l ON sr.LAB_ID = l.LAB_ID
    JOIN PURPOSES p ON sr.PURPOSE_ID = p.PURPOSE_ID
    WHERE sr.SESSION = 'ON_GOING'
    ORDER BY sr.CREATED_AT DESC
    """
    sit_ins = execute_query(query)
    return jsonify(sit_ins)

@staff_bp.route('/staff/start-sit-in', methods=['POST'])
@login_required
@role_required('STAFF')
def start_sit_in():
    data = request.get_json()
    student_idno = data.get('student_idno')
    lab_id = data.get('lab_id')
    purpose_id = data.get('purpose_id')
    
    if not all([student_idno, lab_id, purpose_id]):
        return jsonify({'success': False, 'message': 'Missing required fields'})
    
    try:
        # Check if student has remaining sessions
        check_query = """
        SELECT sl.MAX_SIT_INS - sl.SIT_IN_COUNT as remaining_sessions
        FROM SIT_IN_LIMITS sl
        WHERE sl.USER_IDNO = %s
        """
        result = execute_query(check_query, (student_idno,))
        
        if not result or result[0]['remaining_sessions'] <= 0:
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
        
        # Start sit-in session
        insert_query = """
        INSERT INTO SIT_IN_RECORDS (USER_IDNO, LAB_ID, PURPOSE_ID, CREATED_AT, SESSION, STATUS)
        VALUES (%s, %s, %s, NOW(), 'ON_GOING', 'APPROVED')
        """
        execute_query(insert_query, (student_idno, lab_id, purpose_id))
        
        # Update sit-in count
        update_query = """
        UPDATE SIT_IN_LIMITS
        SET SIT_IN_COUNT = SIT_IN_COUNT + 1
        WHERE USER_IDNO = %s
        """
        execute_query(update_query, (student_idno,))
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@staff_bp.route('/staff/labs')
@login_required
@role_required('STAFF')
def get_labs():
    query = """
    SELECT l.*, 
           COUNT(c.COMPUTER_ID) as total_computers,
           SUM(CASE WHEN c.STATUS = 'available' THEN 1 ELSE 0 END) as available_computers,
           SUM(CASE WHEN c.STATUS = 'in_use' THEN 1 ELSE 0 END) as in_use_computers,
           SUM(CASE WHEN c.STATUS = 'maintenance' THEN 1 ELSE 0 END) as maintenance_computers
    FROM LABORATORIES l
    LEFT JOIN COMPUTERS c ON l.LAB_ID = c.LAB_ID
    GROUP BY l.LAB_ID
    ORDER BY l.LAB_NAME
    """
    labs = execute_query(query)
    return jsonify(labs)

@staff_bp.route('/staff/purposes')
@login_required
@role_required('STAFF')
def get_purposes():
    query = """
    SELECT * FROM PURPOSES 
    WHERE STATUS = 'active'
    ORDER BY PURPOSE_NAME
    """
    purposes = execute_query(query)
    return jsonify(purposes)

@staff_bp.route('/staff/student/<idno>')
@login_required
@role_required('STAFF')
def get_student(idno):
    query = """
    SELECT 
        u.IDNO,
        u.FIRSTNAME,
        u.LASTNAME,
        u.COURSE,
        u.YEAR,
        u.EMAIL,
        u.STATUS,
        COALESCE(sl.MAX_SIT_INS - sl.SIT_IN_COUNT, 0) as remaining_sessions
    FROM USERS u
    LEFT JOIN SIT_IN_LIMITS sl ON u.IDNO = sl.USER_IDNO
    WHERE u.IDNO = %s AND u.USER_TYPE = 'STUDENT'
    """
    student = execute_query(query, (idno,))
    
    if student:
        return jsonify(student[0])
    return jsonify({'error': 'Student not found'}), 404

@staff_bp.route('/staff/sit-in-records')
@login_required
@role_required('STAFF')
def sit_in_records():
    page = request.args.get('page', 1, type=int)
    per_page = 10
    
    # Get total count
    count_query = "SELECT COUNT(*) as total FROM SIT_IN_RECORDS"
    total = execute_query(count_query)[0]['total']
    
    # Calculate offset
    offset = (page - 1) * per_page
    
    # Get paginated records
    query = """
    SELECT 
        sr.*,
        u.FIRSTNAME,
        u.LASTNAME,
        u.COURSE,
        u.YEAR,
        l.LAB_NAME,
        p.PURPOSE_NAME
    FROM SIT_IN_RECORDS sr
    JOIN USERS u ON sr.USER_IDNO = u.IDNO
    JOIN LABORATORIES l ON sr.LAB_ID = l.LAB_ID
    JOIN PURPOSES p ON sr.PURPOSE_ID = p.PURPOSE_ID
    ORDER BY sr.CREATED_AT DESC
    LIMIT %s OFFSET %s
    """
    records = execute_query(query, (per_page, offset))
    
    # Calculate total pages
    total_pages = (total + per_page - 1) // per_page
    
    return render_template('staff/sit_in_records.html', 
                         records=records,
                         current_page=page,
                         total_pages=total_pages)

@staff_bp.route('/staff/profile', methods=['GET', 'POST'])
@login_required
@role_required('STAFF')
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
                    return redirect(url_for('staff.manage_profile'))
                    
                password_query = "UPDATE USERS SET PASSWORD = %s WHERE IDNO = %s"
                execute_query(password_query, (new_password, session['user_id']))
            
            flash('Profile updated successfully', 'success')
            return redirect(url_for('staff.manage_profile'))
            
        except Exception as e:
            flash(f'Error updating profile: {str(e)}', 'error')
            return redirect(url_for('staff.manage_profile'))
    
    # Get current user details
    user_query = "SELECT * FROM USERS WHERE IDNO = %s"
    user = execute_query(user_query, (session['user_id'],))[0]
    
    return render_template('staff/profile.html', user=user)

@staff_bp.route('/staff/feedback')
@login_required
@role_required('STAFF')
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
    WHERE {where_clause}
    """
    total = execute_query(count_query, params)[0]['total']
    
    # Calculate offset
    offset = (page - 1) * per_page
    
    # Get paginated feedbacks
    query = f"""
    SELECT 
        f.*,
        CONCAT(u.FIRSTNAME, ' ', u.LASTNAME) as STUDENT_NAME,
        l.LAB_NAME,
        p.PURPOSE_NAME,
        DATE_FORMAT(sr.CREATED_AT, '%Y-%m-%d %H:%i:%s') as SIT_IN_DATE
    FROM FEEDBACKS f
    JOIN SIT_IN_RECORDS sr ON f.RECORD_ID = sr.RECORD_ID
    JOIN USERS u ON f.USER_IDNO = u.IDNO
    JOIN LABORATORIES l ON sr.LAB_ID = l.LAB_ID
    JOIN PURPOSES p ON sr.PURPOSE_ID = p.PURPOSE_ID
    WHERE {where_clause}
    ORDER BY f.CREATED_AT DESC
    LIMIT %s OFFSET %s
    """
    feedbacks = execute_query(query, params + [per_page, offset])
    
    # Get labs for filter
    labs_query = "SELECT * FROM LABORATORIES WHERE STATUS = 'active' ORDER BY LAB_NAME"
    labs = execute_query(labs_query)
    
    # Calculate total pages
    total_pages = (total + per_page - 1) // per_page
    
    return render_template('staff/feedback.html',
                         feedbacks=feedbacks,
                         labs=labs,
                         page=page,
                         total_pages=total_pages)

@staff_bp.route('/download_report/<report_type>/<format>')
@login_required
def download_report(report_type, format):
    try:
        if report_type == 'lab_usage':
            query = """
                SELECT l.LAB_NAME, COUNT(s.RECORD_ID) as usage_count
                FROM LABS l
                LEFT JOIN SIT_IN_RECORDS s ON l.LAB_ID = s.LAB_ID
                GROUP BY l.LAB_NAME
                ORDER BY usage_count DESC
            """
            headers = ['Lab Name', 'Usage Count']
            filename = 'lab_usage_report'
            
        elif report_type == 'purpose_usage':
            query = """
                SELECT p.PURPOSE_NAME, COUNT(s.RECORD_ID) as usage_count
                FROM PURPOSES p
                LEFT JOIN SIT_IN_RECORDS s ON p.PURPOSE_ID = s.PURPOSE_ID
                GROUP BY p.PURPOSE_NAME
                ORDER BY usage_count DESC
            """
            headers = ['Purpose Name', 'Usage Count']
            filename = 'purpose_usage_report'
            
        elif report_type == 'sit_ins':
            # Get filter parameters from request
            lab_id = request.args.get('lab_id')
            purpose_id = request.args.get('purpose_id')
            start_date = request.args.get('start_date')
            end_date = request.args.get('end_date')
            
            # Build the query with filters
            query = """
                SELECT 
                    s.RECORD_ID,
                    CONCAT(u.FIRSTNAME, ' ', u.LASTNAME) as student_name,
                    u.COURSE,
                    u.YEAR,
                    l.LAB_NAME,
                    p.PURPOSE_NAME,
                    DATE_FORMAT(s.CREATED_AT, '%Y-%m-%d') as date,
                    TIME_FORMAT(s.TIME_IN, '%H:%i') as time_in,
                    TIME_FORMAT(s.TIME_OUT, '%H:%i') as time_out,
                    s.STATUS
                FROM SIT_IN_RECORDS s
                JOIN USERS u ON s.USER_IDNO = u.IDNO
                JOIN LABORATORIES l ON s.LAB_ID = l.LAB_ID
                JOIN PURPOSES p ON s.PURPOSE_ID = p.PURPOSE_ID
                WHERE 1=1
            """
            
            params = []
            if lab_id:
                query += " AND s.LAB_ID = %s"
                params.append(lab_id)
            if purpose_id:
                query += " AND s.PURPOSE_ID = %s"
                params.append(purpose_id)
            if start_date:
                query += " AND DATE(s.CREATED_AT) >= %s"
                params.append(start_date)
            if end_date:
                query += " AND DATE(s.CREATED_AT) <= %s"
                params.append(end_date)
                
            query += " ORDER BY s.CREATED_AT DESC"
            
            headers = ['Record ID', 'Student Name', 'Course', 'Year', 'Lab', 'Purpose', 'Date', 'Time In', 'Time Out', 'Status']
            filename = 'sit_in_records_report'
            
        elif report_type == 'feedback':
            query = """
                SELECT 
                    f.FEEDBACK_ID,
                    f.RECORD_ID,
                    CONCAT(u.FIRSTNAME, ' ', u.LASTNAME) as student_name,
                    l.LAB_NAME,
                    p.PURPOSE_NAME,
                    f.RATING,
                    f.COMMENT,
                    DATE_FORMAT(f.CREATED_AT, '%Y-%m-%d %H:%i') as created_at
                FROM FEEDBACKS f
                JOIN SIT_IN_RECORDS s ON f.RECORD_ID = s.RECORD_ID
                JOIN USERS u ON f.USER_IDNO = u.IDNO
                JOIN LABORATORIES l ON s.LAB_ID = l.LAB_ID
                JOIN PURPOSES p ON s.PURPOSE_ID = p.PURPOSE_ID
                ORDER BY f.CREATED_AT DESC
            """
            headers = ['Feedback ID', 'Record ID', 'Student Name', 'Lab', 'Purpose', 'Rating', 'Comment', 'Date']
            filename = 'feedback_report'
            
        else:
            return jsonify({'error': 'Invalid report type'}), 400
            
        # Execute query with parameters if needed
        if report_type == 'sit_ins':
            data = execute_query(query, params)
        else:
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
        print(f"Error generating report: {str(e)}")
        return jsonify({'error': str(e)}), 500

def generate_csv_report(data, headers, title):
    output = StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow(['University of Cebu Main Campus'])
    writer.writerow(['College of Computer Studies'])
    writer.writerow(['Computer Laboratory Sit-In Monitoring System'])
    writer.writerow([title])
    writer.writerow([])
    
    # Write column headers
    writer.writerow(headers)
    
    # Write data
    for row in data:
        writer.writerow([row[header] for header in headers])
    
    output.seek(0)
    return Response(
        output,
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename={title.lower().replace(" ", "_")}.csv'}
    )

def generate_pdf_report(data, headers, title):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    elements = []
    
    # Add header
    styles = getSampleStyleSheet()
    header_style = ParagraphStyle(
        'CustomHeader',
        parent=styles['Heading1'],
        fontSize=16,
        spaceAfter=30
    )
    
    elements.append(Paragraph('University of Cebu Main Campus', header_style))
    elements.append(Paragraph('College of Computer Studies', header_style))
    elements.append(Paragraph('Computer Laboratory Sit-In Monitoring System', header_style))
    elements.append(Paragraph(title, header_style))
    elements.append(Spacer(1, 20))
    
    # Create table
    table_data = [headers]
    for row in data:
        table_data.append([row[header] for header in headers])
    
    table = Table(table_data)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    
    elements.append(table)
    doc.build(elements)
    
    buffer.seek(0)
    return Response(
        buffer,
        mimetype='application/pdf',
        headers={'Content-Disposition': f'attachment; filename={title.lower().replace(" ", "_")}.pdf'}
    )

def generate_excel_report(data, headers, title):
    output = BytesIO()
    workbook = xlsxwriter.Workbook(output)
    worksheet = workbook.add_worksheet()
    
    # Add header
    header_format = workbook.add_format({
        'bold': True,
        'font_size': 14,
        'align': 'center',
        'valign': 'vcenter'
    })
    
    worksheet.merge_range('A1:H1', 'University of Cebu Main Campus', header_format)
    worksheet.merge_range('A2:H2', 'College of Computer Studies', header_format)
    worksheet.merge_range('A3:H3', 'Computer Laboratory Sit-In Monitoring System', header_format)
    worksheet.merge_range('A4:H4', title, header_format)
    
    # Add column headers
    header_format = workbook.add_format({
        'bold': True,
        'bg_color': '#4e73df',
        'font_color': 'white',
        'border': 1
    })
    
    for col, header in enumerate(headers):
        worksheet.write(5, col, header, header_format)
    
    # Add data
    data_format = workbook.add_format({
        'border': 1,
        'align': 'center'
    })
    
    for row, data_row in enumerate(data, start=6):
        for col, header in enumerate(headers):
            worksheet.write(row, col, data_row[header], data_format)
    
    # Adjust column widths
    for col, header in enumerate(headers):
        worksheet.set_column(col, col, max(len(header) + 2, 15))
    
    workbook.close()
    output.seek(0)
    
    return Response(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers={'Content-Disposition': f'attachment; filename={title.lower().replace(" ", "_")}.xlsx'}
    )

@staff_bp.route('/api/announcements')
@login_required
def get_announcements():
    try:
        print("\n=== Fetching Announcements ===")
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        
        print(f"Page: {page}, Per Page: {per_page}")
        
        # Get total count
        count_query = "SELECT COUNT(*) as total FROM ANNOUNCEMENTS WHERE STATUS = 'active'"
        total = execute_query(count_query)[0]['total']
        print(f"Total announcements: {total}")
        
        # Calculate offset
        offset = (page - 1) * per_page
        
        # Get paginated announcements
        query = """
        SELECT 
            a.ANNOUNCEMENT_ID,
            a.TITLE,
            a.CONTENT,
            DATE_FORMAT(a.DATE_POSTED, '%Y-%m-%d %H:%i') as DATE_POSTED,
            CONCAT(u.FIRSTNAME, ' ', u.LASTNAME) as posted_by
        FROM ANNOUNCEMENTS a
        JOIN USERS u ON a.POSTED_BY = u.IDNO
        WHERE a.STATUS = 'active'
        ORDER BY a.DATE_POSTED DESC
        LIMIT %s OFFSET %s
        """
        announcements = execute_query(query, (per_page, offset))
        print(f"Found {len(announcements)} announcements")
        print("Announcements:", announcements)
        
        response_data = {
            'announcements': announcements,
            'total': total,
            'page': page,
            'per_page': per_page
        }
        print("Response data:", response_data)
        
        return jsonify(response_data)
    except Exception as e:
        print(f"Error fetching announcements: {str(e)}")
        return jsonify({'error': str(e)}), 500

@staff_bp.context_processor
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

@staff_bp.route('/api/announcements/download')
@login_required
def download_announcements():
    try:
        format = request.args.get('format', 'csv')
        
        # Get all active announcements
        query = """
        SELECT 
            a.ANNOUNCEMENT_ID,
            a.TITLE,
            a.CONTENT,
            DATE_FORMAT(a.DATE_POSTED, '%Y-%m-%d %H:%i') as DATE_POSTED,
            CONCAT(u.FIRSTNAME, ' ', u.LASTNAME) as posted_by
        FROM ANNOUNCEMENTS a
        JOIN USERS u ON a.POSTED_BY = u.IDNO
        WHERE a.STATUS = 'active'
        ORDER BY a.DATE_POSTED DESC
        """
        announcements = execute_query(query)
        
        headers = ['ID', 'Title', 'Content', 'Date Posted', 'Posted By']
        filename = 'announcements_report'
        
        if format == 'csv':
            return generate_csv_report(announcements, headers, filename)
        elif format == 'pdf':
            return generate_pdf_report(announcements, headers, filename)
        elif format == 'excel':
            return generate_excel_report(announcements, headers, filename)
        else:
            return jsonify({'error': 'Invalid format'}), 400
            
    except Exception as e:
        print(f"Error generating announcements report: {str(e)}")
        return jsonify({'error': str(e)}), 500

@staff_bp.route('/resources')
@login_required
@role_required('STAFF')
def view_resources():
    # Get all enabled resources with their purposes
    query = """
    SELECT 
        r.*,
        p.PURPOSE_NAME,
        CONCAT(u.FIRSTNAME, ' ', u.LASTNAME) as CREATED_BY
    FROM LAB_RESOURCES r
    JOIN PURPOSES p ON r.PURPOSE_ID = p.PURPOSE_ID
    LEFT JOIN USERS u ON r.CREATED_BY = u.IDNO
    WHERE r.ENABLED = TRUE
    ORDER BY r.CREATED_AT DESC
    """
    resources = execute_query(query)
    
    return render_template('staff/resources.html', resources=resources)

@staff_bp.route('/resources/<int:resource_id>')
@login_required
@role_required('STAFF')
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

@staff_bp.route('/resources/add', methods=['GET', 'POST'])
@login_required
@role_required('STAFF')
def add_resource():
    purposes = execute_query("SELECT * FROM PURPOSES WHERE STATUS = 'active' ORDER BY PURPOSE_NAME")
    if request.method == 'POST':
        title = request.form['title']
        context = request.form['context']
        resource_type = request.form['resource_type']
        purpose_id = request.form['purpose_id']
        enabled = request.form.get('enabled', 'off') == 'on'
        resource_value = ''
        
        if resource_type in ['file', 'image'] and 'resource_file' in request.files:
            file = request.files['resource_file']
            if file and file.filename:
                filename = secure_filename(file.filename)
                save_path = os.path.join('static', 'resources', filename)
                file.save(save_path)
                resource_value = save_path
        elif resource_type == 'link':
            resource_value = request.form['resource_link']
        elif resource_type == 'text':
            resource_value = request.form['resource_text']
            
        resource_id = execute_query(
            """
            INSERT INTO LAB_RESOURCES (TITLE, CONTEXT, RESOURCE_TYPE, RESOURCE_VALUE, PURPOSE_ID, ENABLED, CREATED_BY)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (title, context, resource_type, resource_value, purpose_id, enabled, session['user_id'])
        )
        return redirect(url_for('staff.view_resources'))
    return render_template('staff/resource_form.html', purposes=purposes, resource=None)

@staff_bp.route('/resources/edit/<int:resource_id>', methods=['GET', 'POST'])
@login_required
@role_required('STAFF')
def edit_resource(resource_id):
    resource = execute_query("SELECT * FROM LAB_RESOURCES WHERE RESOURCE_ID=%s", (resource_id,))[0]
    purposes = execute_query("SELECT * FROM PURPOSES WHERE STATUS = 'active' ORDER BY PURPOSE_NAME")
    
    if request.method == 'POST':
        title = request.form['title']
        context = request.form['context']
        resource_type = request.form['resource_type']
        purpose_id = request.form['purpose_id']
        enabled = request.form.get('enabled', 'off') == 'on'
        resource_value = resource['RESOURCE_VALUE']
        
        if resource_type in ['file', 'image'] and 'resource_file' in request.files:
            file = request.files['resource_file']
            if file and file.filename:
                filename = secure_filename(file.filename)
                save_path = os.path.join('static', 'resources', filename)
                file.save(save_path)
                resource_value = save_path
        elif resource_type == 'link':
            resource_value = request.form['resource_link']
        elif resource_type == 'text':
            resource_value = request.form['resource_text']
            
        execute_query(
            """
            UPDATE LAB_RESOURCES 
            SET TITLE=%s, CONTEXT=%s, RESOURCE_TYPE=%s, RESOURCE_VALUE=%s, PURPOSE_ID=%s, ENABLED=%s 
            WHERE RESOURCE_ID=%s
            """,
            (title, context, resource_type, resource_value, purpose_id, enabled, resource_id)
        )
        return redirect(url_for('staff.view_resources'))
    return render_template('staff/resource_form.html', purposes=purposes, resource=resource)

@staff_bp.route('/resources/delete/<int:resource_id>', methods=['POST'])
@login_required
@role_required('STAFF')
def delete_resource(resource_id):
    execute_query("DELETE FROM LAB_RESOURCES WHERE RESOURCE_ID=%s", (resource_id,))
    return redirect(url_for('staff.view_resources'))

@staff_bp.route('/resources/toggle/<int:resource_id>', methods=['POST'])
@login_required
@role_required('STAFF')
def toggle_resource(resource_id):
    resource = execute_query("SELECT ENABLED FROM LAB_RESOURCES WHERE RESOURCE_ID=%s", (resource_id,))[0]
    new_status = not resource['ENABLED']
    execute_query("UPDATE LAB_RESOURCES SET ENABLED=%s WHERE RESOURCE_ID=%s", (new_status, resource_id))
    return redirect(url_for('staff.view_resources'))

@staff_bp.route('/top-participants')
@login_required
@role_required('STAFF')
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

    return render_template('staff/top_participants.html', 
                         top_participants=top_participants,
                         all_participants=all_participants)

@staff_bp.route('/point-history/<student_id>')
@login_required
@role_required('STAFF')
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

@staff_bp.route('/add-points', methods=['POST'])
@login_required
@role_required('STAFF')
def add_points():
    try:
        data = request.get_json()
        student_id = data.get('student_id')
        points = data.get('points')
        reason = data.get('reason')

        if not all([student_id, points, reason]):
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

        return jsonify({'success': True, 'message': 'Points added successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@staff_bp.route('/use-points', methods=['POST'])
@login_required
@role_required('STAFF')
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

@staff_bp.route('/lab-schedules')
@login_required
@role_required('STAFF')
def lab_schedules():
    try:
        # Get all active labs
        labs_query = "SELECT * FROM LABORATORIES WHERE STATUS = 'active'"
        labs = execute_query(labs_query)
        
        # Get all active purposes
        purposes_query = "SELECT * FROM PURPOSES WHERE STATUS = 'active'"
        purposes = execute_query(purposes_query)
        
        # Get all lab schedules
        schedules_query = """
        SELECT 
            ls.*,
            l.LAB_NAME,
            p.PURPOSE_NAME
        FROM LAB_SCHEDULES ls
        JOIN LABORATORIES l ON ls.LAB_ID = l.LAB_ID
        JOIN PURPOSES p ON ls.PURPOSE_ID = p.PURPOSE_ID
        WHERE ls.STATUS = 'active'
        ORDER BY ls.DAY_OF_WEEK, ls.START_TIME
        """
        schedules = execute_query(schedules_query)
        
        return render_template('staff/lab_schedules.html',
                             labs=labs,
                             purposes=purposes,
                             schedules=schedules)
    except Exception as e:
        print(f"Error in lab schedules: {str(e)}")
        flash('An error occurred while loading lab schedules', 'error')
        return redirect(url_for('staff.dashboard'))

@staff_bp.route('/reset-all-sit-ins', methods=['POST'])
@login_required
@role_required('STAFF')
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

@staff_bp.route('/reset-student-sit-ins/<idno>', methods=['POST'])
@login_required
@role_required('STAFF')
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

@staff_bp.route('/manage-students')
@login_required
@role_required('STAFF')
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
        
        return render_template('staff/manage_students.html', 
                             students=students,
                             current_page=page,
                             total_pages=total_pages)
    except Exception as e:
        print(f"Error in manage students: {str(e)}")
        flash('An error occurred while loading students', 'error')
        return redirect(url_for('staff.dashboard'))

@staff_bp.route('/lab-schedules/add', methods=['POST'])
@login_required
@role_required('STAFF')
def add_lab_schedule():
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['lab_id', 'purpose_id', 'day', 'start_time', 'end_time', 'status']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'success': False, 'message': f'{field} is required'}), 400
        
        # Check for schedule conflicts
        conflict_query = """
        SELECT COUNT(*) as count
        FROM LAB_SCHEDULES
        WHERE LAB_ID = %s
        AND DAY_OF_WEEK = %s
        AND (
            (START_TIME <= %s AND END_TIME > %s)
            OR (START_TIME < %s AND END_TIME >= %s)
            OR (START_TIME >= %s AND END_TIME <= %s)
        )
        AND STATUS = 'active'
        """
        conflict_result = execute_query(conflict_query, (
            data['lab_id'],
            data['day'],
            data['start_time'],
            data['start_time'],
            data['end_time'],
            data['end_time'],
            data['start_time'],
            data['end_time']
        ))
        
        if conflict_result[0]['count'] > 0:
            return jsonify({'success': False, 'message': 'Schedule conflict detected'}), 400
        
        # Insert new schedule
        insert_query = """
        INSERT INTO LAB_SCHEDULES (
            LAB_ID, PURPOSE_ID, DAY_OF_WEEK, START_TIME, END_TIME, STATUS
        ) VALUES (%s, %s, %s, %s, %s, %s)
        """
        execute_query(insert_query, (
            data['lab_id'],
            data['purpose_id'],
            data['day'],
            data['start_time'],
            data['end_time'],
            data['status']
        ))
        
        return jsonify({'success': True, 'message': 'Schedule added successfully'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@staff_bp.route('/lab-schedules/edit/<int:schedule_id>', methods=['PUT'])
@login_required
@role_required('STAFF')
def edit_lab_schedule(schedule_id):
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['lab_id', 'purpose_id', 'day', 'start_time', 'end_time', 'status']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'success': False, 'message': f'{field} is required'}), 400
        
        # Check for schedule conflicts (excluding current schedule)
        conflict_query = """
        SELECT COUNT(*) as count
        FROM LAB_SCHEDULES
        WHERE LAB_ID = %s
        AND DAY_OF_WEEK = %s
        AND SCHEDULE_ID != %s
        AND (
            (START_TIME <= %s AND END_TIME > %s)
            OR (START_TIME < %s AND END_TIME >= %s)
            OR (START_TIME >= %s AND END_TIME <= %s)
        )
        AND STATUS = 'active'
        """
        conflict_result = execute_query(conflict_query, (
            data['lab_id'],
            data['day'],
            schedule_id,
            data['start_time'],
            data['start_time'],
            data['end_time'],
            data['end_time'],
            data['start_time'],
            data['end_time']
        ))
        
        if conflict_result[0]['count'] > 0:
            return jsonify({'success': False, 'message': 'Schedule conflict detected'}), 400
        
        # Update schedule
        update_query = """
        UPDATE LAB_SCHEDULES
        SET LAB_ID = %s,
            PURPOSE_ID = %s,
            DAY_OF_WEEK = %s,
            START_TIME = %s,
            END_TIME = %s,
            STATUS = %s
        WHERE SCHEDULE_ID = %s
        """
        execute_query(update_query, (
            data['lab_id'],
            data['purpose_id'],
            data['day'],
            data['start_time'],
            data['end_time'],
            data['status'],
            schedule_id
        ))
        
        return jsonify({'success': True, 'message': 'Schedule updated successfully'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@staff_bp.route('/lab-schedules/delete/<int:schedule_id>', methods=['DELETE'])
@login_required
@role_required('STAFF')
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

@staff_bp.route('/lab-schedules/available-slots')
@login_required
@role_required('STAFF')
def get_available_slots():
    try:
        lab_id = request.args.get('lab_id')
        day_of_week = request.args.get('day_of_week')
        
        if not lab_id or not day_of_week:
            return jsonify({'error': 'Lab ID and day of week are required'}), 400
        
        # Get all time slots
        time_slots = [
            ('07:30:00', '08:30:00'),
            ('08:30:00', '09:30:00'),
            ('09:30:00', '10:30:00'),
            ('10:30:00', '11:30:00'),
            ('11:30:00', '12:30:00'),
            ('13:00:00', '14:00:00'),
            ('14:00:00', '15:00:00'),
            ('15:00:00', '16:00:00'),
            ('16:00:00', '17:00:00'),
            ('17:00:00', '18:00:00'),
            ('18:00:00', '19:00:00'),
            ('19:00:00', '20:00:00'),
            ('20:00:00', '21:00:00')
        ]
        
        # Get existing schedules for the lab and day
        existing_schedules_query = """
        SELECT START_TIME, END_TIME
        FROM LAB_SCHEDULES
        WHERE LAB_ID = %s
        AND DAY_OF_WEEK = %s
        AND STATUS = 'active'
        """
        existing_schedules = execute_query(existing_schedules_query, (lab_id, day_of_week))
        
        # Filter out occupied slots
        available_slots = []
        for start, end in time_slots:
            is_available = True
            for schedule in existing_schedules:
                if (start >= schedule['START_TIME'] and start < schedule['END_TIME']) or \
                   (end > schedule['START_TIME'] and end <= schedule['END_TIME']) or \
                   (start <= schedule['START_TIME'] and end >= schedule['END_TIME']):
                    is_available = False
                    break
            
            if is_available:
                # Format the time for display
                start_time = datetime.strptime(start, '%H:%M:%S').strftime('%I:%M %p')
                end_time = datetime.strptime(end, '%H:%M:%S').strftime('%I:%M %p')
                
                available_slots.append({
                    'start': start,
                    'end': end,
                    'formatted': f"{start_time} - {end_time}"
                })
        
        return jsonify(available_slots)
    except Exception as e:
        print(f"Error getting available slots: {str(e)}")
        return jsonify({'error': str(e)}), 500 