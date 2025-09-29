-- Create usnews_data table
CREATE TABLE IF NOT EXISTS usnews_data (
    id SERIAL PRIMARY KEY,
    npi VARCHAR(20) NOT NULL,
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    markdown_file TEXT,
    medical_school TEXT,
    residency TEXT,
    fellowship TEXT,
    certifications TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create healthgrades_data table
CREATE TABLE IF NOT EXISTS healthgrades_data (
    id SERIAL PRIMARY KEY,
    npi VARCHAR(20) NOT NULL,
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    filenames TEXT,
    specialties TEXT,
    medical_school TEXT,
    residency TEXT,
    fellowship TEXT,
    certifications TEXT,
    matching_method VARCHAR(100),
    matching_notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_usnews_npi ON usnews_data(npi);
CREATE INDEX IF NOT EXISTS idx_healthgrades_npi ON healthgrades_data(npi);
CREATE INDEX IF NOT EXISTS idx_usnews_names ON usnews_data(first_name, last_name);
CREATE INDEX IF NOT EXISTS idx_healthgrades_names ON healthgrades_data(first_name, last_name);
