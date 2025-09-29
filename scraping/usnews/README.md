# Neurosurgeon URL Mapper

This script maps neurosurgeons from the PostgreSQL database to their US News URLs using Firecrawl.

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set up environment variables in `.env`:
```
FIRECRAWL_API_KEY=your_firecrawl_api_key
DATABASE_URL=your_database_url
```

## Usage

```bash
python neurosurgeon_url_mapper.py
```

## What it does

1. **Fetches neurosurgeons**: Gets all neurosurgeons from the `npi_providers` table (around 8k doctors)
2. **Maps by first name**: Uses Firecrawl `/map` to get all URLs for each unique first name from `https://health.usnews.com/doctors/[firstname]`
3. **Matches doctors**: For each doctor, checks if their first and last name appear in the URLs
4. **Fallback**: If not found, tries full name format (`firstname-lastname`)
5. **Outputs CSV**: Creates `neurosurgeon_urls.csv` with NPI, names, and corresponding URL (or "Not found")

## Output

The script generates a CSV file with columns:
- `npi`: Doctor's NPI number
- `first_name`: Doctor's first name
- `last_name`: Doctor's last name  
- `url`: US News URL or "Not found"

## Efficiency

- Only makes one Firecrawl call per unique first name (not per doctor)
- For example, if there are 5 doctors named "Aaron", it only calls Firecrawl once for "aaron"
- Then matches all 5 Aarons against the returned URLs
