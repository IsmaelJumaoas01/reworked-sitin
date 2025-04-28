from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from db import execute_query
from datetime import datetime

sit_in_bp = Blueprint('sit_in', __name__)

@sit_in_bp.route('/sit-in/request', methods=['GET', 'POST'])
def request_sit_in():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    if request.method == 'POST':
        lab_id = request.form.get('lab_id')
        computer_id = request.form.get('computer_id')
        purpose_id = request.form.get('purpose_id')
        date = request.form.get('date')
        
        # Check if user has reached sit-in limit
        if session['user_type'] == 'STUDENT':
            limit_query = "SELECT SIT_IN_COUNT FROM SIT_IN_LIMITS WHERE USER_IDNO = %s"
            limit_result = execute_query(limit_query, (session['user_id'],))
            
            if limit_result and limit_result[0]['SIT_IN_COUNT'] >= 30:
                flash('You have reached the maximum number of sit-ins (30)', 'error')
                return redirect(url_for('sit_in.request_sit_in'))
        
        # Insert sit-in request
        query = """
        INSERT INTO SIT_IN_RECORDS (USER_IDNO, LAB_ID, COMPUTER_ID, PURPOSE_ID, DATE, STATUS)
        VALUES (%s, %s, %s, %s, %s, 'PENDING')
        """
        result = execute_query(query, (session['user_id'], lab_id, computer_id, purpose_id, date))
        
        if result:
            flash('Sit-in request submitted successfully', 'success')
            return redirect(url_for('student.dashboard'))
        else:
            flash('Failed to submit sit-in request', 'error')
    
    # Get available labs and purposes for the form
    labs_query = "SELECT * FROM LABORATORIES"
    purposes_query = "SELECT * FROM PURPOSES"
    
    labs = execute_query(labs_query)
    purposes = execute_query(purposes_query)
    
    return render_template('sit_in/request.html', labs=labs, purposes=purposes)

@sit_in_bp.route('/sit-in/history')
def sit_in_history():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    query = """
    SELECT sr.*, l.LAB_NAME, p.PURPOSE_NAME 
    FROM SIT_IN_RECORDS sr
    JOIN LABORATORIES l ON sr.LAB_ID = l.LAB_ID
    JOIN PURPOSES p ON sr.PURPOSE_ID = p.PURPOSE_ID
    WHERE sr.USER_IDNO = %s
    ORDER BY sr.DATE DESC
    """
    history = execute_query(query, (session['user_id'],))
    
    return render_template('sit_in/history.html', history=history)

@sit_in_bp.route('/sit-in/end/<int:record_id>')
def end_sit_in(record_id):
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    # Update session status
    query = "UPDATE SIT_IN_RECORDS SET SESSION = 'ENDED' WHERE RECORD_ID = %s AND USER_IDNO = %s"
    result = execute_query(query, (record_id, session['user_id']))
    
    if result:
        flash('Sit-in session ended successfully', 'success')
    else:
        flash('Failed to end sit-in session', 'error')
    
    return redirect(url_for('sit_in.sit_in_history')) 