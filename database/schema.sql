-- RosterFlow MySQL schema (generated from the SQLAlchemy models).
-- The app can create this itself: `flask init-db` or `flask seed-demo`.
CREATE DATABASE IF NOT EXISTS rosterflow CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE rosterflow;

CREATE TABLE IF NOT EXISTS brands (
	id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT, 
	name VARCHAR(120) NOT NULL, 
	description TEXT, 
	active BOOL NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (name)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS holidays (
	id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT, 
	holiday_date DATE NOT NULL, 
	name VARCHAR(150) NOT NULL, 
	region VARCHAR(100), 
	PRIMARY KEY (id), 
	CONSTRAINT uq_holiday_date_region UNIQUE (holiday_date, region)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS pods (
	id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT, 
	name VARCHAR(100) NOT NULL, 
	lead_employee_id BIGINT UNSIGNED, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (name)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS processes (
	id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT, 
	code VARCHAR(20) NOT NULL, 
	name VARCHAR(100) NOT NULL, 
	description TEXT, 
	active BOOL NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (code), 
	UNIQUE (name)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS roster_versions (
	id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT, 
	roster_month DATE NOT NULL, 
	version_number INTEGER NOT NULL, 
	status ENUM('DRAFT','PUBLISHED','ARCHIVED') NOT NULL, 
	parent_version_id BIGINT UNSIGNED, 
	generated_at DATETIME NOT NULL, 
	published_at DATETIME, 
	notes TEXT, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_roster_month_version UNIQUE (roster_month, version_number), 
	FOREIGN KEY(parent_version_id) REFERENCES roster_versions (id) ON DELETE SET NULL
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS coverage_overrides (
	id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT, 
	brand_id BIGINT UNSIGNED NOT NULL, 
	process_id BIGINT UNSIGNED NOT NULL, 
	override_date DATE NOT NULL, 
	minimum_staff INTEGER NOT NULL, 
	reason VARCHAR(150), 
	PRIMARY KEY (id), 
	CONSTRAINT uq_override_scope UNIQUE (brand_id, process_id, override_date), 
	FOREIGN KEY(brand_id) REFERENCES brands (id), 
	FOREIGN KEY(process_id) REFERENCES processes (id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS employees (
	id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT, 
	employee_code VARCHAR(30) NOT NULL, 
	full_name VARCHAR(150) NOT NULL, 
	email VARCHAR(190) NOT NULL, 
	phone VARCHAR(30), 
	designation VARCHAR(80), 
	pod_id BIGINT UNSIGNED, 
	weekly_offs_per_week INTEGER NOT NULL, 
	active BOOL NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (employee_code), 
	UNIQUE (email), 
	FOREIGN KEY(pod_id) REFERENCES pods (id) ON DELETE SET NULL
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS roster_change_log (
	id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT, 
	roster_version_id BIGINT UNSIGNED NOT NULL, 
	created_at DATETIME NOT NULL, 
	action VARCHAR(40) NOT NULL, 
	description TEXT NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(roster_version_id) REFERENCES roster_versions (id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS working_rules (
	id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT, 
	brand_id BIGINT UNSIGNED NOT NULL, 
	process_id BIGINT UNSIGNED NOT NULL, 
	rule_name VARCHAR(120) NOT NULL, 
	daily_minimums VARCHAR(40) NOT NULL, 
	operates_public_holidays BOOL NOT NULL, 
	shift_start TIME NOT NULL, 
	shift_end TIME NOT NULL, 
	effective_from DATE NOT NULL, 
	effective_to DATE, 
	active BOOL NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(brand_id) REFERENCES brands (id), 
	FOREIGN KEY(process_id) REFERENCES processes (id)
) ENGINE=InnoDB;
CREATE INDEX idx_rule_lookup ON working_rules (brand_id, process_id, active, effective_from);

CREATE TABLE IF NOT EXISTS assignments (
	id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT, 
	employee_id BIGINT UNSIGNED NOT NULL, 
	brand_id BIGINT UNSIGNED NOT NULL, 
	process_id BIGINT UNSIGNED NOT NULL, 
	effective_from DATE NOT NULL, 
	effective_to DATE, 
	priority INTEGER NOT NULL, 
	active BOOL NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(employee_id) REFERENCES employees (id), 
	FOREIGN KEY(brand_id) REFERENCES brands (id), 
	FOREIGN KEY(process_id) REFERENCES processes (id)
) ENGINE=InnoDB;
CREATE INDEX idx_assignment_employee_dates ON assignments (employee_id, effective_from, effective_to);
CREATE INDEX idx_assignment_scope ON assignments (brand_id, process_id, active);

CREATE TABLE IF NOT EXISTS availability (
	id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT, 
	employee_id BIGINT UNSIGNED NOT NULL, 
	start_date DATE NOT NULL, 
	end_date DATE NOT NULL, 
	availability_type ENUM('WEEKLY_OFF','PLANNED_LEAVE','COMP_OFF','UNAVAILABLE') NOT NULL, 
	approval_status ENUM('PENDING','APPROVED','REJECTED') NOT NULL, 
	notes VARCHAR(255), 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(employee_id) REFERENCES employees (id)
) ENGINE=InnoDB;
CREATE INDEX idx_availability_dates ON availability (employee_id, start_date, end_date, approval_status);

CREATE TABLE IF NOT EXISTS conflicts (
	id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT, 
	roster_version_id BIGINT UNSIGNED NOT NULL, 
	roster_date DATE NOT NULL, 
	brand_id BIGINT UNSIGNED, 
	process_id BIGINT UNSIGNED, 
	employee_id BIGINT UNSIGNED, 
	conflict_type ENUM('COVERAGE_GAP','UNASSIGNED_REQUIREMENT','MULTI_BRAND_IMPACT','DOUBLE_BOOKING','INCOMPATIBLE_SHIFT','LEAVE_CONFLICT','RULE_VIOLATION','REST_VIOLATION','PREFERENCE_VIOLATION','COMP_OFF_ELIGIBLE') NOT NULL, 
	severity ENUM('ERROR','WARNING','INFO') NOT NULL, 
	required_staff INTEGER, 
	available_staff INTEGER, 
	message TEXT NOT NULL, 
	suggestion TEXT, 
	candidates_json TEXT, 
	ai_explanation TEXT, 
	resolved BOOL NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(roster_version_id) REFERENCES roster_versions (id) ON DELETE CASCADE, 
	FOREIGN KEY(brand_id) REFERENCES brands (id) ON DELETE SET NULL, 
	FOREIGN KEY(process_id) REFERENCES processes (id) ON DELETE SET NULL, 
	FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE SET NULL
) ENGINE=InnoDB;
CREATE INDEX idx_conflict_version_status ON conflicts (roster_version_id, resolved, severity);

CREATE TABLE IF NOT EXISTS employee_weekly_offs (
	id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT, 
	employee_id BIGINT UNSIGNED NOT NULL, 
	weekday INTEGER NOT NULL, 
	kind ENUM('FIXED','PREFERRED') NOT NULL, 
	effective_from DATE NOT NULL, 
	effective_to DATE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE CASCADE
) ENGINE=InnoDB;
CREATE INDEX idx_weekly_off_employee_dates ON employee_weekly_offs (employee_id, effective_from, effective_to);

CREATE TABLE IF NOT EXISTS roster_days (
	id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT, 
	roster_version_id BIGINT UNSIGNED NOT NULL, 
	employee_id BIGINT UNSIGNED NOT NULL, 
	roster_date DATE NOT NULL, 
	status ENUM('WORKING','WEEKLY_OFF','PUBLIC_HOLIDAY','LEAVE','COMP_OFF','UNAVAILABLE','UNASSIGNED') NOT NULL, 
	source ENUM('AUTO','MANUAL') NOT NULL, 
	note VARCHAR(255), 
	PRIMARY KEY (id), 
	CONSTRAINT uq_roster_day UNIQUE (roster_version_id, employee_id, roster_date), 
	FOREIGN KEY(roster_version_id) REFERENCES roster_versions (id) ON DELETE CASCADE, 
	FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE CASCADE
) ENGINE=InnoDB;
CREATE INDEX idx_roster_day_date ON roster_days (roster_version_id, roster_date);

CREATE TABLE IF NOT EXISTS roster_entries (
	id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT, 
	roster_version_id BIGINT UNSIGNED NOT NULL, 
	employee_id BIGINT UNSIGNED NOT NULL, 
	brand_id BIGINT UNSIGNED NOT NULL, 
	process_id BIGINT UNSIGNED NOT NULL, 
	roster_date DATE NOT NULL, 
	shift_start TIME, 
	shift_end TIME, 
	status ENUM('WORKING','WEEKLY_OFF','PUBLIC_HOLIDAY','LEAVE','COMP_OFF','UNASSIGNED') NOT NULL, 
	source ENUM('AUTO','MANUAL') NOT NULL, 
	is_cover BOOL NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(roster_version_id) REFERENCES roster_versions (id) ON DELETE CASCADE, 
	FOREIGN KEY(employee_id) REFERENCES employees (id), 
	FOREIGN KEY(brand_id) REFERENCES brands (id), 
	FOREIGN KEY(process_id) REFERENCES processes (id)
) ENGINE=InnoDB;
CREATE INDEX idx_roster_date_scope ON roster_entries (roster_version_id, roster_date, brand_id, process_id);
CREATE INDEX idx_roster_employee_date ON roster_entries (roster_version_id, employee_id, roster_date);

ALTER TABLE pods ADD CONSTRAINT fk_pod_lead FOREIGN KEY (lead_employee_id) REFERENCES employees(id) ON DELETE SET NULL;
