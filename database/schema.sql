-- ===============================================================
-- DIGITAL MITRAZ - TRAINING MANAGEMENT SYSTEM (FULL SCHEMA)
-- Version: 2.0 (Enterprise Edition)
-- ===============================================================

-- 1. RESET DATABASE

-- ===============================================================
-- 2. CORE ACCESS CONTROL
-- ===============================================================

-- USERS (Login & Profiles)
CREATE TABLE users (
    user_id INT PRIMARY KEY AUTO_INCREMENT,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(255) NOT NULL,
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    phone VARCHAR(20),
    gender ENUM('Male', 'Female', 'Other') DEFAULT 'Male',
    role ENUM('super_admin', 'admin', 'trainer', 'student') NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    profile_picture VARCHAR(255),
    qualifications TEXT, -- Specific to Trainers
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by INT, 
    FOREIGN KEY (created_by) REFERENCES users(user_id) ON DELETE SET NULL
);

-- CENTERS (Location Management)
CREATE TABLE centers (
    center_id INT PRIMARY KEY AUTO_INCREMENT,
    center_name VARCHAR(255) NOT NULL, 
    location VARCHAR(255) DEFAULT 'Puttaparthi',
    is_active BOOLEAN DEFAULT TRUE
);

-- ===============================================================
-- 3. ACADEMIC STRUCTURE
-- ===============================================================

-- COURSES (Programs)
CREATE TABLE courses (
    course_id INT PRIMARY KEY AUTO_INCREMENT,
    course_name VARCHAR(255) NOT NULL,
    code VARCHAR(50),
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_by INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (created_by) REFERENCES users(user_id) ON DELETE SET NULL
);

-- BATCHES (Cohorts)
CREATE TABLE batches (
    batch_id INT PRIMARY KEY AUTO_INCREMENT,
    batch_name VARCHAR(255) NOT NULL,
    course_id INT,
    center_id INT,
    start_date DATE,
    end_date DATE,
    max_students INT DEFAULT 30, -- Capacity
    status ENUM('PLANNED', 'ACTIVE', 'COMPLETED') DEFAULT 'PLANNED',
    is_active BOOLEAN DEFAULT TRUE,
    
    -- Leave Configuration Rules
    personal_leave_limit INT DEFAULT 5,
    medical_leave_limit INT NULL,
    academic_leave_limit INT NULL,
    special_leave_limit INT NULL,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by INT,
    FOREIGN KEY (course_id) REFERENCES courses(course_id) ON DELETE CASCADE,
    FOREIGN KEY (center_id) REFERENCES centers(center_id) ON DELETE SET NULL
);

-- ROLE MAPPINGS
CREATE TABLE course_admins (
    id INT PRIMARY KEY AUTO_INCREMENT,
    course_id INT,
    admin_id INT,
    is_active BOOLEAN DEFAULT TRUE,
    FOREIGN KEY (course_id) REFERENCES courses(course_id) ON DELETE CASCADE,
    FOREIGN KEY (admin_id) REFERENCES users(user_id) ON DELETE CASCADE
);

CREATE TABLE course_trainers (
    id INT PRIMARY KEY AUTO_INCREMENT,
    course_id INT,
    trainer_id INT,
    is_active BOOLEAN DEFAULT TRUE,
    FOREIGN KEY (course_id) REFERENCES courses(course_id) ON DELETE CASCADE,
    FOREIGN KEY (trainer_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- ===============================================================
-- 4. STUDENT LIFECYCLE (9-Tab Data Structure)
-- ===============================================================

-- MASTER STUDENT TABLE
CREATE TABLE students (
    student_id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT UNIQUE, 
    enrollment_id VARCHAR(50) UNIQUE, -- Official ID (e.g., MIT-2025-01)
    batch_id INT,
    course_id INT, -- Denormalized for easier reporting
    enrollment_status ENUM('DRAFT', 'PENDING_APPROVAL', 'ENROLLED', 'DROPOUT', 'ALUMNI') DEFAULT 'DRAFT',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (batch_id) REFERENCES batches(batch_id) ON DELETE SET NULL,
    FOREIGN KEY (course_id) REFERENCES courses(course_id) ON DELETE SET NULL
);

-- TAB 1: PERSONAL DETAILS
CREATE TABLE student_personal_details (
    id INT PRIMARY KEY AUTO_INCREMENT,
    student_id INT UNIQUE,
    salutation VARCHAR(10),
    first_name VARCHAR(100),
    middle_name VARCHAR(100),
    last_name VARCHAR(100),
    aadhar_number VARCHAR(20) UNIQUE,
    dob DATE,
    gender ENUM('Male', 'Female', 'Other'),
    blood_group VARCHAR(10),
    
    -- Marital Status & Children
    marital_status VARCHAR(20),
    spouse_name VARCHAR(100),
    children_count INT DEFAULT 0,
    
    religion VARCHAR(50),
    category VARCHAR(50),
    father_name VARCHAR(100),
    mother_name VARCHAR(100),
    
    -- Disability & Status
    is_physically_challenged BOOLEAN DEFAULT FALSE,
    disability_details TEXT,
    bpl_status ENUM('Yes', 'No') DEFAULT 'No',
    
    -- Mobilization
    mobilization_channel VARCHAR(100),
    refered_by VARCHAR(100),
    
    -- Contact & Address
    primary_phone VARCHAR(20),
    primary_email VARCHAR(100),
    secondary_phone VARCHAR(20),
    secondary_email VARCHAR(100),
    linkedin_url VARCHAR(255),
    
    current_address TEXT,
    permanent_address TEXT,
    city VARCHAR(100),
    district VARCHAR(100),
    state VARCHAR(100),
    pincode VARCHAR(10),
    
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
);

-- TAB 2: SOCIO-ECONOMIC (NGO Specific)
CREATE TABLE student_socio_economic (
    id INT PRIMARY KEY AUTO_INCREMENT,
    student_id INT UNIQUE,
    housing_type ENUM('Owned', 'Rented') DEFAULT 'Owned',
    housing_condition ENUM('Pucca', 'Kutcha', 'Semi-Pucca'),
    room_count INT,
    
    -- Rural Indicators
    lighting_source VARCHAR(100),
    cooking_fuel VARCHAR(100),    
    water_source VARCHAR(100),
    
    -- Economic Indicators
    ration_card_type VARCHAR(50), -- White/Pink/Yellow
    primary_income_source VARCHAR(50),
    has_active_loans VARCHAR(10),
    
    -- Digital & Assets
    digital_device VARCHAR(50),
    internet_access VARCHAR(50),
    household_assets TEXT, 
    has_bank_account BOOLEAN DEFAULT FALSE,
    
    -- Family Stats
    family_members_count INT,
    
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
);

-- TAB 3: EDUCATION
CREATE TABLE student_education (
    id INT PRIMARY KEY AUTO_INCREMENT,
    student_id INT,
    qualification_level VARCHAR(100), 
    institute_name VARCHAR(255),
    passing_year INT,
    percentage DECIMAL(5,2),
    specialization VARCHAR(100),
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
);

-- TAB 4: FAMILY
CREATE TABLE student_family (
    id INT PRIMARY KEY AUTO_INCREMENT,
    student_id INT,
    name VARCHAR(100),
    relationship VARCHAR(50),
    occupation VARCHAR(100),
    qualification VARCHAR(100),
    income DECIMAL(12,2) DEFAULT 0.00,
    contact_number VARCHAR(20),
    is_head_of_family BOOLEAN DEFAULT FALSE,
    is_primary_breadwinner BOOLEAN DEFAULT FALSE,
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
);

-- TAB 5: EXPERIENCE
CREATE TABLE student_experience (
    id INT PRIMARY KEY AUTO_INCREMENT,
    student_id INT,
    exp_type ENUM('Fresher', 'Experienced') DEFAULT 'Fresher',
    employer_name VARCHAR(255),
    designation VARCHAR(100),
    salary DECIMAL(10,2),
    start_date DATE,
    end_date DATE,
    location VARCHAR(100),
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
);

-- TAB 6: COUNSELLING
CREATE TABLE student_counselling (
    id INT PRIMARY KEY AUTO_INCREMENT,
    student_id INT UNIQUE,
    interest_inventory VARCHAR(100),
    status VARCHAR(50),
    counsellor_rating VARCHAR(50),
    counsellor_1_comments TEXT,
    parent_counselling_comments TEXT,
    recommended_course VARCHAR(100),
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
);

-- TAB 7: DOCUMENTS
CREATE TABLE student_documents (
    id INT PRIMARY KEY AUTO_INCREMENT,
    student_id INT,
    doc_category VARCHAR(50),
    doc_type VARCHAR(100),
    file_path VARCHAR(500),
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
);

-- TAB 8: PLACEMENT
CREATE TABLE student_placement (
    id INT PRIMARY KEY AUTO_INCREMENT,
    student_id INT UNIQUE,
    interview_status VARCHAR(50) DEFAULT 'Pending',
    remarks TEXT,
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
);

-- TAB 9: ENROLLMENT HISTORY
CREATE TABLE batch_students (
    id INT PRIMARY KEY AUTO_INCREMENT,
    batch_id INT,
    student_id INT,
    enrolled_date DATE DEFAULT (CURRENT_DATE),
    is_active BOOLEAN DEFAULT TRUE,
    FOREIGN KEY (batch_id) REFERENCES batches(batch_id) ON DELETE CASCADE,
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE,
    UNIQUE KEY unique_batch_student (batch_id, student_id)
);

-- ===============================================================
-- 5. ACADEMIC OPERATIONS
-- ===============================================================

-- TOPICS
CREATE TABLE topics (
    topic_id INT PRIMARY KEY AUTO_INCREMENT,
    topic_name VARCHAR(255) NOT NULL,
    description TEXT,
    course_id INT,
    batch_id INT,
    parent_topic_id INT NULL,
    trainer_id INT, -- Added for Trainer ownership
    sequence_order INT DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (course_id) REFERENCES courses(course_id) ON DELETE CASCADE,
    FOREIGN KEY (parent_topic_id) REFERENCES topics(topic_id) ON DELETE CASCADE,
    FOREIGN KEY (trainer_id) REFERENCES users(user_id) ON DELETE SET NULL
);

-- ASSIGNMENTS & AUTO-GRADING
CREATE TABLE assignments (
    assignment_id INT PRIMARY KEY AUTO_INCREMENT,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    topic_id INT,
    batch_id INT, 
    created_by INT,
    due_date DATETIME,
    assignment_type ENUM('individual', 'group') DEFAULT 'individual',
    max_points INT DEFAULT 100,
    file_path VARCHAR(500),
    
    evaluation_type ENUM('none', 'python', 'sql', 'excel', 'web') DEFAULT 'none',
    test_case_file_path VARCHAR(500),
    
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (topic_id) REFERENCES topics(topic_id) ON DELETE CASCADE,
    FOREIGN KEY (batch_id) REFERENCES batches(batch_id) ON DELETE CASCADE
);

-- SUBMISSIONS
CREATE TABLE assignment_submissions (
    submission_id INT PRIMARY KEY AUTO_INCREMENT,
    assignment_id INT,
    student_id INT,
    submission_text TEXT,
    file_path VARCHAR(500),
    submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_late BOOLEAN DEFAULT FALSE,
    grade INT DEFAULT NULL,
    auto_grade INT NULL,
    feedback TEXT,
    auto_feedback TEXT,
    evaluation_output TEXT,
    evaluation_status ENUM('pending', 'processing', 'completed', 'error') DEFAULT 'pending',
    graded_by INT,
    graded_at TIMESTAMP NULL,
    FOREIGN KEY (assignment_id) REFERENCES assignments(assignment_id) ON DELETE CASCADE,
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
);

-- ATTENDANCE (Advanced)
CREATE TABLE attendance (
    attendance_id INT PRIMARY KEY AUTO_INCREMENT,
    student_id INT,
    batch_id INT,
    course_id INT,
    attendance_date DATE NOT NULL,
    status ENUM('PRESENT', 'ABSENT', 'HALF_DAY_MORNING', 'HALF_DAY_AFTERNOON', 'LEAVE', 'HOLIDAY', 'WEEKEND') NOT NULL,
    marked_by INT,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    -- Compatibility Column (Virtual) for legacy code support
    is_present BOOLEAN GENERATED ALWAYS AS (IF(status = 'PRESENT', 1, 0)) VIRTUAL,
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE,
    FOREIGN KEY (batch_id) REFERENCES batches(batch_id) ON DELETE CASCADE,
    UNIQUE KEY unique_daily_att (student_id, attendance_date)
);

-- ===============================================================
-- 6. REQUESTS & NOTIFICATIONS
-- ===============================================================

CREATE TABLE leave_types (
    leave_type_id INT PRIMARY KEY AUTO_INCREMENT,
    type_name VARCHAR(100),
    has_limit BOOLEAN DEFAULT TRUE,
    default_limit_days INT
);

CREATE TABLE leave_applications (
    leave_id INT PRIMARY KEY AUTO_INCREMENT,
    student_id INT,
    batch_id INT,
    leave_type_id INT,
    start_date DATE,
    end_date DATE,
    days_requested INT,
    reason TEXT,
    supporting_document VARCHAR(500),
    status ENUM('pending', 'approved', 'rejected') DEFAULT 'pending',
    admin_comments TEXT,
    reviewed_by INT,
    reviewed_at TIMESTAMP,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE,
    FOREIGN KEY (leave_type_id) REFERENCES leave_types(leave_type_id)
);

CREATE TABLE approval_requests (
    request_id INT PRIMARY KEY AUTO_INCREMENT,
    requester_id INT, 
    action_type VARCHAR(50), -- DELETE_STUDENT, DROPOUT, LATE_ENROLLMENT
    target_id INT,
    reason TEXT,
    status ENUM('PENDING', 'APPROVED', 'REJECTED') DEFAULT 'PENDING',
    new_data_payload JSON,
    approver_id INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE holidays (
    holiday_id INT PRIMARY KEY AUTO_INCREMENT,
    holiday_date DATE UNIQUE NOT NULL,
    title VARCHAR(100),
    year INT
);

CREATE TABLE activity_logs (
    log_id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT,
    action VARCHAR(50),
    table_affected VARCHAR(50),
    record_id INT,
    description TEXT,
    ip_address VARCHAR(45),
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE password_resets (
    reset_id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT,
    reset_token VARCHAR(255),
    expires_at TIMESTAMP,
    is_used BOOLEAN DEFAULT FALSE
);

-- ===============================================================
-- 7. SEED DATA (Default Login)
-- ===============================================================

-- Super Admin: Email: superadmin@mitraz.com | Pass: admin123
INSERT INTO users (email, password_hash, full_name, role, is_active) 
VALUES ('superadmin@mitraz.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxRQJ9J.4W.1e/8z.d.z.y.z.y.', 'Super Administrator', 'super_admin', TRUE);

-- Initial Center
INSERT INTO centers (center_name) VALUES ('MITRAz Skills Center');

-- Default Leave Types
INSERT INTO leave_types (type_name, has_limit, default_limit_days) VALUES 
('Personal', TRUE, 5), 
('Medical', FALSE, NULL), 
('Emergency', TRUE, 3),
('Academic', FALSE, NULL);