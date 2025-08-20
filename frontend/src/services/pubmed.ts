import axios from 'axios';

const PUBMED_API_KEY = '550c63b2e654e0300b5df904520d7df94208';
const BASE_URL = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils';

export interface PubMedPublication {
  id: string;
  title: string;
  authors: string[];
  journal: string;
  publicationDate: string;
  abstract?: string;
  doi?: string;
  pmid: string;
}

export interface PubMedSearchResponse {
  publications: PubMedPublication[];
  totalCount: number;
}

/**
 * Search PubMed for publications by author name
 * @param authorName - The author's name to search for
 * @param maxResults - Maximum number of results to return (default: 5)
 * @returns Promise with publications array
 */
export const searchAuthorPublications = async (
  authorName: string,
  maxResults: number = 5
): Promise<PubMedPublication[]> => {
  try {
    // Step 1: Search for the author to get publication IDs
    const searchUrl = `${BASE_URL}/esearch.fcgi`;
    const searchParams = new URLSearchParams({
      db: 'pubmed',
      term: `"${authorName}"[Author]`,
      retmax: maxResults.toString(),
      retmode: 'json',
      sort: 'relevance',
      api_key: PUBMED_API_KEY
    });

    const searchResponse = await axios.get(`${searchUrl}?${searchParams}`);
    
    if (!searchResponse.data.esearchresult || !searchResponse.data.esearchresult.idlist) {
      return [];
    }

    const publicationIds = searchResponse.data.esearchresult.idlist;
    
    if (publicationIds.length === 0) {
      return [];
    }

    // Step 2: Fetch detailed information for each publication
    const fetchUrl = `${BASE_URL}/efetch.fcgi`;
    const fetchParams = new URLSearchParams({
      db: 'pubmed',
      id: publicationIds.join(','),
      retmode: 'xml',
      api_key: PUBMED_API_KEY
    });

    const fetchResponse = await axios.get(`${fetchUrl}?${fetchParams}`);
    
    // Parse XML response to extract publication details
    const publications = parsePubMedXML(fetchResponse.data, publicationIds);
    
    return publications;
  } catch (error) {
    console.error('Error fetching PubMed publications:', error);
    return [];
  }
};

/**
 * Parse PubMed XML response to extract publication details
 * @param xmlData - Raw XML response from PubMed
 * @param publicationIds - Array of publication IDs
 * @returns Array of parsed publications
 */
const parsePubMedXML = (xmlData: string, publicationIds: string[]): PubMedPublication[] => {
  const publications: PubMedPublication[] = [];
  
  try {
    // Create a DOM parser to parse the XML
    const parser = new DOMParser();
    const xmlDoc = parser.parseFromString(xmlData, 'text/xml');
    
    // Find all article elements
    const articles = xmlDoc.querySelectorAll('PubmedArticle');
    
    articles.forEach((article, index) => {
      if (index >= publicationIds.length) return;
      
      const pmid = publicationIds[index];
      
      // Extract title
      const titleElement = article.querySelector('ArticleTitle');
      const title = titleElement?.textContent || 'No title available';
      
      // Extract authors
      const authorElements = article.querySelectorAll('Author');
      const authors: string[] = [];
      authorElements.forEach(author => {
        const lastName = author.querySelector('LastName')?.textContent;
        const foreName = author.querySelector('ForeName')?.textContent;
        if (lastName && foreName) {
          authors.push(`${foreName} ${lastName}`);
        } else if (lastName) {
          authors.push(lastName);
        }
      });
      
      // Extract journal information
      const journalElement = article.querySelector('Journal');
      const journalTitle = journalElement?.querySelector('Title')?.textContent || 'Unknown journal';
      
      // Extract publication date
      const pubDateElement = article.querySelector('PubDate');
      let publicationDate = 'Unknown date';
      if (pubDateElement) {
        const year = pubDateElement.querySelector('Year')?.textContent;
        const month = pubDateElement.querySelector('Month')?.textContent;
        if (year) {
          publicationDate = month ? `${month} ${year}` : year;
        }
      }
      
      // Extract abstract
      const abstractElement = article.querySelector('AbstractText');
      const abstract = abstractElement?.textContent || undefined;
      
      // Extract DOI if available
      const doiElement = article.querySelector('ELocationID[EIdType="doi"]');
      const doi = doiElement?.textContent || undefined;
      
      publications.push({
        id: pmid,
        pmid,
        title,
        authors,
        journal: journalTitle,
        publicationDate,
        abstract: abstract || undefined,
        doi: doi || undefined
      });
    });
  } catch (error) {
    console.error('Error parsing PubMed XML:', error);
  }
  
  return publications;
};

/**
 * Alternative method using PubMed's JSON API (more reliable parsing)
 * @param authorName - The author's name to search for
 * @param maxResults - Maximum number of results to return (default: 5)
 * @returns Promise with publications array
 */
export const searchAuthorPublicationsJSON = async (
  authorName: string,
  maxResults: number = 5,
  exactMatch: boolean = true,
  fieldType: 'author' | 'full' = 'author'
): Promise<PubMedPublication[]> => {
  try {
    let searchTerm: string;
    if (fieldType === 'full') {
      searchTerm = `${authorName}[Full Author Name]`;
    } else {
      searchTerm = exactMatch ? `"${authorName}"[Author]` : `${authorName}[Author]`;
    }
    console.log(`Searching PubMed for author: ${searchTerm}`);
    
    // Use the summary API which returns JSON
    const searchUrl = `${BASE_URL}/esearch.fcgi`;
    const searchParams = new URLSearchParams({
      db: 'pubmed',
      term: searchTerm,
      retmax: maxResults.toString(),
      retmode: 'json',
      sort: 'relevance',
      api_key: PUBMED_API_KEY
    });

    const searchResponse = await axios.get(`${searchUrl}?${searchParams}`);
    console.log('PubMed search response:', searchResponse.data);
    
    if (!searchResponse.data.esearchresult || !searchResponse.data.esearchresult.idlist) {
      console.log('No search results found');
      return [];
    }

    const publicationIds = searchResponse.data.esearchresult.idlist;
    console.log(`Found ${publicationIds.length} publication IDs:`, publicationIds);
    
    if (publicationIds.length === 0) {
      return [];
    }

    // Get summaries for the publications
    const summaryUrl = `${BASE_URL}/esummary.fcgi`;
    const summaryParams = new URLSearchParams({
      db: 'pubmed',
      id: publicationIds.join(','),
      retmode: 'json',
      api_key: PUBMED_API_KEY
    });

    const summaryResponse = await axios.get(`${summaryUrl}?${summaryParams}`);
    console.log('PubMed summary response structure:', Object.keys(summaryResponse.data.result || {}));
    
    const publications: PubMedPublication[] = [];
    
    if (summaryResponse.data.result && summaryResponse.data.result.uids) {
      const uids = summaryResponse.data.result.uids;
      
      uids.forEach((uid: string) => {
        const pubData = summaryResponse.data.result[uid];
        if (pubData) {
          console.log(`Processing publication ${uid}:`, pubData);
          
          const authors = pubData.authors || [];
          const authorNames = authors.map((author: any) => 
            author.name || `${author.lastname || ''} ${author.forename || ''}`.trim()
          ).filter((name: string) => name.length > 0);
          
          publications.push({
            id: uid,
            pmid: uid,
            title: pubData.title || 'No title available',
            authors: authorNames,
            journal: pubData.fulljournalname || 'Unknown journal',
            publicationDate: pubData.pubdate || 'Unknown date',
            abstract: pubData.abstract,
            doi: pubData.articleids?.find((id: any) => id.idtype === 'doi')?.value
          });
        }
      });
    }
    
    console.log(`Returning ${publications.length} publications`);
    return publications;
  } catch (error) {
    console.error('Error fetching PubMed publications (JSON):', error);
    if (axios.isAxiosError(error)) {
      console.error('Response status:', error.response?.status);
      console.error('Response data:', error.response?.data);
    }
    return [];
  }
};
