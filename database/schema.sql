CREATE DATABASE IF NOT EXISTS rosterflow CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE rosterflow;

CREATE TABLE pods (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(100) NOT NULL UNIQUE,
  lead_employee_id BIGINT UNSIGNED NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

CREATE TABLE employees (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  employee_code VARCHAR(30) NOT NULL UNIQUE,
  full_name VARCHAR(150) NOT NULL,
  email VARCHAR(190) NOT NULL UNIQUE,
  phone VARCHAR(30) NULL,
  pod_id BIGINT UNSIGNED NULL,
  active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_employee_pod FOREIGN KEY (pod_id) REFERENCES pods(id) ON DELETE SET NULL
) ENGINE=InnoDB;

ALTER TABLE pods ADD CONSTRAINT fk_pod_lead FOREIGN KEY (lead_employee_id) REFERENCES employees(id) ON DELETE SET NULL;

CREATE TABLE brands (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(120) NOT NULL UNIQUE,
  description TEXT NULL,
  active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

CREATE TABLE processes (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  code VARCHAR(20) NOT NULL UNIQUE,
  name VARCHAR(100) NOT NULL UNIQUE,
  description TEXT NULL,
  active BOOLEAN NOT NULL DEFAULT TRUE
) ENGINE=InnoDB;

CREATE TABLE assignments (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  employee_id BIGINT UNSIGNED NOT NULL,
  brand_id BIGINT UNSIGNED NOT NULL,
  process_id BIGINT UNSIGNED NOT NULL,
  effective_from DATE NOT NULL,
  effective_to DATE NULL,
  priority INT NOT NULL DEFAULT 100,
  active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_assignment_employee FOREIGN KEY (employee_id) REFERENCES employees(id),
  CONSTRAINT fk_assignment_brand FOREIGN KEY (brand_id) REFERENCES brands(id),
  CONSTRAINT fk_assignment_process FOREIGN KEY (process_id) REFERENCES processes(id),
  INDEX idx_assignment_scope (brand_id, process_id, active),
  INDEX idx_assignment_employee_dates (employee_id, effective_from, effective_to)
) ENGINE=InnoDB;

CREATE TABLE working_rules (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  brand_id BIGINT UNSIGNED NOT NULL,
  process_id BIGINT UNSIGNED NOT NULL,
  rule_name VARCHAR(120) NOT NULL,
  operates_sunday BOOLEAN NOT NULL DEFAULT FALSE,
  operates_public_holidays BOOLEAN NOT NULL DEFAULT FALSE,
  operates_monday_to_saturday BOOLEAN NOT NULL DEFAULT TRUE,
  minimum_staff INT UNSIGNED NOT NULL DEFAULT 1,
  effective_from DATE NOT NULL,
  effective_to DATE NULL,
  active BOOLEAN NOT NULL DEFAULT TRUE,
  CONSTRAINT fk_rule_brand FOREIGN KEY (brand_id) REFERENCES brands(id),
  CONSTRAINT fk_rule_process FOREIGN KEY (process_id) REFERENCES processes(id),
  INDEX idx_rule_lookup (brand_id, process_id, active, effective_from)
) ENGINE=InnoDB;

CREATE TABLE employee_weekly_offs (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  employee_id BIGINT UNSIGNED NOT NULL,
  weekday TINYINT UNSIGNED NOT NULL COMMENT '0=Monday through 6=Sunday',
  effective_from DATE NOT NULL,
  effective_to DATE NULL,
  CONSTRAINT fk_weekly_off_employee FOREIGN KEY (employee_id) REFERENCES employees(id) ON DELETE CASCADE,
  CONSTRAINT chk_weekday_range CHECK (weekday BETWEEN 0 AND 6),
  INDEX idx_weekly_off_employee_dates (employee_id, effective_from, effective_to)
) ENGINE=InnoDB;

CREATE TABLE holidays (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  holiday_date DATE NOT NULL,
  name VARCHAR(150) NOT NULL,
  region VARCHAR(100) NULL,
  UNIQUE KEY uq_holiday_date_region (holiday_date, region)
) ENGINE=InnoDB;

CREATE TABLE availability (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  employee_id BIGINT UNSIGNED NOT NULL,
  start_date DATE NOT NULL,
  end_date DATE NOT NULL,
  availability_type ENUM('WEEKLY_OFF','PLANNED_LEAVE','COMP_OFF','UNAVAILABLE') NOT NULL,
  approval_status ENUM('PENDING','APPROVED','REJECTED') NOT NULL DEFAULT 'APPROVED',
  notes VARCHAR(255) NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_availability_employee FOREIGN KEY (employee_id) REFERENCES employees(id),
  CONSTRAINT chk_availability_dates CHECK (end_date >= start_date),
  INDEX idx_availability_dates (employee_id, start_date, end_date, approval_status)
) ENGINE=InnoDB;

CREATE TABLE roster_versions (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  roster_month DATE NOT NULL,
  version_number INT UNSIGNED NOT NULL,
  status ENUM('DRAFT','PUBLISHED','ARCHIVED') NOT NULL DEFAULT 'DRAFT',
  generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  published_at TIMESTAMP NULL,
  notes TEXT NULL,
  UNIQUE KEY uq_roster_month_version (roster_month, version_number)
) ENGINE=InnoDB;

CREATE TABLE roster_entries (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  roster_version_id BIGINT UNSIGNED NOT NULL,
  employee_id BIGINT UNSIGNED NOT NULL,
  brand_id BIGINT UNSIGNED NOT NULL,
  process_id BIGINT UNSIGNED NOT NULL,
  roster_date DATE NOT NULL,
  shift_start TIME NULL,
  shift_end TIME NULL,
  status ENUM('WORKING','WEEKLY_OFF','PUBLIC_HOLIDAY','LEAVE','COMP_OFF','UNASSIGNED') NOT NULL,
  source ENUM('AUTO','MANUAL') NOT NULL DEFAULT 'AUTO',
  CONSTRAINT fk_roster_version FOREIGN KEY (roster_version_id) REFERENCES roster_versions(id) ON DELETE CASCADE,
  CONSTRAINT fk_roster_employee FOREIGN KEY (employee_id) REFERENCES employees(id),
  CONSTRAINT fk_roster_brand FOREIGN KEY (brand_id) REFERENCES brands(id),
  CONSTRAINT fk_roster_process FOREIGN KEY (process_id) REFERENCES processes(id),
  INDEX idx_roster_date_scope (roster_version_id, roster_date, brand_id, process_id),
  INDEX idx_roster_employee_date (roster_version_id, employee_id, roster_date)
) ENGINE=InnoDB;

CREATE TABLE conflicts (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  roster_version_id BIGINT UNSIGNED NOT NULL,
  roster_date DATE NOT NULL,
  brand_id BIGINT UNSIGNED NULL,
  process_id BIGINT UNSIGNED NULL,
  employee_id BIGINT UNSIGNED NULL,
  conflict_type ENUM('COVERAGE_GAP','DOUBLE_BOOKING','LEAVE_CONFLICT','RULE_VIOLATION','UNASSIGNED_REQUIREMENT') NOT NULL,
  severity ENUM('ERROR','WARNING','INFO') NOT NULL DEFAULT 'ERROR',
  required_staff INT UNSIGNED NULL,
  available_staff INT UNSIGNED NULL,
  message TEXT NOT NULL,
  resolved BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_conflict_version FOREIGN KEY (roster_version_id) REFERENCES roster_versions(id) ON DELETE CASCADE,
  CONSTRAINT fk_conflict_brand FOREIGN KEY (brand_id) REFERENCES brands(id) ON DELETE SET NULL,
  CONSTRAINT fk_conflict_process FOREIGN KEY (process_id) REFERENCES processes(id) ON DELETE SET NULL,
  CONSTRAINT fk_conflict_employee FOREIGN KEY (employee_id) REFERENCES employees(id) ON DELETE SET NULL,
  INDEX idx_conflict_version_status (roster_version_id, resolved, severity)
) ENGINE=InnoDB;
