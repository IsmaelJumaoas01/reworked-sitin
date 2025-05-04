from flask import Blueprint, render_template, request, jsonify, session, flash, redirect, url_for
from db import execute_query
from datetime import datetime, timedelta
from routes.auth import login_required, role_required

reservation_bp = Blueprint('reservation', __name__)

def check_and_convert_reservations():
    try:
        current_time = datetime.now()
        current_date = current_time.date()
        current_time_str = current_time.strftime('%H:%M:%S')

        # Update pending sit-in records that should be active now
        update_pending_query = """
        UPDATE SIT_IN_RECORDS s
        JOIN COMPUTERS c ON s.COMPUTER_ID = c.COMPUTER_ID
        SET 
            s.STATUS = 'APPROVED',
            s.SESSION = 'ON_GOING',
            c.STATUS = 'in_use'
        WHERE s.STATUS = 'PENDING'
        AND s.SESSION = 'PENDING'
        AND s.DATE <= %s
        AND s.TIME_IN <= %s
        """
        execute_query(update_pending_query, (current_date, current_time_str))

        # Get all approved reservations that should be active now
        query = """
        SELECT r.*, u.COURSE
        FROM RESERVATIONS r
        JOIN USERS u ON r.USER_IDNO = u.IDNO
        WHERE r.STATUS = 'APPROVED'
        AND r.RESERVATION_DATE <= %s
        AND r.TIME_IN <= %s
        AND NOT EXISTS (
            SELECT 1 FROM SIT_IN_RECORDS s 
            WHERE s.USER_IDNO = r.USER_IDNO 
            AND s.LAB_ID = r.LAB_ID 
            AND s.COMPUTER_ID = r.COMPUTER_ID 
            AND DATE(s.CREATED_AT) = r.RESERVATION_DATE
            AND s.TIME_IN = r.TIME_IN
        )
        """
        reservations = execute_query(query, (current_date, current_time_str))

        for reservation in reservations:
            # Start a sit-in session for this reservation
            insert_query = """
            INSERT INTO SIT_IN_RECORDS (
                USER_IDNO, LAB_ID, COMPUTER_ID, PURPOSE_ID,
                DATE, TIME_IN, STATUS, SESSION, USE_POINTS
            ) VALUES (%s, %s, %s, %s, %s, %s, 'APPROVED', 'ON_GOING', %s)
            """
            execute_query(insert_query, (
                reservation['USER_IDNO'],
                reservation['LAB_ID'],
                reservation['COMPUTER_ID'],
                reservation['PURPOSE_ID'],
                reservation['RESERVATION_DATE'],
                reservation['TIME_IN'],
                reservation.get('USE_POINTS', False)
            ))

            # Update computer status
            update_computer_query = """
            UPDATE COMPUTERS
            SET STATUS = 'in_use'
            WHERE COMPUTER_ID = %s
            """
            execute_query(update_computer_query, (reservation['COMPUTER_ID'],))

            # Update sit-in count for student
            update_count_query = """
            UPDATE SIT_IN_LIMITS 
            SET SIT_IN_COUNT = SIT_IN_COUNT + 1 
            WHERE USER_IDNO = %s
            """
            execute_query(update_count_query, (reservation['USER_IDNO'],))

            print(f"Converted reservation {reservation['RESERVATION_ID']} to sit-in record")

    except Exception as e:
        print(f"Error in check_and_convert_reservations: {str(e)}")

@reservation_bp.before_request
def before_request():
    # Run the conversion check before each request
    check_and_convert_reservations()

@reservation_bp.route('/student/reservation', methods=['GET', 'POST'])
@login_required
@role_required('STUDENT')
def student_reservation():
    if request.method == 'POST':
        try:
            lab_id = request.form.get('lab_id')
            computer_id = request.form.get('computer_id')
            purpose_id = request.form.get('purpose_id')
            date = request.form.get('date')
            time_in = request.form.get('time_in')
            use_points = request.form.get('use_points') == 'true'

            if not all([lab_id, computer_id, purpose_id, date, time_in]):
                flash('All fields are required', 'error')
                return redirect(url_for('reservation.student_reservation'))

            # Check if student already has a reservation for this time
            check_query = """
            SELECT COUNT(*) as count
            FROM RESERVATIONS
            WHERE USER_IDNO = %s
            AND RESERVATION_DATE = %s
            AND TIME_IN = %s
            AND STATUS != 'DENIED'
            """
            result = execute_query(check_query, (session['user_id'], date, time_in))

            if result[0]['count'] > 0:
                flash('You already have a reservation for this time', 'error')
                return redirect(url_for('reservation.student_reservation'))

            # Check student's points and sit-in count
            check_limits_query = """
            SELECT 
                COALESCE(sp.CURRENT_POINTS, 0) as current_points,
                COALESCE(sl.MAX_SIT_INS - sl.SIT_IN_COUNT, 0) as remaining_sessions
            FROM USERS u
            LEFT JOIN STUDENT_POINTS sp ON u.IDNO = sp.USER_IDNO
            LEFT JOIN SIT_IN_LIMITS sl ON u.IDNO = sl.USER_IDNO
            WHERE u.IDNO = %s
            """
            limits = execute_query(check_limits_query, (session['user_id'],))

            if not limits:
                flash('Unable to verify sit-in limits', 'error')
                return redirect(url_for('reservation.student_reservation'))

            current_points = limits[0]['current_points']
            remaining_sessions = limits[0]['remaining_sessions']

            if use_points:
                if current_points < 3:
                    flash('Not enough points. You need 3 points to make a reservation using points.', 'error')
                    return redirect(url_for('reservation.student_reservation'))
            else:
                if remaining_sessions <= 0:
                    flash('No remaining sit-in sessions. You can use points instead if you have enough.', 'error')
                    return redirect(url_for('reservation.student_reservation'))

            # Insert reservation
            insert_query = """
            INSERT INTO RESERVATIONS (
                USER_IDNO, LAB_ID, COMPUTER_ID, PURPOSE_ID,
                RESERVATION_DATE, TIME_IN, STATUS, USE_POINTS
            ) VALUES (%s, %s, %s, %s, %s, %s, 'PENDING', %s)
            """
            execute_query(insert_query, (
                session['user_id'], lab_id, computer_id, purpose_id,
                date, time_in, use_points
            ))

            flash('Reservation submitted successfully', 'success')
            return redirect(url_for('reservation.student_reservation_history'))

        except Exception as e:
            print(f"Error in student_reservation: {str(e)}")
            flash('An error occurred while submitting your reservation', 'error')
            return redirect(url_for('reservation.student_reservation'))

    # Get all active labs
    labs = execute_query("SELECT * FROM LABORATORIES WHERE STATUS = 'active'")
    
    # Get all active purposes
    purposes = execute_query("SELECT * FROM PURPOSES WHERE STATUS = 'active'")

    # Get student's points and sit-in count
    limits_query = """
    SELECT 
        COALESCE(sp.CURRENT_POINTS, 0) as current_points,
        COALESCE(sl.MAX_SIT_INS - sl.SIT_IN_COUNT, 0) as remaining_sessions
    FROM USERS u
    LEFT JOIN STUDENT_POINTS sp ON u.IDNO = sp.USER_IDNO
    LEFT JOIN SIT_IN_LIMITS sl ON u.IDNO = sl.USER_IDNO
    WHERE u.IDNO = %s
    """
    limits = execute_query(limits_query, (session['user_id'],))
    student_limits = limits[0] if limits else {'current_points': 0, 'remaining_sessions': 0}

    return render_template('student/reservation.html',
                         labs=labs,
                         purposes=purposes,
                         student_limits=student_limits)

@reservation_bp.route('/student/reservation/history', methods=['GET'])
@login_required
@role_required('STUDENT')
def student_reservation_history():
    try:
        query = """
        SELECT 
            r.*,
            l.LAB_NAME,
            p.PURPOSE_NAME,
            c.COMPUTER_NUMBER,
            DATE_FORMAT(r.CREATED_AT, '%Y-%m-%d %H:%i') as CREATED_TIME,
            DATE_FORMAT(r.TIME_IN, '%h:%i %p') as FORMATTED_TIME
        FROM RESERVATIONS r
        JOIN LABORATORIES l ON r.LAB_ID = l.LAB_ID
        JOIN PURPOSES p ON r.PURPOSE_ID = p.PURPOSE_ID
        JOIN COMPUTERS c ON r.COMPUTER_ID = c.COMPUTER_ID
        WHERE r.USER_IDNO = %s
        ORDER BY r.CREATED_AT DESC
        """
        reservations = execute_query(query, (session['user_id'],))
        return render_template('student/reservation_history.html', reservations=reservations)
    except Exception as e:
        print(f"Error in student reservation history: {str(e)}")
        flash('An error occurred while loading reservation history', 'error')
        return redirect(url_for('student.dashboard'))

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

@reservation_bp.route('/api/available-slots')
@login_required
@role_required('STUDENT')
def get_available_slots():
    try:
        lab_id = request.args.get('lab_id')
        date = request.args.get('date')
        
        if not lab_id or not date:
            return jsonify({'error': 'Lab ID and date are required'}), 400
            
        # Convert date to day of week
        selected_date = datetime.strptime(date, '%Y-%m-%d')
        day_of_week = selected_date.strftime('%A')
        
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
            ('21:00:00', '22:00:00')   # 1 hour
        ]
        
        # Get booked slots from lab schedules
        schedule_query = """
        SELECT START_TIME, END_TIME 
        FROM LAB_SCHEDULES 
        WHERE LAB_ID = %s 
        AND DAY_OF_WEEK = %s 
        AND STATUS = 'active'
        """
        booked_schedules = execute_query(schedule_query, (lab_id, day_of_week))
        
        # Get booked slots from reservations
        reservation_query = """
        SELECT TIME_IN 
        FROM RESERVATIONS 
        WHERE LAB_ID = %s 
        AND RESERVATION_DATE = %s
        AND STATUS != 'DENIED'
        """
        booked_reservations = execute_query(reservation_query, (lab_id, date))
        
        # Filter out booked slots
        available_slots = []
        for slot in all_slots:
            is_available = True
            slot_start = datetime.strptime(slot[0], '%H:%M:%S').time()
            
            # Check against lab schedules
            for schedule in booked_schedules:
                schedule_start = datetime.strptime(str(schedule['START_TIME']), '%H:%M:%S').time()
                schedule_end = datetime.strptime(str(schedule['END_TIME']), '%H:%M:%S').time()
                
                if slot_start >= schedule_start and slot_start < schedule_end:
                    is_available = False
                    break
            
            # Check against existing reservations
            for reservation in booked_reservations:
                reservation_time = datetime.strptime(str(reservation['TIME_IN']), '%H:%M:%S').time()
                if slot_start == reservation_time:
                    is_available = False
                    break
            
            # Check if time has already passed for today
            if selected_date.date() == datetime.now().date():
                current_time = datetime.now().time()
                if slot_start <= current_time:
                    is_available = False
            
            if is_available:
                available_slots.append({
                    'time': slot[0],
                    'formatted_time': datetime.strptime(slot[0], '%H:%M:%S').strftime('%I:%M %p')
                })
        
        return jsonify({
            'success': True,
            'available_slots': available_slots
        })
        
    except Exception as e:
        print(f"Error getting available slots: {str(e)}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500 