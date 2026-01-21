import React, { useState } from 'react';
import { api } from '../services/api';

interface CPTCode {
  code: string;
  description: string;
}

const CPTTestingPage: React.FC = () => {
  const [icd10Code, setIcd10Code] = useState<string>('');
  const [cptCodes, setCptCodes] = useState<CPTCode[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchedIcd10, setSearchedIcd10] = useState<string | null>(null);

  const handleSearch = async () => {
    if (!icd10Code.trim()) {
      setError('Please enter an ICD-10 code');
      return;
    }

    setIsLoading(true);
    setError(null);
    setCptCodes([]);
    setSearchedIcd10(icd10Code.trim().toUpperCase());

    try {
      const response = await api.get(`/api/v1/medical-analysis/cpt-codes-by-icd10/${encodeURIComponent(icd10Code.trim())}`);
      setCptCodes(response.data.cpt_codes || []);
      if (response.data.cpt_codes && response.data.cpt_codes.length === 0) {
        setError('No CPT codes found for this ICD-10 code');
      }
    } catch (err: any) {
      console.error('Error fetching CPT codes:', err);
      setError(err.response?.data?.detail || err.message || 'Failed to fetch CPT codes');
      setCptCodes([]);
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
          <h1 className="text-3xl font-bold text-gray-900 mb-6">CPT Testing</h1>
          
          {/* Search Section */}
          <div className="mb-6">
            <label htmlFor="icd10-input" className="block text-sm font-medium text-gray-700 mb-2">
              ICD-10 Code
            </label>
            <div className="flex gap-3">
              <input
                id="icd10-input"
                type="text"
                value={icd10Code}
                onChange={(e) => setIcd10Code(e.target.value)}
                onKeyPress={handleKeyPress}
                placeholder="Enter ICD-10 code (e.g., D35.2)"
                className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-sm"
              />
              <button
                onClick={handleSearch}
                disabled={isLoading || !icd10Code.trim()}
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
              Codes starting with "98" or "99" are automatically excluded from results.
            </p>
          </div>

          {/* Error Message */}
          {error && (
            <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg">
              <p className="text-sm text-red-800">{error}</p>
            </div>
          )}

          {/* Results Section */}
          {searchedIcd10 && (
            <div className="mt-6">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-xl font-semibold text-gray-900">
                  Results for ICD-10: <code className="bg-gray-100 px-2 py-1 rounded text-sm font-mono">{searchedIcd10}</code>
                </h2>
                {cptCodes.length > 0 && (
                  <span className="text-sm text-gray-600">
                    {cptCodes.length} {cptCodes.length === 1 ? 'code' : 'codes'} found
                  </span>
                )}
              </div>

              {cptCodes.length > 0 ? (
                <div className="space-y-2 max-h-96 overflow-y-auto">
                  {cptCodes.map((cpt, index) => (
                    <div key={index} className="bg-green-50 rounded-lg p-3 border border-green-200">
                      <div className="flex items-start gap-3">
                        <code className="bg-green-100 px-2 py-1 rounded text-sm font-semibold text-green-900 whitespace-nowrap">
                          {cpt.code}
                        </code>
                        <span className="text-sm text-gray-700 flex-1">{cpt.description}</span>
                      </div>
                    </div>
                  ))}
                </div>
              ) : !isLoading && !error && (
                <div className="text-center py-8 text-gray-500">
                  <p>No CPT codes found for this ICD-10 code.</p>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default CPTTestingPage;
