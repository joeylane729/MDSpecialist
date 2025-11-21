-- Find all doctors who have a medical school entry that only contains "MD" or "M.D." 
-- and NOT "Medical School"
-- 
-- This catches cases where the parser found an institution followed by "M.D." or "MD"
-- but not explicitly labeled as "Medical School"
--
-- Note: medical_school can contain multiple entries separated by " | "
-- This query finds any entry that has MD/M.D. but no "Medical School" label

SELECT 
    u.npi,
    n.provider_first_name,
    n.provider_last_name,
    u.medical_school
FROM usnews_data u
JOIN npi_providers n ON u.npi = n.npi
WHERE 
    -- Medical school field exists and is not empty
    u.medical_school IS NOT NULL 
    AND u.medical_school != ''
    -- Contains MD or M.D. (case-insensitive, with parentheses)
    AND (
        UPPER(u.medical_school) LIKE '%(MD)%' 
        OR UPPER(u.medical_school) LIKE '%(M.D.)%'
        OR UPPER(u.medical_school) LIKE '%(M D)%'
        OR UPPER(u.medical_school) LIKE '% MD %'
        OR UPPER(u.medical_school) LIKE '% M.D. %'
    )
    -- Does NOT contain "Medical School" anywhere in the field
    AND UPPER(u.medical_school) NOT LIKE '%MEDICAL SCHOOL%'
ORDER BY n.provider_last_name, n.provider_first_name;

