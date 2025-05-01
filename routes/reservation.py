from flask import Blueprint, render_template, request, jsonify, session
from db import execute_query
from datetime import datetime

reservation_bp = Blueprint('reservation', __name__)

@reservation_bp.route('/student/reservation', methods=['GET'])
def student_reservation():
    # Get available labs
    labs = execute_query("SELECT LAB_ID, LAB_NAME FROM LABORATORIES WHERE STATUS = 'active'")
    # Get available purposes
    purposes = execute_query("SELECT PURPOSE_ID, PURPOSE_NAME FROM PURPOSES WHERE STATUS = 'active'")
    return render_template('student/reservation.html', labs=labs, purposes=purposes)

@reservation_bp.route('/student/reservation/submit', methods=['POST'])
def submit_reservation():
    try:
        data = request.form
        user_idno = session.get('user_idno')
        
        # Validate required fields
        required_fields = ['lab_id', 'computer_id', 'purpose_id', 'date', 'time_in', 'time_out', 'program']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        # Convert date to day of week
        reservation_date = datetime.strptime(data['date'], '%Y-%m-%d')
        day_of_week = reservation_date.strftime('%A')
        
        # Check if the time slot conflicts with any lab schedule
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
            day_of_week,
            data['time_in'],
            data['time_in'],
            data['time_out'],
            data['time_out'],
            data['time_in'],
            data['time_out']
        ))
        
        if conflict_result[0]['count'] > 0:
            return jsonify({'error': 'The selected time slot conflicts with an existing lab schedule'}), 400
        
        # Check if computer is available for the selected time slot
        computer_query = """
        SELECT COUNT(*) as count
        FROM RESERVATIONS
        WHERE COMPUTER_ID = %s
        AND RESERVATION_DATE = %s
        AND (
            (TIME_IN <= %s AND TIME_OUT > %s)
            OR (TIME_IN < %s AND TIME_OUT >= %s)
            OR (TIME_IN >= %s AND TIME_OUT <= %s)
        )
        AND STATUS = 'APPROVED'
        """
        computer_result = execute_query(computer_query, (
            data['computer_id'],
            data['date'],
            data['time_in'],
            data['time_in'],
            data['time_out'],
            data['time_out'],
            data['time_in'],
            data['time_out']
        ))
        
        if computer_result[0]['count'] > 0:
            return jsonify({'error': 'The selected computer is already reserved for this time slot'}), 400
        
        # Validate time slot duration (minimum 30 minutes, maximum 2 hours)
        time_in = datetime.strptime(data['time_in'], '%H:%M')
        time_out = datetime.strptime(data['time_out'], '%H:%M')
        duration = (time_out - time_in).total_seconds() / 60  # duration in minutes
        
        if duration < 30:
            return jsonify({'error': 'Reservation must be at least 30 minutes long'}), 400
        if duration > 120:
            return jsonify({'error': 'Reservation cannot exceed 2 hours'}), 400
        
        # Insert reservation
        query = """
        INSERT INTO RESERVATIONS 
        (USER_IDNO, LAB_ID, COMPUTER_ID, PURPOSE_ID, RESERVATION_DATE, TIME_IN, TIME_OUT, PROGRAM)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        params = (
            user_idno,
            data['lab_id'],
            data['computer_id'],
            data['purpose_id'],
            data['date'],
            data['time_in'],
            data['time_out'],
            data['program']
        )
        
        execute_query(query, params)
        return jsonify({'message': 'Reservation submitted successfully'}), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@reservation_bp.route('/admin/reservations', methods=['GET'])
def admin_reservations():
    # Get all pending reservations
    query = """
    SELECT r.*, u.FIRSTNAME, u.LASTNAME, l.LAB_NAME, p.PURPOSE_NAME
    FROM RESERVATIONS r
    JOIN USERS u ON r.USER_IDNO = u.IDNO
    JOIN LABORATORIES l ON r.LAB_ID = l.LAB_ID
    JOIN PURPOSES p ON r.PURPOSE_ID = p.PURPOSE_ID
    WHERE r.STATUS = 'PENDING'
    ORDER BY r.CREATED_AT DESC
    """
    reservations = execute_query(query)
    return render_template('admin/reservations.html', reservations=reservations)

@reservation_bp.route('/admin/reservation/<int:reservation_id>/<action>', methods=['POST'])
def handle_reservation(reservation_id, action):
    try:
        if action not in ['approve', 'deny']:
            return jsonify({'error': 'Invalid action'}), 400
            
        status = 'APPROVED' if action == 'approve' else 'DENIED'
        
        # Update reservation status
        query = "UPDATE RESERVATIONS SET STATUS = %s WHERE RESERVATION_ID = %s"
        execute_query(query, (status, reservation_id))
        
        # If approved, create sit-in record
        if action == 'approve':
            # Get reservation details
            res_query = """
            SELECT * FROM RESERVATIONS WHERE RESERVATION_ID = %s
            """
            reservation = execute_query(res_query, (reservation_id,))[0]
            
            # Create sit-in record
            sit_in_query = """
            INSERT INTO SIT_IN_RECORDS 
            (USER_IDNO, LAB_ID, COMPUTER_ID, PURPOSE_ID, DATE, TIME_IN, TIME_OUT, STATUS)
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'APPROVED')
            """
            sit_in_params = (
                reservation['USER_IDNO'],
                reservation['LAB_ID'],
                reservation['COMPUTER_ID'],
                reservation['PURPOSE_ID'],
                reservation['RESERVATION_DATE'],
                reservation['TIME_IN'],
                reservation['TIME_OUT']
            )
            execute_query(sit_in_query, sit_in_params)
        
        return jsonify({'message': f'Reservation {action}d successfully'}), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@reservation_bp.route('/student/reservation/history', methods=['GET'])
def student_reservation_history():
    user_idno = session.get('user_idno')
    query = """
    SELECT r.*, l.LAB_NAME, p.PURPOSE_NAME
    FROM RESERVATIONS r
    JOIN LABORATORIES l ON r.LAB_ID = l.LAB_ID
    JOIN PURPOSES p ON r.PURPOSE_ID = p.PURPOSE_ID
    WHERE r.USER_IDNO = %s
    ORDER BY r.CREATED_AT DESC
    """
    reservations = execute_query(query, (user_idno,))
    return render_template('student/reservation_history.html', reservations=reservations)

@reservation_bp.route('/api/computers/<int:lab_id>', methods=['GET'])
def get_computers(lab_id):
    try:
        # Get available computers for the selected lab
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