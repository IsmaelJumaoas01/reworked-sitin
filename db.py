import mysql.connector
from mysql.connector import Error
import os
from dotenv import load_dotenv
import hashlib
import random
from datetime import datetime, timedelta
import time

# Load environment variables
load_dotenv()

def get_db_connection():
    try:
        connection = mysql.connector.connect(
            host=os.getenv('DB_HOST', 'localhost'),
            user=os.getenv('DB_USER', 'root'),
            password=os.getenv('DB_PASSWORD', ''),
            database=os.getenv('DB_NAME', 'sit_in_db')
        )
        return connection
    except Error as e:
        print(f"Error connecting to MySQL Database: {e}")
        return None

def execute_query(query, params=None):
    try:
        connection = get_db_connection()
        if connection is None:
            return None
        
        cursor = connection.cursor(dictionary=True)
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
            
        if query.strip().upper().startswith('SELECT'):
            result = cursor.fetchall()
        else:
            connection.commit()
            result = cursor.lastrowid
            
        cursor.close()
        connection.close()
        return result
    except Error as e:
        print(f"Error executing query: {e}")
        return None

def insert_default_data():
    try:
        print("\n=== Checking for existing data ===")
        
        # Check if any data exists
        check_query = """
        SELECT 
            (SELECT COUNT(*) FROM PURPOSES) as purpose_count,
            (SELECT COUNT(*) FROM LABORATORIES) as lab_count,
            (SELECT COUNT(*) FROM USERS WHERE USER_TYPE IN ('STAFF', 'STUDENT')) as user_count,
            (SELECT COUNT(*) FROM ANNOUNCEMENTS) as announcement_count
        """
        result = execute_query(check_query)
        
        if result and result[0]['purpose_count'] > 0:
            print("Default data already exists. Skipping insertion.")
            return
        
        print("No existing data found. Inserting default data...")
        
        # Insert default purposes
        print("\nInserting purposes...")
        purposes = [
            'C PROGRAMMING',
            'JAVA PROGRAMMING',
            'PYTHON',
            'C#',
            'DATABASE',
            'DIGITAL AND LOGIC DESIGN',
            'EMBEDDED SYSTEMS AND IOT',
            'SYSTEM INTEGRATION AND ARCHITECTURE',
            'COMPUTER APPLICATION',
            'PROJECT MANAGEMENT',
            'IT TRENDS',
            'TECHNOPRENEURSHIP',
            'CAPSTONE'
        ]
        
        for purpose in purposes:
            execute_query("""
                INSERT INTO PURPOSES (PURPOSE_NAME, STATUS)
                VALUES (%s, 'active')
            """, (purpose,))
        print(f"Inserted {len(purposes)} purposes")
        
        # Insert default laboratories
        print("\nInserting laboratories...")
        labs = [
            'LAB 524',
            'LAB 525',
            'LAB 528',
            'LAB 530',
            'LAB 542',
            'LAB 544',
            'LAB 517',
            'LAB 557'
        ]
        
        for lab in labs:
            # Insert lab
            execute_query("""
                INSERT INTO LABORATORIES (LAB_NAME, STATUS)
                VALUES (%s, 'active')
            """, (lab,))
            
            # Get lab ID
            lab_result = execute_query("SELECT LAB_ID FROM LABORATORIES WHERE LAB_NAME = %s", (lab,))
            if lab_result and len(lab_result) > 0:
                lab_id = lab_result[0]['LAB_ID']
                
                # Add 50 computers for each lab
                for i in range(1, 51):
                    execute_query("""
                        INSERT INTO COMPUTERS (LAB_ID, COMPUTER_NUMBER, STATUS)
                        VALUES (%s, %s, 'available')
                    """, (lab_id, i))
        print(f"Inserted {len(labs)} laboratories with 50 computers each")
        
        # Insert default staff users
        print("\nInserting staff users...")
        staff_users = [
            ('STAFF001', 'John', 'Doe', 'john.doe@example.com', 'staff123', 'BSIT', 4, 'STAFF'),
            ('STAFF002', 'Jane', 'Smith', 'jane.smith@example.com', 'staff123', 'BSCS', 4, 'STAFF')
        ]
        
        for staff in staff_users:
            hashed_password = hashlib.sha256(staff[4].encode()).hexdigest()
            execute_query("""
                INSERT INTO USERS (IDNO, FIRSTNAME, LASTNAME, EMAIL, PASSWORD, COURSE, YEAR, USER_TYPE, STATUS)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'active')
            """, staff[:4] + (hashed_password,) + staff[5:])
        print(f"Inserted {len(staff_users)} staff users")
        
        # Insert default student users with diverse courses
        print("\nInserting student users...")
        student_users = [
            # BSIT Students (30 max sit-ins)
            ('20230001', 'Alice', 'Johnson', 'alice.j@example.com', 'student123', 'BSIT', 3, 'STUDENT'),
            ('20230002', 'Bob', 'Williams', 'bob.w@example.com', 'student123', 'BSIT', 2, 'STUDENT'),
            ('20230003', 'Carol', 'Brown', 'carol.b@example.com', 'student123', 'BSIT', 4, 'STUDENT'),
            
            # BSCS Students (30 max sit-ins)
            ('20230004', 'David', 'Miller', 'david.m@example.com', 'student123', 'BSCS', 1, 'STUDENT'),
            ('20230005', 'Eve', 'Davis', 'eve.d@example.com', 'student123', 'BSCS', 2, 'STUDENT'),
            
            # BSA Students (15 max sit-ins)
            ('20230006', 'Frank', 'Wilson', 'frank.w@example.com', 'student123', 'BSA', 3, 'STUDENT'),
            ('20230007', 'Grace', 'Taylor', 'grace.t@example.com', 'student123', 'BSA', 4, 'STUDENT'),
            
            # BSCE Students (15 max sit-ins)
            ('20230008', 'Henry', 'Anderson', 'henry.a@example.com', 'student123', 'BSCE', 2, 'STUDENT'),
            ('20230009', 'Ivy', 'Martinez', 'ivy.m@example.com', 'student123', 'BSCE', 3, 'STUDENT'),
            
            # BSEE Students (15 max sit-ins)
            ('20230010', 'Jack', 'Robinson', 'jack.r@example.com', 'student123', 'BSEE', 1, 'STUDENT'),
            ('20230011', 'Kelly', 'Clark', 'kelly.c@example.com', 'student123', 'BSEE', 4, 'STUDENT'),
            
            # BSCHE Students (15 max sit-ins)
            ('20230012', 'Liam', 'Rodriguez', 'liam.r@example.com', 'student123', 'BSCHE', 2, 'STUDENT'),
            ('20230013', 'Mia', 'Lewis', 'mia.l@example.com', 'student123', 'BSCHE', 3, 'STUDENT'),
            
            # BSCHEM Students (15 max sit-ins)
            ('20230014', 'Noah', 'Lee', 'noah.l@example.com', 'student123', 'BSCHEM', 1, 'STUDENT'),
            ('20230015', 'Olivia', 'Walker', 'olivia.w@example.com', 'student123', 'BSCHEM', 4, 'STUDENT')
        ]
        
        for student in student_users:
            hashed_password = hashlib.sha256(student[4].encode()).hexdigest()
            execute_query("""
                INSERT INTO USERS (IDNO, FIRSTNAME, LASTNAME, EMAIL, PASSWORD, COURSE, YEAR, USER_TYPE, STATUS)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'active')
            """, student[:4] + (hashed_password,) + student[5:])
            
            # Set sit-in limits for students based on their course
            max_sit_ins = 30 if student[5] in ['BSIT', 'BSCS'] else 15
            execute_query("""
                INSERT INTO SIT_IN_LIMITS (USER_IDNO, SIT_IN_COUNT, MAX_SIT_INS)
                VALUES (%s, 0, %s)
            """, (student[0], max_sit_ins))
        print(f"Inserted {len(student_users)} student users with appropriate sit-in limits")
        
        # Insert default announcements
        print("\nInserting announcements...")
        announcements = [
            ('Welcome to the New Semester', 'Welcome to the new semester! Please check your schedules and prepare for your classes.', 'STAFF001'),
            ('Laboratory Guidelines', 'Please follow the laboratory guidelines and maintain cleanliness in the computer labs.', 'STAFF002'),
            ('Sit-In System Update', 'The sit-in management system has been updated with new features. Please check the user guide for details.', 'STAFF001')
        ]
        
        for announcement in announcements:
            execute_query("""
                INSERT INTO ANNOUNCEMENTS (TITLE, CONTENT, POSTED_BY, STATUS)
                VALUES (%s, %s, %s, 'active')
            """, announcement)
        print(f"Inserted {len(announcements)} announcements")
        
        # Insert default resources for each purpose
        print("\nInserting default resources...")
        try:
            # First check if admin user exists
            admin_check = execute_query("SELECT IDNO FROM USERS WHERE IDNO = 'ADMIN001'")
            if not admin_check:
                print("Warning: Admin user not found. Creating default admin...")
                execute_query("""
                    INSERT INTO USERS (IDNO, LASTNAME, FIRSTNAME, COURSE, YEAR, EMAIL, PASSWORD, USER_TYPE)
                    VALUES ('ADMIN001', 'Admin', 'System', 'N/A', 0, 'admin@system.com', 
                           SHA2('admin123', 256), 'ADMIN')
                """)
            
            # Set a shorter timeout for resource insertion
            connection = get_db_connection()
            if connection:
                cursor = connection.cursor()
                cursor.execute("SET SESSION innodb_lock_wait_timeout = 5")  # 5 second timeout
                cursor.close()
                connection.close()
            
            default_resources = [
                ('C Programming Basics', 'Introduction to C programming language', 'link', 'https://www.tutorialspoint.com/cprogramming/index.htm', 'C PROGRAMMING'),
                ('C Programming Examples', 'Collection of C programming examples', 'link', 'https://www.programiz.com/c-programming/examples', 'C PROGRAMMING'),
                ('Java Tutorial', 'Complete Java programming tutorial', 'link', 'https://www.w3schools.com/java/', 'JAVA PROGRAMMING'),
                ('Java Examples', 'Java programming examples and exercises', 'link', 'https://www.javatpoint.com/java-programs', 'JAVA PROGRAMMING'),
                ('Python Documentation', 'Official Python documentation', 'link', 'https://docs.python.org/3/', 'PYTHON'),
                ('Python Tutorial', 'Python programming tutorial', 'link', 'https://www.python.org/about/gettingstarted/', 'PYTHON'),
                ('C# Documentation', 'Microsoft C# documentation', 'link', 'https://docs.microsoft.com/en-us/dotnet/csharp/', 'C#'),
                ('C# Tutorial', 'C# programming tutorial', 'link', 'https://www.tutorialspoint.com/csharp/index.htm', 'C#'),
                ('SQL Tutorial', 'SQL database tutorial', 'link', 'https://www.w3schools.com/sql/', 'DATABASE'),
                ('Database Design', 'Database design principles', 'link', 'https://www.tutorialspoint.com/dbms/index.htm', 'DATABASE'),
                ('Digital Logic Tutorial', 'Digital logic design tutorial', 'link', 'https://www.tutorialspoint.com/digital_circuits/index.htm', 'DIGITAL AND LOGIC DESIGN'),
                ('Logic Gates', 'Understanding logic gates', 'link', 'https://www.electronics-tutorials.ws/logic/logic_1.html', 'DIGITAL AND LOGIC DESIGN'),
                ('Embedded Systems Guide', 'Introduction to embedded systems', 'link', 'https://www.tutorialspoint.com/embedded_systems/index.htm', 'EMBEDDED SYSTEMS AND IOT'),
                ('IoT Basics', 'Internet of Things fundamentals', 'link', 'https://www.tutorialspoint.com/internet_of_things/index.htm', 'EMBEDDED SYSTEMS AND IOT'),
                ('System Architecture', 'System architecture principles', 'link', 'https://www.tutorialspoint.com/software_architecture_design/index.htm', 'SYSTEM INTEGRATION AND ARCHITECTURE'),
                ('Integration Patterns', 'System integration patterns', 'link', 'https://www.enterpriseintegrationpatterns.com/', 'SYSTEM INTEGRATION AND ARCHITECTURE'),
                ('Office Applications', 'Microsoft Office tutorials', 'link', 'https://support.microsoft.com/en-us/office', 'COMPUTER APPLICATION'),
                ('Productivity Tools', 'Productivity software guide', 'link', 'https://www.tutorialspoint.com/computer_fundamentals/index.htm', 'COMPUTER APPLICATION'),
                ('Project Management Guide', 'Project management fundamentals', 'link', 'https://www.pmi.org/learning/library', 'PROJECT MANAGEMENT'),
                ('Agile Methodology', 'Agile project management', 'link', 'https://www.agilealliance.org/agile101/', 'PROJECT MANAGEMENT'),
                ('Tech Trends', 'Latest IT trends and innovations', 'link', 'https://www.gartner.com/en/information-technology/insights/top-technology-trends', 'IT TRENDS'),
                ('Future of IT', 'Future technology predictions', 'link', 'https://www.mckinsey.com/business-functions/mckinsey-digital/our-insights', 'IT TRENDS'),
                ('Startup Guide', 'Guide to starting a tech business', 'link', 'https://www.startupgrind.com/blog/', 'TECHNOPRENEURSHIP'),
                ('Tech Entrepreneurship', 'Technology entrepreneurship resources', 'link', 'https://www.entrepreneur.com/technology', 'TECHNOPRENEURSHIP'),
                ('Capstone Project Guide', 'Guide to capstone projects', 'link', 'https://www.capstone.org/', 'CAPSTONE'),
                ('Project Planning', 'Project planning and execution', 'link', 'https://www.projectmanagement.com/', 'CAPSTONE')
            ]
            
            # Get all purposes first to avoid repeated queries
            purposes_query = "SELECT PURPOSE_ID, PURPOSE_NAME FROM PURPOSES WHERE STATUS = 'active'"
            purposes = execute_query(purposes_query)
            if not purposes:
                print("Error: No active purposes found. Cannot insert resources.")
                return
                
            purpose_map = {p['PURPOSE_NAME']: p['PURPOSE_ID'] for p in purposes}
            
            # Insert resources with timeout handling
            for title, context, resource_type, resource_value, purpose_name in default_resources:
                try:
                    if purpose_name not in purpose_map:
                        print(f"Warning: Purpose '{purpose_name}' not found. Skipping resource.")
                        continue
                        
                    purpose_id = purpose_map[purpose_name]
                    execute_query("""
                        INSERT INTO LAB_RESOURCES 
                        (TITLE, CONTEXT, RESOURCE_TYPE, RESOURCE_VALUE, PURPOSE_ID, CREATED_BY, ENABLED)
                        VALUES (%s, %s, %s, %s, %s, 'ADMIN001', TRUE)
                    """, (title, context, resource_type, resource_value, purpose_id))
                    print(f"Inserted: {title}")
                except Exception as e:
                    print(f"Error inserting resource '{title}': {str(e)}")
                    continue
                
                # Add a small delay between insertions
                time.sleep(0.1)
            
            print("Default resources inserted successfully!")
        except Exception as e:
            print(f"\nError in resource insertion: {str(e)}")
            print("Continuing with other initialization...")
        
        print("\nDefault data inserted successfully!")
    except Exception as e:
        print(f"\nError inserting default data: {str(e)}")
        raise e

def insert_sample_sit_in_records():
    try:
        print("\n=== Checking for Sample Data ===")
        
        # Check if any sample data exists
        check_query = """
        SELECT 
            (SELECT COUNT(*) FROM SIT_IN_RECORDS) as sit_in_count,
            (SELECT COUNT(*) FROM FEEDBACKS) as feedback_count,
            (SELECT COUNT(*) FROM RESERVATIONS) as reservation_count
        """
        result = execute_query(check_query)
        
        if result and (result[0]['sit_in_count'] > 0 or result[0]['feedback_count'] > 0 or result[0]['reservation_count'] > 0):
            print("Sample data already exists. Skipping insertion.")
            return
            
        print("No sample data found. Inserting sample records...")
        
        # First, get some sample data from existing tables
        users_query = "SELECT IDNO FROM USERS WHERE USER_TYPE = 'STUDENT' LIMIT 5"
        labs_query = "SELECT LAB_ID FROM LABORATORIES WHERE STATUS = 'active' LIMIT 3"
        purposes_query = "SELECT PURPOSE_ID FROM PURPOSES WHERE STATUS = 'active'"
        computers_query = "SELECT COMPUTER_ID FROM COMPUTERS WHERE STATUS = 'available' LIMIT 5"
        
        users = execute_query(users_query)
        labs = execute_query(labs_query)
        purposes = execute_query(purposes_query)
        computers = execute_query(computers_query)
        
        if not all([users, labs, purposes, computers]):
            print("Error: Could not get required sample data")
            return
        
        # Define time slots (1-hour intervals)
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
        
        # Generate dates for the last 7 days and next 7 days
        past_dates = [(datetime.now() - timedelta(days=i)).date() for i in range(7)]
        future_dates = [(datetime.now() + timedelta(days=i)).date() for i in range(1, 8)]
        
        # Insert sit-in records and feedbacks for past dates
        for date in past_dates:
            for user in users:
                # Randomly select lab, purpose, and computer
                lab = random.choice(labs)
                purpose = random.choice(purposes)
                computer = random.choice(computers)
                
                # Randomly select time slot
                time_slot = random.choice(time_slots)
                time_in = time_slot[0]
                time_out = time_slot[1]
                
                # Check if student points record exists, if not create it
                points_check = execute_query("SELECT POINT_ID FROM STUDENT_POINTS WHERE USER_IDNO = %s", (user['IDNO'],))
                if not points_check:
                    execute_query("""
                        INSERT INTO STUDENT_POINTS (USER_IDNO, CURRENT_POINTS, TOTAL_POINTS)
                        VALUES (%s, 0, 0)
                    """, (user['IDNO'],))
                
                # Insert sit-in record
                sit_in_query = """
                INSERT INTO SIT_IN_RECORDS (
                    USER_IDNO, LAB_ID, COMPUTER_ID, PURPOSE_ID,
                    DATE, TIME_IN, TIME_OUT, STATUS, SESSION,
                    USE_POINTS, CREATED_AT
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, 'COMPLETED', 'COMPLETED',
                    FALSE, %s)
                """
                created_at = datetime.combine(date, datetime.strptime(time_in, '%H:%M:%S').time())
                execute_query(sit_in_query, (
                    user['IDNO'],
                    lab['LAB_ID'],
                    computer['COMPUTER_ID'],
                    purpose['PURPOSE_ID'],
                    date,
                    time_in,
                    time_out,
                    created_at
                ))
                
                # Get the inserted record ID
                record_query = """
                SELECT RECORD_ID FROM SIT_IN_RECORDS 
                WHERE USER_IDNO = %s AND DATE = %s AND TIME_IN = %s
                ORDER BY CREATED_AT DESC LIMIT 1
                """
                record = execute_query(record_query, (user['IDNO'], date, time_in))
                
                if record:
                    # Insert feedback for this sit-in record
                    feedback_query = """
                    INSERT INTO FEEDBACKS (
                        RECORD_ID, USER_IDNO, RATING, COMMENT
                    ) VALUES (%s, %s, %s, %s)
                    """
                    rating = random.randint(1, 5)
                    comments = [
                        "Great experience!",
                        "The lab was well-maintained.",
                        "Good facilities.",
                        "Could use some improvements.",
                        "Excellent service!"
                    ]
                    execute_query(feedback_query, (
                        record[0]['RECORD_ID'],
                        user['IDNO'],
                        rating,
                        random.choice(comments)
                    ))
                    
                    # Update computer status
                    update_computer_query = """
                    UPDATE COMPUTERS
                    SET STATUS = 'available'
                    WHERE COMPUTER_ID = %s
                    """
                    execute_query(update_computer_query, (computer['COMPUTER_ID'],))
                    
                    # Update sit-in count for student
                    update_count_query = """
                    UPDATE SIT_IN_LIMITS 
                    SET SIT_IN_COUNT = SIT_IN_COUNT + 1 
                    WHERE USER_IDNO = %s
                    """
                    execute_query(update_count_query, (user['IDNO'],))
                    
                    # Add points for completed session
                    points_query = """
                    UPDATE STUDENT_POINTS 
                    SET CURRENT_POINTS = CURRENT_POINTS + 1,
                        TOTAL_POINTS = TOTAL_POINTS + 1
                    WHERE USER_IDNO = %s
                    """
                    execute_query(points_query, (user['IDNO'],))
                    
                    # Add to point history
                    history_query = """
                    INSERT INTO POINT_HISTORY (USER_IDNO, POINTS_CHANGE, REASON, ADDED_BY)
                    VALUES (%s, 1, 'Completed sit-in session', %s)
                    """
                    execute_query(history_query, (user['IDNO'], user['IDNO']))
        
        # Insert sample reservations for future dates (ensuring no multiple pending reservations)
        print("\n=== Inserting Sample Reservations ===")
        for user in users:
            # Only create one pending reservation per student
            has_pending = False
            
            for date in future_dates:
                if has_pending:
                    break
                    
                # Randomly select lab, purpose, and computer
                lab = random.choice(labs)
                purpose = random.choice(purposes)
                computer = random.choice(computers)
                
                # Randomly select time slot
                time_slot = random.choice(time_slots)
                time_in = time_slot[0]
                
                # Randomly decide if this will be a pending or approved reservation
                status = random.choice(['PENDING', 'APPROVED'])
                use_points = random.choice([True, False])
                
                # If status is PENDING, mark that this student now has a pending reservation
                if status == 'PENDING':
                    has_pending = True
                
                # Check if student has enough points if using points
                if use_points:
                    points_check = execute_query("""
                        SELECT CURRENT_POINTS 
                        FROM STUDENT_POINTS 
                        WHERE USER_IDNO = %s AND CURRENT_POINTS >= 3
                    """, (user['IDNO'],))
                    if not points_check:
                        use_points = False
                
                # Insert reservation
                reservation_query = """
                INSERT INTO RESERVATIONS (
                    USER_IDNO, LAB_ID, COMPUTER_ID, PURPOSE_ID,
                    RESERVATION_DATE, TIME_IN, STATUS, USE_POINTS,
                    CREATED_AT
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                created_at = datetime.combine(date, datetime.strptime(time_in, '%H:%M:%S').time())
                execute_query(reservation_query, (
                    user['IDNO'],
                    lab['LAB_ID'],
                    computer['COMPUTER_ID'],
                    purpose['PURPOSE_ID'],
                    date,
                    time_in,
                    status,
                    use_points,
                    created_at
                ))
                
                # If reservation is approved, create corresponding sit-in record
                if status == 'APPROVED':
                    sit_in_query = """
                    INSERT INTO SIT_IN_RECORDS (
                        USER_IDNO, LAB_ID, COMPUTER_ID, PURPOSE_ID,
                        DATE, TIME_IN, STATUS, SESSION, USE_POINTS,
                        CREATED_AT
                    ) VALUES (%s, %s, %s, %s, %s, %s, 'PENDING', 'PENDING',
                        %s, %s)
                    """
                    execute_query(sit_in_query, (
                        user['IDNO'],
                        lab['LAB_ID'],
                        computer['COMPUTER_ID'],
                        purpose['PURPOSE_ID'],
                        date,
                        time_in,
                        use_points,
                        created_at
                    ))
                    
                    # If using points, deduct them
                    if use_points:
                        points_query = """
                        UPDATE STUDENT_POINTS 
                        SET CURRENT_POINTS = CURRENT_POINTS - 3
                        WHERE USER_IDNO = %s
                        """
                        execute_query(points_query, (user['IDNO'],))
                        
                        # Add to point history
                        history_query = """
                        INSERT INTO POINT_HISTORY (USER_IDNO, POINTS_CHANGE, REASON, ADDED_BY)
                        VALUES (%s, -3, 'Points used for reservation', %s)
                        """
                        execute_query(history_query, (user['IDNO'], user['IDNO']))
                    else:
                        # Increment sit-in count
                        update_count_query = """
                        UPDATE SIT_IN_LIMITS 
                        SET SIT_IN_COUNT = SIT_IN_COUNT + 1 
                        WHERE USER_IDNO = %s
                        """
                        execute_query(update_count_query, (user['IDNO'],))
        
        print("Sample sit-in records, feedbacks, and reservations inserted successfully!")
    except Exception as e:
        print(f"Error inserting sample data: {str(e)}")
        raise e

def init_db():
    try:
        connection = get_db_connection()
        if connection is None:
            return False
        
        cursor = connection.cursor(dictionary=True)
        
        # Create tables if they don't exist
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS USERS (
                IDNO VARCHAR(20) PRIMARY KEY,
                LASTNAME VARCHAR(50) NOT NULL,
                FIRSTNAME VARCHAR(50) NOT NULL,
                MIDDLENAME VARCHAR(50),
                COURSE VARCHAR(10) NOT NULL,
                YEAR INT NOT NULL,
                EMAIL VARCHAR(100) UNIQUE NOT NULL,
                PASSWORD VARCHAR(255) NOT NULL,
                USER_TYPE ENUM('ADMIN', 'STAFF', 'STUDENT') NOT NULL,
                STATUS ENUM('active', 'inactive') DEFAULT 'active',
                PROFILE_PICTURE MEDIUMBLOB,
                CREATED_AT TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS LABORATORIES (
                LAB_ID INT AUTO_INCREMENT PRIMARY KEY,
                LAB_NAME VARCHAR(50) NOT NULL,
                STATUS ENUM('active', 'inactive') DEFAULT 'active',
                CREATED_AT TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS COMPUTERS (
                COMPUTER_ID INT AUTO_INCREMENT PRIMARY KEY,
                LAB_ID INT NOT NULL,
                COMPUTER_NUMBER INT NOT NULL,
                STATUS ENUM('available', 'in_use', 'maintenance') DEFAULT 'available',
                CREATED_AT TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (LAB_ID) REFERENCES LABORATORIES(LAB_ID) ON DELETE CASCADE,
                UNIQUE KEY unique_computer (LAB_ID, COMPUTER_NUMBER)
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS PURPOSES (
                PURPOSE_ID INT AUTO_INCREMENT PRIMARY KEY,
                PURPOSE_NAME VARCHAR(100) NOT NULL,
                STATUS ENUM('active', 'inactive') DEFAULT 'active',
                CREATED_AT TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS PROFESSORS (
                PROFESSOR_ID INT AUTO_INCREMENT PRIMARY KEY,
                FIRST_NAME VARCHAR(50) NOT NULL,
                LAST_NAME VARCHAR(50) NOT NULL,
                MIDDLE_NAME VARCHAR(50),
                STATUS ENUM('active', 'inactive') DEFAULT 'active',
                CREATED_AT TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UPDATED_AT TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS LAB_SCHEDULES (
                SCHEDULE_ID INT AUTO_INCREMENT PRIMARY KEY,
                LAB_ID INT NOT NULL,
                PURPOSE_ID INT NOT NULL,
                PROFESSOR_ID INT NOT NULL,
                DAY_OF_WEEK ENUM('Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday') NOT NULL,
                START_TIME TIME NOT NULL,
                END_TIME TIME NOT NULL,
                STATUS ENUM('active', 'inactive') DEFAULT 'active',
                CREATED_AT TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (LAB_ID) REFERENCES LABORATORIES(LAB_ID) ON DELETE CASCADE,
                FOREIGN KEY (PURPOSE_ID) REFERENCES PURPOSES(PURPOSE_ID) ON DELETE CASCADE,
                FOREIGN KEY (PROFESSOR_ID) REFERENCES PROFESSORS(PROFESSOR_ID) ON DELETE CASCADE
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS SIT_IN_RECORDS (
                RECORD_ID INT AUTO_INCREMENT PRIMARY KEY,
                USER_IDNO VARCHAR(20) NOT NULL,
                LAB_ID INT NOT NULL,
                COMPUTER_ID INT NOT NULL,
                PURPOSE_ID INT NOT NULL,
                DATE DATE NOT NULL,
                TIME_IN TIME NOT NULL,
                TIME_OUT TIME,
                STATUS ENUM('PENDING', 'APPROVED', 'DENIED', 'COMPLETED') DEFAULT 'PENDING',
                SESSION ENUM('ON_GOING', 'COMPLETED') DEFAULT 'ON_GOING',
                USE_POINTS BOOLEAN DEFAULT FALSE,
                CREATED_AT TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (USER_IDNO) REFERENCES USERS(IDNO) ON DELETE CASCADE,
                FOREIGN KEY (LAB_ID) REFERENCES LABORATORIES(LAB_ID) ON DELETE CASCADE,
                FOREIGN KEY (COMPUTER_ID) REFERENCES COMPUTERS(COMPUTER_ID) ON DELETE CASCADE,
                FOREIGN KEY (PURPOSE_ID) REFERENCES PURPOSES(PURPOSE_ID) ON DELETE CASCADE
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS RESERVATIONS (
                RESERVATION_ID INT AUTO_INCREMENT PRIMARY KEY,
                USER_IDNO VARCHAR(20) NOT NULL,
                LAB_ID INT NOT NULL,
                COMPUTER_ID INT NOT NULL,
                PURPOSE_ID INT NOT NULL,
                RESERVATION_DATE DATE NOT NULL,
                TIME_IN TIME NOT NULL,
                STATUS ENUM('PENDING', 'APPROVED', 'DENIED') DEFAULT 'PENDING',
                USE_POINTS BOOLEAN DEFAULT FALSE,
                CREATED_AT TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UPDATED_AT TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (USER_IDNO) REFERENCES USERS(IDNO),
                FOREIGN KEY (LAB_ID) REFERENCES LABORATORIES(LAB_ID),
                FOREIGN KEY (COMPUTER_ID) REFERENCES COMPUTERS(COMPUTER_ID),
                FOREIGN KEY (PURPOSE_ID) REFERENCES PURPOSES(PURPOSE_ID)
            )
        """)
        
        # Add points system tables
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS STUDENT_POINTS (
                POINT_ID INT AUTO_INCREMENT PRIMARY KEY,
                USER_IDNO VARCHAR(20) NOT NULL,
                CURRENT_POINTS INT DEFAULT 0,
                TOTAL_POINTS INT DEFAULT 0,
                LAST_UPDATED TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (USER_IDNO) REFERENCES USERS(IDNO)
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS POINT_HISTORY (
                HISTORY_ID INT AUTO_INCREMENT PRIMARY KEY,
                USER_IDNO VARCHAR(20) NOT NULL,
                POINTS_CHANGE INT NOT NULL,
                REASON VARCHAR(255) NOT NULL,
                ADDED_BY VARCHAR(20) NOT NULL,
                CREATED_AT TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (USER_IDNO) REFERENCES USERS(IDNO),
                FOREIGN KEY (ADDED_BY) REFERENCES USERS(IDNO)
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS POINT_REDEMPTIONS (
                REDEMPTION_ID INT AUTO_INCREMENT PRIMARY KEY,
                USER_IDNO VARCHAR(20) NOT NULL,
                SIT_IN_RECORD_ID INT NOT NULL,
                POINTS_USED INT NOT NULL,
                CREATED_AT TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (USER_IDNO) REFERENCES USERS(IDNO),
                FOREIGN KEY (SIT_IN_RECORD_ID) REFERENCES SIT_IN_RECORDS(RECORD_ID)
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS SIT_IN_LIMITS (
                LIMIT_ID INT AUTO_INCREMENT PRIMARY KEY,
                USER_IDNO VARCHAR(20) NOT NULL,
                SIT_IN_COUNT INT DEFAULT 0,
                MAX_SIT_INS INT NOT NULL,
                FOREIGN KEY (USER_IDNO) REFERENCES USERS(IDNO)
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ANNOUNCEMENTS (
                ANNOUNCEMENT_ID INT AUTO_INCREMENT PRIMARY KEY,
                TITLE VARCHAR(100) NOT NULL,
                CONTENT TEXT NOT NULL,
                POSTED_BY VARCHAR(20) NOT NULL,
                DATE_POSTED TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                STATUS ENUM('active', 'inactive') DEFAULT 'active',
                FOREIGN KEY (POSTED_BY) REFERENCES USERS(IDNO)
            )
        """)
        
        # Create feedbacks table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS FEEDBACKS (
                FEEDBACK_ID INT AUTO_INCREMENT PRIMARY KEY,
                RECORD_ID INT NOT NULL,
                USER_IDNO VARCHAR(20) NOT NULL,
                RATING INT NOT NULL CHECK (RATING BETWEEN 1 AND 5),
                COMMENT TEXT,
                CREATED_AT TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UPDATED_AT TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (RECORD_ID) REFERENCES SIT_IN_RECORDS(RECORD_ID),
                FOREIGN KEY (USER_IDNO) REFERENCES USERS(IDNO)
            )
        """)
        
        # Create lab_resources table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS LAB_RESOURCES (
                RESOURCE_ID INT AUTO_INCREMENT PRIMARY KEY,
                TITLE VARCHAR(255) NOT NULL,
                CONTEXT TEXT,
                RESOURCE_TYPE ENUM('file', 'link', 'text', 'image') NOT NULL,
                RESOURCE_VALUE TEXT,
                RESOURCE_FILE MEDIUMBLOB,
                FILE_NAME VARCHAR(255),
                FILE_TYPE VARCHAR(100),
                PURPOSE_ID INT NOT NULL,
                ENABLED BOOLEAN DEFAULT TRUE,
                CREATED_BY VARCHAR(20) NOT NULL,
                CREATED_AT TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UPDATED_AT TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (CREATED_BY) REFERENCES USERS(IDNO),
                FOREIGN KEY (PURPOSE_ID) REFERENCES PURPOSES(PURPOSE_ID)
            )
        """)

        # Remove the lab_resource_courses table since we're not using it anymore
        cursor.execute("DROP TABLE IF EXISTS LAB_RESOURCE_COURSES")
        
        # Insert default data
        insert_default_data()
        
        # Insert sample sit-in records and feedbacks
        insert_sample_sit_in_records()
        
        # Initialize lab schedules if none exist
        cursor.execute("SELECT COUNT(*) as count FROM LAB_SCHEDULES")
        if cursor.fetchone()['count'] == 0:
            # Get all active labs, purposes, and professors
            cursor.execute("SELECT LAB_ID FROM LABORATORIES WHERE STATUS = 'active'")
            labs = cursor.fetchall()
            
            cursor.execute("SELECT PURPOSE_ID FROM PURPOSES WHERE STATUS = 'active'")
            purposes = cursor.fetchall()

            cursor.execute("SELECT PROFESSOR_ID FROM PROFESSORS WHERE STATUS = 'active'")
            professors = cursor.fetchall()
            
            # Define time slots with random intervals
            time_slots = [
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
                # Random interval slots
                ('07:30:00', '09:00:00'),  # 1.5 hours
                ('09:00:00', '11:00:00'),  # 2 hours
                ('11:00:00', '12:30:00'),  # 1.5 hours
                ('13:00:00', '14:30:00'),  # 1.5 hours
                ('14:30:00', '16:00:00'),  # 1.5 hours
                ('16:00:00', '17:30:00'),  # 1.5 hours
                ('17:30:00', '19:00:00'),  # 1.5 hours
                ('19:00:00', '20:30:00'),  # 1.5 hours
                ('20:30:00', '22:00:00')   # 1.5 hours
            ]
            
            # Define days of the week
            days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
            
            # Function to check if a time slot overlaps with existing schedules
            def check_schedule_overlap(cursor, lab_id, day, start_time, end_time):
                query = """
                SELECT COUNT(*) as count
                FROM LAB_SCHEDULES
                WHERE LAB_ID = %s
                AND DAY_OF_WEEK = %s
                AND (
                    (START_TIME <= %s AND END_TIME > %s)
                    OR (START_TIME < %s AND END_TIME >= %s)
                    OR (START_TIME >= %s AND END_TIME <= %s)
                )
                """
                cursor.execute(query, (lab_id, day, start_time, start_time, end_time, end_time, start_time, end_time))
                result = cursor.fetchone()
                return result['count'] > 0
            
            # Insert schedules with vacancy checks
            for lab in labs:
                for day in days:
                    # Track total hours scheduled for this lab and day
                    total_hours_scheduled = 0
                    max_hours_per_day = 8  # Maximum hours to schedule per day
                    
                    # Randomly select time slots
                    available_slots = time_slots.copy()
                    random.shuffle(available_slots)
                    
                    for start_time, end_time in available_slots:
                        # Calculate duration in hours
                        start_dt = datetime.strptime(start_time, '%H:%M:%S')
                        end_dt = datetime.strptime(end_time, '%H:%M:%S')
                        duration = (end_dt - start_dt).total_seconds() / 3600
                        
                        # Check if adding this slot would exceed max hours
                        if total_hours_scheduled + duration > max_hours_per_day:
                            continue
                        
                        # Check for overlap
                        if check_schedule_overlap(cursor, lab['LAB_ID'], day, start_time, end_time):
                            continue
                        
                        # Randomly select purposes for this slot
                        available_purposes = purposes.copy()
                        random.shuffle(available_purposes)
                        
                        # Randomly select professor for this slot
                        available_professors = professors.copy()
                        random.shuffle(available_professors)
                        
                        # Add schedule for this time slot - only one purpose and one professor per slot
                        if available_purposes and available_professors:
                            cursor.execute("""
                                INSERT INTO LAB_SCHEDULES 
                                (LAB_ID, PURPOSE_ID, PROFESSOR_ID, DAY_OF_WEEK, START_TIME, END_TIME, STATUS)
                                VALUES (%s, %s, %s, %s, %s, %s, 'active')
                            """, (lab['LAB_ID'], available_purposes[0]['PURPOSE_ID'], available_professors[0]['PROFESSOR_ID'], day, start_time, end_time))
                        
                        total_hours_scheduled += duration
                        
                        # Break if we've reached max hours
                        if total_hours_scheduled >= max_hours_per_day:
                            break
        
        # Insert default professors
        cursor.execute("SELECT COUNT(*) as count FROM PROFESSORS")
        if cursor.fetchone()['count'] == 0:
            print("\nInserting default professors...")
            default_professors = [
                ('NONITO', 'ODJINAR', 'O.'),
                ('WILSON', 'GAYO', ''),
                ('JEFF', 'SALIMBANGON', ''),
                ('DENNIS', 'DURANO', 'S.'),
                ('LEO', 'BERMUDEZ', 'C.'),
                ('JENNIFER', 'AMORES', 'G.'),
                ('JIA NOVA', 'MONTECINO', 'B.'),
                ('LEAH', 'YBANEZ', 'B.')
            ]

            for prof in default_professors:
                cursor.execute("""
                    INSERT INTO PROFESSORS (FIRST_NAME, LAST_NAME, MIDDLE_NAME, STATUS)
                    VALUES (%s, %s, %s, 'active')
                """, prof)
            print(f"Inserted {len(default_professors)} professors")
        else:
            print("\nProfessors already exist. Skipping insertion.")
        
        connection.commit()
        cursor.close()
        connection.close()
        return True
    except Error as e:
        print(f"Error initializing database: {e}")
        return False 
