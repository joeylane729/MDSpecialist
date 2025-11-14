-- Create functional indexes on normalized ISSN columns for faster JOINs
-- This allows PostgreSQL to use indexes when matching normalized ISSNs

-- Index on normalized journals.issn (for exact match JOIN lookups)
-- This helps with the most common case: exact ISSN match
CREATE INDEX IF NOT EXISTS idx_journals_issn_normalized 
ON journals (REPLACE(REPLACE(COALESCE(issn, ''), '-', ''), ' ', ''))
WHERE issn IS NOT NULL AND issn != '';

-- Regular index on pubmed_articles.issn for WHERE clause filtering
CREATE INDEX IF NOT EXISTS idx_pubmed_articles_issn 
ON pubmed_articles (issn)
WHERE issn IS NOT NULL AND issn != '';

-- Index on pubmed_articles.pmid for ORDER BY (if not already exists)
CREATE INDEX IF NOT EXISTS idx_pubmed_articles_pmid_desc 
ON pubmed_articles (pmid DESC);

-- Analyze tables to update statistics for query planner
ANALYZE journals;
ANALYZE pubmed_articles;
