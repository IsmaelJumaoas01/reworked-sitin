import mysql.connector
from mysql.connector import Error
import os
from dotenv import load_dotenv
import hashlib
import random
from datetime import datetime

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
        
        # Insert default student users
        print("\nInserting student users...")
        student_users = [
            ('20230001', 'Alice', 'Johnson', 'alice.j@example.com', 'student123', 'BSIT', 3, 'STUDENT'),
            ('20230002', 'Bob', 'Williams', 'bob.w@example.com', 'student123', 'BSCS', 2, 'STUDENT'),
            ('20230003', 'Carol', 'Brown', 'carol.b@example.com', 'student123', 'BSIT', 4, 'STUDENT'),
            ('20230004', 'David', 'Miller', 'david.m@example.com', 'student123', 'BSCS', 1, 'STUDENT'),
            ('20230005', 'Eve', 'Davis', 'eve.d@example.com', 'student123', 'BSIT', 2, 'STUDENT')
        ]
        
        for student in student_users:
            hashed_password = hashlib.sha256(student[4].encode()).hexdigest()
            execute_query("""
                INSERT INTO USERS (IDNO, FIRSTNAME, LASTNAME, EMAIL, PASSWORD, COURSE, YEAR, USER_TYPE, STATUS)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'active')
            """, student[:4] + (hashed_password,) + student[5:])
            
            # Set sit-in limits for students
            max_sit_ins = 30 if student[5] in ['BSIT', 'BSCS'] else 15
            execute_query("""
                INSERT INTO SIT_IN_LIMITS (USER_IDNO, SIT_IN_COUNT, MAX_SIT_INS)
                VALUES (%s, 0, %s)
            """, (student[0], max_sit_ins))
        print(f"Inserted {len(student_users)} student users")
        
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
        
        print("\nDefault data inserted successfully!")
    except Exception as e:
        print(f"\nError inserting default data: {str(e)}")
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
                FOREIGN KEY (LAB_ID) REFERENCES LABORATORIES(LAB_ID),
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
                CREATED_AT TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
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
                RESOURCE_VALUE TEXT NOT NULL,
                ENABLED BOOLEAN DEFAULT TRUE,
                CREATED_BY VARCHAR(20) NOT NULL,
                CREATED_AT TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UPDATED_AT TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (CREATED_BY) REFERENCES USERS(IDNO)
            )
        """)

        # Create join table for lab_resource_courses (many-to-many)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS LAB_RESOURCE_COURSES (
                RESOURCE_ID INT NOT NULL,
                COURSE VARCHAR(10) NOT NULL,
                PRIMARY KEY (RESOURCE_ID, COURSE),
                FOREIGN KEY (RESOURCE_ID) REFERENCES LAB_RESOURCES(RESOURCE_ID)
            )
        """)
        
        # Create lab schedules table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS LAB_SCHEDULES (
                SCHEDULE_ID INT AUTO_INCREMENT PRIMARY KEY,
                LAB_ID INT NOT NULL,
                PURPOSE_ID INT NOT NULL,
                DAY_OF_WEEK ENUM('Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday') NOT NULL,
                START_TIME TIME NOT NULL,
                END_TIME TIME NOT NULL,
                STATUS ENUM('active', 'inactive') DEFAULT 'active',
                CREATED_AT TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (LAB_ID) REFERENCES LABORATORIES(LAB_ID),
                FOREIGN KEY (PURPOSE_ID) REFERENCES PURPOSES(PURPOSE_ID) ON DELETE CASCADE
            )
        """)
        
        # Create default admin user if not exists
        cursor.execute("""
            INSERT IGNORE INTO USERS (IDNO, LASTNAME, FIRSTNAME, COURSE, YEAR, EMAIL, PASSWORD, USER_TYPE)
            VALUES ('ADMIN001', 'Admin', 'System', 'N/A', 0, 'admin@system.com', 
                   SHA2('admin123', 256), 'ADMIN')
        """)
        
        # Insert default data
        insert_default_data()
        
        # Initialize lab schedules if none exist
        cursor.execute("SELECT COUNT(*) as count FROM LAB_SCHEDULES")
        if cursor.fetchone()['count'] == 0:
            # Get all active labs and purposes
            cursor.execute("SELECT LAB_ID FROM LABORATORIES WHERE STATUS = 'active'")
            labs = cursor.fetchall()
            
            cursor.execute("SELECT PURPOSE_ID FROM PURPOSES WHERE STATUS = 'active'")
            purposes = cursor.fetchall()
            
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
                        
                        # Add schedule for this time slot
                        for purpose in available_purposes[:2]:  # Add up to 2 purposes per time slot
                            cursor.execute("""
                                INSERT INTO LAB_SCHEDULES 
                                (LAB_ID, PURPOSE_ID, DAY_OF_WEEK, START_TIME, END_TIME, STATUS)
                                VALUES (%s, %s, %s, %s, %s, 'active')
                            """, (lab['LAB_ID'], purpose['PURPOSE_ID'], day, start_time, end_time))
                        
                        total_hours_scheduled += duration
                        
                        # Break if we've reached max hours
                        if total_hours_scheduled >= max_hours_per_day:
                            break
        
        connection.commit()
        cursor.close()
        connection.close()
        return True
    except Error as e:
        print(f"Error initializing database: {e}")
        return False 
