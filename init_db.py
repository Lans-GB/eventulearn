CREATE DATABASE eventulearn;
USE eventulearn;

CREATE TABLE users (
    user_id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100),
    sr_code VARCHAR(20),
    password VARCHAR(100),
    role VARCHAR(20)
);

CREATE TABLE events (
    event_id INT AUTO_INCREMENT PRIMARY KEY,
    event_name VARCHAR(255),
    organizer VARCHAR(255),
    venue VARCHAR(255),
    price FLOAT,
    event_date DATE,
    capacity INT,
    event_type VARCHAR(50),
    year_levels TEXT,
    department VARCHAR(100),
    program VARCHAR(100),
    short_desc TEXT,
    long_desc TEXT,
    poster TEXT,
    icon TEXT
);

CREATE TABLE registrations (
    reg_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT,
    event_id INT,
    qr_code VARCHAR(255)
);