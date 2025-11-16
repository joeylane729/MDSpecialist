#!/usr/bin/env python3
"""
Upload PubMed data into pubmed_articles with JSONB columns per spec.
"""

import os
import json
import io
import logging
from logging.handlers import RotatingFileHandler
import xml.etree.ElementTree as ET
from datetime import date
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
import psycopg2

load_dotenv()


# --- Logging setup ---
logger = logging.getLogger("pubmed_upload")
if not logger.handlers:
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')

    # Stream to console
    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.INFO)
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    # Rotating file in project root
    log_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'pubmed_upload.log'))
    file_handler = RotatingFileHandler(log_path, maxBytes=10*1024*1024, backupCount=3)
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)


def safe_text(elem: Optional[ET.Element]) -> str:
    return (elem.text or "").strip() if elem is not None and elem.text else ""


def parse_date(y: Optional[str], m: Optional[str], d: Optional[str]) -> Optional[str]:
    try:
        if not y:
            return None
        yi = int(y)
        mi = int(m) if m and m.isdigit() else 1
        di = int(d) if d and d.isdigit() else 1
        return date(yi, mi, di).isoformat()
    except Exception:
        return None


def month_to_int(m: Optional[str]) -> Optional[int]:
    if not m:
        return None
    mm = m.lower()
    mapping = {
        'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
        'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12,
        'january': 1, 'february': 2, 'march': 3, 'april': 4, 'june': 6,
        'july': 7, 'august': 8, 'september': 9, 'october': 10, 'november': 11, 'december': 12
    }
    return mapping.get(mm)


def element_full_text(elem: Optional[ET.Element]) -> str:
    """Return concatenated text content including child tags (e.g., <i>).</"""
    if elem is None:
        return ""
    return "".join(list(elem.itertext())).strip()


def parse_medline_date_to_iso(medline_date: str) -> Optional[str]:
    """Convert MedlineDate strings (e.g., '2023 Jan-Jun', '2023 Mar-Apr', '2023', '2023 Spring')
    to an ISO date using the earliest plausible day in that period.

    Rules:
    - Year only -> YYYY-01-01
    - Year + Month -> YYYY-MM-01
    - Year + Month-Month (range) -> YYYY-(first month)-01
    - Seasons -> Spring=Mar, Summer=Jun, Fall/Autumn=Sep, Winter=Dec
    - Fallback: return None
    """
    if not medline_date:
        return None
    s = medline_date.strip()
    # Normalize separators
    s = s.replace('–', '-').replace('—', '-').replace('\u2013', '-').replace('\u2014', '-')
    parts = s.split()
    if not parts:
        return None
    # Year detection
    try:
        yr = int(parts[0])
    except Exception:
        return None

    # Season mapping
    season_map = {
        'spring': 3,
        'summer': 6,
        'fall': 9,
        'autumn': 9,
        'winter': 12,
    }

    # If only year
    if len(parts) == 1:
        try:
            return date(yr, 1, 1).isoformat()
        except Exception:
            return None

    token = parts[1].lower()
    # Season
    if token in season_map:
        try:
            return date(yr, season_map[token], 1).isoformat()
        except Exception:
            return None

    # Month or range
    # Examples: 'Jan', 'Jan-Jun', 'Mar-Apr'
    rng = token.split('-')
    first = rng[0]
    mm = month_to_int(first)
    if mm:
        try:
            return date(yr, mm, 1).isoformat()
        except Exception:
            return None

    # If not matched, try later token (some strings like 'Jan-Jun,' with punctuation)
    token = token.strip(',;')
    rng = token.split('-')
    first = rng[0]
    mm = month_to_int(first)
    if mm:
        try:
            return date(yr, mm, 1).isoformat()
        except Exception:
            return None
    return None


def create_table(engine):
    sql = """
    CREATE TABLE IF NOT EXISTS pubmed_articles (
        pmid BIGINT PRIMARY KEY,
        title TEXT,
        journal_title TEXT,
        journal_abbrev TEXT,
        issn TEXT,
        pub_date DATE,
        doi TEXT,
        abstract TEXT,
        authors JSONB,
        mesh_terms JSONB,
        chemicals JSONB,
        grants JSONB,
        citations JSONB,
        publication_types JSONB,
        journal_country TEXT,
        language TEXT,
        date_completed DATE,
        date_revised DATE
    );
    CREATE INDEX IF NOT EXISTS idx_pubmed_articles_pub_date ON pubmed_articles(pub_date);
    CREATE INDEX IF NOT EXISTS idx_pubmed_articles_language ON pubmed_articles(language);
    CREATE INDEX IF NOT EXISTS idx_pubmed_articles_journal_country ON pubmed_articles(journal_country);
    """
    with engine.connect() as conn:
        conn.execute(text(sql))
        conn.commit()


def create_stage_table(cur):
    cur.execute(
        """
        CREATE UNLOGGED TABLE IF NOT EXISTS pubmed_stage (
            pmid BIGINT,
            title TEXT,
            journal_title TEXT,
            journal_abbrev TEXT,
            issn TEXT,
            pub_date TEXT,
            doi TEXT,
            abstract TEXT,
            authors TEXT,
            mesh_terms TEXT,
            chemicals TEXT,
            grants TEXT,
            citations TEXT,
            publication_types TEXT,
            journal_country TEXT,
            language TEXT,
            date_completed TEXT,
            date_revised TEXT
        );
        TRUNCATE TABLE pubmed_stage;
        """
    )


def parse_article(article_el: ET.Element) -> Optional[Dict[str, Any]]:
    try:
        medline = article_el.find('.//MedlineCitation')
        if medline is None:
            medline = article_el  # fallback

        pmid_text = safe_text(medline.find('PMID'))
        if not pmid_text or not pmid_text.isdigit():
            return None
        pmid = int(pmid_text)

        article = medline.find('Article')
        # Try ArticleTitle first, fallback to VernacularTitle if empty
        title = element_full_text(article.find('ArticleTitle')) if article is not None else ""
        if not title and article is not None:
            title = element_full_text(article.find('VernacularTitle')) or ""
        journal_title = safe_text(article.find('.//Journal/Title')) if article is not None else ""
        journal_abbrev = safe_text(article.find('.//Journal/ISOAbbreviation')) if article is not None else ""
        issn = safe_text(article.find('.//Journal/ISSN')) if article is not None else ""

        # pub_date (prefer earliest available in JournalIssue PubDate)
        pub_date_el = article.find('.//Journal/JournalIssue/PubDate') if article is not None else None
        y = safe_text(pub_date_el.find('Year')) if pub_date_el is not None else None
        m_raw = safe_text(pub_date_el.find('Month')) if pub_date_el is not None else None
        d = safe_text(pub_date_el.find('Day')) if pub_date_el is not None else None
        m = str(month_to_int(m_raw)) if m_raw and not m_raw.isdigit() else m_raw
        pub_date_iso = parse_date(y, m, d)
        if not pub_date_iso and pub_date_el is not None:
            # Fallback to MedlineDate ranges
            medline_date = safe_text(pub_date_el.find('MedlineDate'))
            pub_date_iso = parse_medline_date_to_iso(medline_date)

        # DOI
        doi = safe_text(article.find(".//ELocationID[@EIdType='doi']")) if article is not None else ""

        # abstract
        abstract = ""
        abstract_el = article.find('Abstract') if article is not None else None
        if abstract_el is not None:
            parts = []
            for t in abstract_el.findall('.//AbstractText'):
                txt = "".join(list(t.itertext())).strip()
                if txt:
                    parts.append(txt)
            abstract = " ".join(parts)

        # language
        language = safe_text(article.find('Language')) if article is not None else ""

        # publication status (removed from storage)

        # Authors JSONB
        authors_json: List[Dict[str, Any]] = []
        for a in article.findall('.//AuthorList/Author') if article is not None else []:
            lastname = safe_text(a.find('LastName'))
            forename = safe_text(a.find('ForeName'))
            initials = safe_text(a.find('Initials'))
            orcid = safe_text(a.find("Identifier[@Source='ORCID']"))
            affiliations = [safe_text(aff) for aff in a.findall('.//Affiliation') if safe_text(aff)]
            # Include author if any name field or affiliations or orcid exist
            if lastname or forename or initials or affiliations or orcid:
                authors_json.append({
                    "lastname": lastname,
                    "forename": forename,
                    "initials": initials,
                    "orcid": orcid,
                    "affiliations": affiliations
                })

        # MeSH JSONB
        mesh_terms: List[Dict[str, Any]] = []
        for mh in medline.findall('.//MeshHeading'):
            desc = mh.find('DescriptorName')
            term = safe_text(desc)
            major = (desc.get('MajorTopicYN') == 'Y') if desc is not None else False
            qualifiers = [safe_text(q) for q in mh.findall('QualifierName') if safe_text(q)]
            if term:
                mesh_terms.append({
                    "term": term,
                    "major": major,
                    "qualifiers": qualifiers
                })

        # Chemicals JSONB
        chemicals: List[Dict[str, Any]] = []
        for ch in medline.findall('.//Chemical'):
            name = safe_text(ch.find('NameOfSubstance'))
            reg = safe_text(ch.find('RegistryNumber'))
            if name or reg:
                chemicals.append({"name": name, "registry_number": reg})

        # Grants JSONB
        grants: List[Dict[str, Any]] = []
        for gr in medline.findall('.//Grant'):
            gid = safe_text(gr.find('GrantID'))
            agency = safe_text(gr.find('Agency'))
            country = safe_text(gr.find('Country'))
            if gid or agency or country:
                grants.append({"id": gid, "agency": agency, "country": country})

        # Citations JSONB (from ReferenceList if present)
        citations: List[Dict[str, Any]] = []
        for ref in medline.findall('.//Reference'):
            citation = safe_text(ref.find('Citation'))
            pmid_ref = None
            for aid in ref.findall('.//ArticleId'):
                if aid.get('IdType') == 'pubmed' and safe_text(aid):
                    try:
                        pmid_ref = int(safe_text(aid))
                        break
                    except Exception:
                        pass
            citations.append({"citation": citation, "pmid": pmid_ref})

        # Publication types JSONB
        publication_types: List[str] = []
        for pt in article.findall('.//PublicationType') if article is not None else []:
            if safe_text(pt):
                publication_types.append(safe_text(pt))

        # Journal Country
        country = safe_text(medline.find('.//MedlineJournalInfo/Country'))

        # DateCompleted and DateRevised
        dc = medline.find('DateCompleted')
        dr = medline.find('DateRevised')
        dc_iso = parse_date(safe_text(dc.find('Year')) if dc is not None else None,
                            safe_text(dc.find('Month')) if dc is not None else None,
                            safe_text(dc.find('Day')) if dc is not None else None)
        dr_iso = parse_date(safe_text(dr.find('Year')) if dr is not None else None,
                            safe_text(dr.find('Month')) if dr is not None else None,
                            safe_text(dr.find('Day')) if dr is not None else None)

        return {
            'pmid': pmid,
            'title': title,
            'journal_title': journal_title,
            'journal_abbrev': journal_abbrev,
            'issn': issn,
            'pub_date': pub_date_iso,
            'doi': doi,
            'abstract': abstract,
            'authors': json.dumps(authors_json),
            'mesh_terms': json.dumps(mesh_terms),
            'chemicals': json.dumps(chemicals),
            'grants': json.dumps(grants),
            'citations': json.dumps(citations),
            'publication_types': json.dumps(publication_types),
            'journal_country': country,
            'language': language,
            'date_completed': dc_iso,
            'date_revised': dr_iso
        }
    except Exception:
        return None


def main():
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        logger.error('❌ DATABASE_URL is not set')
        return
    engine = create_engine(database_url)

    # Discover all PubMed XML files. Prefer backend/data/pubmed; fallback to data/pubmed at repo root.
    script_dir = os.path.dirname(os.path.abspath(__file__))
    candidate_dirs = [
        os.path.abspath(os.path.join(script_dir, '..', 'backend', 'data', 'pubmed')),
        os.path.abspath(os.path.join(script_dir, '..', 'data', 'pubmed')),
    ]
    pubmed_dir = next((d for d in candidate_dirs if os.path.isdir(d)), None)
    if not pubmed_dir:
        logger.error('❌ No pubmed directory found. Looked in:')
        for d in candidate_dirs:
            logger.error(f'   - {d}')
        return
    xml_files = sorted(
        [os.path.join(pubmed_dir, f) for f in os.listdir(pubmed_dir) if f.lower().endswith('.xml')]
    )
    if not xml_files:
        logger.error(f'❌ No .xml files found in: {pubmed_dir}')
        return

    logger.info('🔧 Creating table pubmed_articles...')
    create_table(engine)

    # psycopg2 connection for high-throughput COPY
    dsn = database_url
    with psycopg2.connect(dsn) as pgconn:
        pgconn.autocommit = False
        with pgconn.cursor() as cur:
            # Speed-friendly session settings
            cur.execute("SET synchronous_commit = off")
            cur.execute("SET work_mem = '128MB'")
            create_stage_table(cur)

            logger.info('📤 Streaming parse + COPY into staging from multiple files...')
            columns = [
                'pmid','title','journal_title','journal_abbrev','issn','pub_date','doi','abstract',
                'authors','mesh_terms','chemicals','grants','citations','publication_types',
                'journal_country','language','date_completed','date_revised'
            ]

            def sanitize(val: Optional[str]) -> str:
                if val is None:
                    return '\\N'
                # Replace tabs/newlines and escape backslashes so JSON text remains valid under COPY text format
                s = str(val).replace('\t', ' ').replace('\r', ' ').replace('\n', ' ')
                s = s.replace('\\', '\\\\')
                return s.strip()

            total_rows = 0
            batch_size_rows = 20000
            files_processed = 0

            for xml_path in xml_files:
                logger.info(f'📄 Processing file: {os.path.basename(xml_path)}')
                if not os.path.exists(xml_path):
                    logger.warning(f'   ⚠️ Skipping missing file: {xml_path}')
                    continue

                buffer = io.StringIO()
                batch_rows = 0

                for event, elem in ET.iterparse(xml_path, events=("end",)):
                    tag = elem.tag if isinstance(elem.tag, str) else ""
                    if tag.endswith('PubmedArticle'):
                        rec = parse_article(elem)
                        if rec:
                            row = [
                                str(rec['pmid']),
                                sanitize(rec['title']),
                                sanitize(rec['journal_title']),
                                sanitize(rec['journal_abbrev']),
                                sanitize(rec['issn']),
                                sanitize(rec['pub_date'] or ''),
                                sanitize(rec['doi']),
                                sanitize(rec['abstract']),
                                sanitize(rec['authors']),
                                sanitize(rec['mesh_terms']),
                                sanitize(rec['chemicals']),
                                sanitize(rec['grants']),
                                sanitize(rec['citations']),
                                sanitize(rec['publication_types']),
                                sanitize(rec['journal_country']),
                                sanitize(rec['language']),
                                sanitize(rec['date_completed'] or ''),
                                sanitize(rec['date_revised'] or '')
                            ]
                            buffer.write('\t'.join(row) + '\n')
                            batch_rows += 1
                            total_rows += 1
                            if total_rows % 1000 == 0:
                                logger.info(f'   Parsed {total_rows} total records...')
                        # free memory for processed subtree
                        elem.clear()

                        if batch_rows >= batch_size_rows:
                            buffer.seek(0)
                            cur.copy_from(buffer, 'pubmed_stage', sep='\t', null='\\N', columns=columns)
                            pgconn.commit()
                            logger.info(f'✅ COPY batch -> staging. Total rows copied so far: {total_rows}')
                            buffer = io.StringIO()
                            batch_rows = 0

                # flush remaining for this file
                if batch_rows > 0:
                    buffer.seek(0)
                    cur.copy_from(buffer, 'pubmed_stage', sep='\t', null='\\N', columns=columns)
                    pgconn.commit()
                    logger.info(f'✅ COPY final batch for {os.path.basename(xml_path)} -> staging. Total rows copied so far: {total_rows}')
                # Merge from staging to final with proper casts (per-file) in 100k pmid chunks
                logger.info('🔄 Merging this file from staging -> pubmed_articles in 100k pmid chunks...')
                cur.execute("SELECT MIN(pmid), MAX(pmid) FROM pubmed_stage")
                bounds = cur.fetchone()
                if bounds and bounds[0] is not None and bounds[1] is not None:
                    min_pmid, max_pmid = int(bounds[0]), int(bounds[1])
                    chunk_size = 100_000
                    current = (min_pmid // chunk_size) * chunk_size
                    if current > min_pmid:
                        current -= chunk_size
                    if current < 0:
                        current = 0
                    while current <= max_pmid:
                        end = current + chunk_size - 1
                        logger.info(f"   Merging pmid {max(current, min_pmid):,}–{min(end, max_pmid):,}")
                        cur.execute(
                            """
                            WITH dedup AS (
                                SELECT *,
                                       ROW_NUMBER() OVER (PARTITION BY pmid ORDER BY COALESCE(LENGTH(title),0) DESC) AS rn
                                FROM pubmed_stage
                                       WHERE pmid BETWEEN %s AND %s
                            )
                            INSERT INTO pubmed_articles (
                                pmid, title, journal_title, journal_abbrev, issn, pub_date, doi, abstract,
                                authors, mesh_terms, chemicals, grants, citations, publication_types,
                                journal_country, language, date_completed, date_revised
                            )
                            SELECT
                                pmid,
                                title,
                                journal_title,
                                journal_abbrev,
                                issn,
                                NULLIF(pub_date,'')::date,
                                doi,
                                abstract,
                                authors::jsonb,
                                mesh_terms::jsonb,
                                chemicals::jsonb,
                                grants::jsonb,
                                citations::jsonb,
                                publication_types::jsonb,
                                journal_country,
                                language,
                                NULLIF(date_completed,'')::date,
                                NULLIF(date_revised,'')::date
                            FROM dedup
                            WHERE rn = 1
                            ON CONFLICT (pmid) DO UPDATE SET
                                title = EXCLUDED.title,
                                abstract = EXCLUDED.abstract,
                                journal_title = EXCLUDED.journal_title,
                                doi = EXCLUDED.doi,
                                authors = EXCLUDED.authors,
                                mesh_terms = EXCLUDED.mesh_terms,
                                chemicals = EXCLUDED.chemicals,
                                grants = EXCLUDED.grants,
                                citations = EXCLUDED.citations,
                                publication_types = EXCLUDED.publication_types,
                                pub_date = COALESCE(EXCLUDED.pub_date, pubmed_articles.pub_date),
                                journal_country = EXCLUDED.journal_country,
                                language = EXCLUDED.language,
                                date_completed = COALESCE(EXCLUDED.date_completed, pubmed_articles.date_completed),
                                date_revised   = COALESCE(EXCLUDED.date_revised,   pubmed_articles.date_revised)
                            """,
                            (max(current, min_pmid), min(end, max_pmid))
                        )
                        pgconn.commit()
                        current += chunk_size
                else:
                    logger.info('   No rows found in staging for this file.')
                logger.info('🧹 TRUNCATE staging after merge to free space')
                cur.execute('TRUNCATE TABLE pubmed_stage')
                pgconn.commit()
                files_processed += 1
                if files_processed % 10 == 0:
                    logger.info('🧽 Running VACUUM pubmed_articles after 10 files to free temp space')
                    # VACUUM must run outside transaction block - use separate connection
                    pgconn.commit()  # Ensure all pending work is committed
                    try:
                        vac_conn = psycopg2.connect(dsn)
                        vac_conn.autocommit = True
                        try:
                            with vac_conn.cursor() as vac_cur:
                                vac_cur.execute("VACUUM pubmed_articles;")
                        finally:
                            vac_conn.close()
                    except psycopg2.OperationalError as e:
                        logger.warning(f'⚠️ VACUUM skipped due to connection error: {e}')

    with engine.connect() as conn:
        cnt = conn.execute(text('SELECT COUNT(*) FROM pubmed_articles')).scalar()
        logger.info(f'🎉 Done. Rows in pubmed_articles: {cnt}')


if __name__ == '__main__':
    main()
