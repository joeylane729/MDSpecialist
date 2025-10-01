-- Create npi_medical_school_mapping table
-- This table maps NPI numbers to medical school ranking IDs

CREATE TABLE IF NOT EXISTS npi_medical_school_mapping (
    id SERIAL PRIMARY KEY,
    npi VARCHAR(10) NOT NULL,
    medical_school_id INTEGER NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Foreign key constraint
    CONSTRAINT fk_npi_medical_school_mapping_medical_school_id 
        FOREIGN KEY (medical_school_id) 
        REFERENCES medical_school_rankings(id),
    
    -- Unique constraint to ensure one medical school per NPI
    CONSTRAINT uq_npi_medical_school_mapping_npi 
        UNIQUE (npi)
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_npi_medical_school_mapping_npi 
    ON npi_medical_school_mapping(npi);

CREATE INDEX IF NOT EXISTS idx_npi_medical_school_mapping_medical_school_id 
    ON npi_medical_school_mapping(medical_school_id);

-- Add comments for documentation
COMMENT ON TABLE npi_medical_school_mapping IS 'Maps NPI providers to their medical school rankings';
COMMENT ON COLUMN npi_medical_school_mapping.npi IS 'National Provider Identifier (10 digits)';
COMMENT ON COLUMN npi_medical_school_mapping.medical_school_id IS 'Foreign key to medical_school_rankings.id';

-- Verify table creation
SELECT 
    table_name,
    column_name,
    data_type,
    is_nullable,
    column_default
FROM information_schema.columns 
WHERE table_name = 'npi_medical_school_mapping'
ORDER BY ordinal_position;
