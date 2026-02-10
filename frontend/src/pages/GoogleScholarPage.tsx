import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../services/api';
import { useTestingMode } from '../contexts/TestingModeContext';

interface ScholarResult {
  title: string;
  author: string;
  year: string;
  venue: string;
  url: string;
  num_citations: number;
}

const GoogleScholarPage: React.FC = () => {
  const { testingMode } = useTestingMode();
  const navigate = useNavigate();
  const [keyword, setKeyword] = useState<string>('');
  const [results, setResults] = useState<ScholarResult[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchedKeyword, setSearchedKeyword] = useState<string | null>(null);

  if (!testingMode) {
    navigate('/');
    return null;
  }

  const handleSearch = async () => {
    if (!keyword.trim()) {
      setError('Please enter a search keyword');
      return;
    }

    setIsLoading(true);
    setError(null);
    setResults([]);
    setSearchedKeyword(keyword.trim());

    try {
      const response = await api.get('/api/v1/google-scholar/search', {
        params: { q: keyword.trim(), limit: 10 },
      });
      setResults(response.data.results || []);
      if (response.data.results && response.data.results.length === 0) {
        setError('No results found');
      }
    } catch (err: any) {
      console.error('Error fetching Google Scholar results:', err);
      setError(err.response?.data?.detail || err.message || 'Failed to search Google Scholar');
      setResults([]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      handleSearch();
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
          <h1 className="text-3xl font-bold text-gray-900 mb-6">Google Scholar</h1>

          {/* Search Section */}
          <div className="mb-6">
            <label htmlFor="keyword-input" className="block text-sm font-medium text-gray-700 mb-2">
              Search keyword
            </label>
            <div className="flex gap-3">
              <input
                id="keyword-input"
                type="text"
                value={keyword}
                onChange={(e) => setKeyword(e.target.value)}
                onKeyPress={handleKeyPress}
                placeholder="Enter search keyword (e.g., pituitary adenoma surgery)"
                className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-sm"
              />
              <button
                onClick={handleSearch}
                disabled={isLoading || !keyword.trim()}
                className="px-6 py-2 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                {isLoading ? (
                  <span className="flex items-center gap-2">
                    <svg className="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                    Searching...
                  </span>
                ) : (
                  'Search'
                )}
              </button>
            </div>
            <p className="mt-2 text-xs text-gray-500">
              Uses the scholarly Python package. Results may be rate-limited by Google.
            </p>
          </div>

          {/* Error Message */}
          {error && (
            <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg">
              <p className="text-sm text-red-800">{error}</p>
            </div>
          )}

          {/* Results Section */}
          {searchedKeyword && (
            <div className="mt-6">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-xl font-semibold text-gray-900">
                  Results for: <span className="font-normal text-gray-700">&quot;{searchedKeyword}&quot;</span>
                </h2>
                {results.length > 0 && (
                  <span className="text-sm text-gray-600">
                    {results.length} {results.length === 1 ? 'result' : 'results'}
                  </span>
                )}
              </div>

              {results.length > 0 ? (
                <div className="space-y-4 max-h-[32rem] overflow-y-auto">
                  {results.map((pub, index) => (
                    <div key={index} className="bg-gray-50 rounded-lg p-4 border border-gray-200">
                      <h3 className="font-medium text-gray-900 mb-1 line-clamp-2">{pub.title}</h3>
                      <p className="text-sm text-gray-600">{pub.author}</p>
                      <div className="flex flex-wrap gap-2 mt-2 text-xs text-gray-500">
                        {pub.year && <span>{pub.year}</span>}
                        {pub.venue && <span>• {pub.venue}</span>}
                        {pub.num_citations > 0 && (
                          <span>• {pub.num_citations} citation{pub.num_citations !== 1 ? 's' : ''}</span>
                        )}
                      </div>
                      {pub.url && (
                        <a
                          href={pub.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-block mt-2 text-sm text-blue-600 hover:text-blue-800 hover:underline"
                        >
                          View on Google Scholar →
                        </a>
                      )}
                    </div>
                  ))}
                </div>
              ) : !isLoading && !error && (
                <div className="text-center py-8 text-gray-500">
                  <p>No results found.</p>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default GoogleScholarPage;
