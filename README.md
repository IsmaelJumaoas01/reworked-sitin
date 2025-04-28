# Sit-In School Management System

A Flask-based web application for managing computer laboratory sit-in requests in schools.

## Features

- User authentication (Students, Staff, and Admin)
- Sit-in request management
- Laboratory and computer management
- Announcement system
- Sit-in history tracking
- User profile management

## Prerequisites

- Python 3.7 or higher
- XAMPP (for MySQL database)
- pip (Python package manager)

## Setup Instructions

1. Clone the repository:
```bash
git clone <repository-url>
cd sit-in
```

2. Create a virtual environment and activate it:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up the database:
   - Start XAMPP and ensure MySQL is running
   - Create a new database named `sit_in_db`
   - Import the database schema from the `database.sql` file

5. Configure the database connection:
   - Open `db.py`
   - Update the database credentials if needed

6. Run the application:
```bash
python app.py
```

7. Access the application at `http://localhost:5000`

## User Types

1. **Admin**
   - Manage laboratories and computers
   - Manage purposes for sit-ins
   - Post announcements
   - View system statistics

2. **Staff**
   - Approve/deny sit-in requests
   - End sit-in sessions
   - View active sit-ins
   - View announcements

3. **Student**
   - Request sit-ins
   - View sit-in history
   - Update profile
   - View announcements

## Security Features

- Password hashing
- Session management
- Role-based access control
- Input validation

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Default Data

### Laboratories
- LAB 524 (50 computers)
- LAB 525 (50 computers)
- LAB 528 (50 computers)
- LAB 530 (50 computers)
- LAB 542 (50 computers)
- LAB 544 (50 computers)
- LAB 517 (50 computers)
- LAB 557 (50 computers)

### Purposes
1. C PROGRAMMING
2. JAVA PROGRAMMING
3. PYTHON
4. C#
5. DATABASE
6. DIGITAL AND LOGIC DESIGN
7. EMBEDDED SYSTEMS AND IOT
8. SYSTEM INTEGRATION AND ARCHITECTURE
9. COMPUTER APPLICATION
10. PROJECT MANAGEMENT
11. IT TRENDS
12. TECHNOPRENEURSHIP
13. CAPSTONE

### Default Users

#### Admin
- Email: admin@system.com
- Password: admin123

#### Staff Users
1. John Doe
   - ID: STAFF001
   - Email: john.doe@example.com
   - Password: staff123
   - Course: BSIT
   - Year: 4

2. Jane Smith
   - ID: STAFF002
   - Email: jane.smith@example.com
   - Password: staff123
   - Course: BSCS
   - Year: 4

#### Student Users
1. Alice Johnson
   - ID: 20230001
   - Email: alice.j@example.com
   - Password: student123
   - Course: BSIT
   - Year: 3
   - Sit-in Limit: 30

2. Bob Williams
   - ID: 20230002
   - Email: bob.w@example.com
   - Password: student123
   - Course: BSCS
   - Year: 2
   - Sit-in Limit: 30

3. Carol Brown
   - ID: 20230003
   - Email: carol.b@example.com
   - Password: student123
   - Course: BSIT
   - Year: 4
   - Sit-in Limit: 30

4. David Miller
   - ID: 20230004
   - Email: david.m@example.com
   - Password: student123
   - Course: BSCS
   - Year: 1
   - Sit-in Limit: 30

5. Eve Davis
   - ID: 20230005
   - Email: eve.d@example.com
   - Password: student123
   - Course: BSIT
   - Year: 2
   - Sit-in Limit: 30

### Default Announcements
1. Welcome to the New Semester
   - Posted by: John Doe (STAFF001)
   - Content: Welcome to the new semester! Please check your schedules and prepare for your classes.

2. Laboratory Guidelines
   - Posted by: Jane Smith (STAFF002)
   - Content: Please follow the laboratory guidelines and maintain cleanliness in the computer labs.

3. Sit-In System Update
   - Posted by: John Doe (STAFF001)
   - Content: The sit-in management system has been updated with new features. Please check the user guide for details.

## Notes
- Each laboratory has 50 computers
- BSIT and BSCS students have a sit-in limit of 30 sessions
- Other courses have a sit-in limit of 15 sessions
- All default users have 'active' status
- All default data is inserted automatically when the database is initialized 