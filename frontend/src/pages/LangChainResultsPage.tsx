import React, { useState, useEffect } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { ArrowLeft, Brain, Clock, Users, Target, FileText } from 'lucide-react';
import { 
  SpecialistRecommendationResponse, 
  SpecialistRecommendation,
  getSpecialistRecommendations 
} from '../services/api';

const LangChainResultsPage: React.FC = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const [recommendations, setRecommendations] = useState<SpecialistRecommendationResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // Check if recommendations are already provided in state
    if (location.state?.recommendations) {
      setRecommendations(location.state.recommendations);
      return;
    }

    // Get search parameters from location state
    const searchParams = location.state?.searchParams;
    if (!searchParams) {
      setError('No search parameters found. Please start a new search.');
      return;
    }

    // Call LangChain API
    fetchRecommendations(searchParams);
  }, [location.state]);

  const fetchRecommendations = async (searchParams: any) => {
    setIsLoading(true);
    setError(null);

    try {
      const request = {
        symptoms: searchParams.symptoms || '',
        diagnosis: searchParams.diagnosis || '',
        location_preference: `${searchParams.city}, ${searchParams.state}`,

        medical_history: searchParams.medicalHistory || '',
        medications: searchParams.medications || '',
        surgical_history: searchParams.surgicalHistory || '',

        files: [] // For now, we'll skip file processing
      };

      const response = await getSpecialistRecommendations(request);
      setRecommendations(response);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to get recommendations');
    } finally {
      setIsLoading(false);
    }
  };

  const goBack = () => {
    navigate(-1);
  };

  if (isLoading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <h2 className="text-xl font-semibold text-gray-700">AI is analyzing your case...</h2>
          <p className="text-gray-500 mt-2">This may take a few moments</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center max-w-md mx-auto p-6">
          <div className="text-red-500 text-6xl mb-4">⚠️</div>
          <h2 className="text-xl font-semibold text-gray-700 mb-2">Error</h2>
          <p className="text-gray-600 mb-4">{error}</p>
          <button
            onClick={goBack}
            className="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700"
          >
            Go Back
          </button>
        </div>
      </div>
    );
  }

  if (!recommendations) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <h2 className="text-xl font-semibold text-gray-700">No recommendations found</h2>
          <button
            onClick={goBack}
            className="mt-4 bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700"
          >
            Go Back
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center">
              <button
                onClick={goBack}
                className="flex items-center text-gray-600 hover:text-gray-900 mr-4"
              >
                <ArrowLeft className="w-5 h-5 mr-2" />
                Back
              </button>
              <div className="flex items-center">
                <Brain className="w-8 h-8 text-blue-600 mr-3" />
                <h1 className="text-2xl font-bold text-gray-900">AI Specialist Recommendations</h1>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Summary Stats */}
        <div className="bg-white rounded-lg shadow-sm p-6 mb-8">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Analysis Summary</h2>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="text-center">
              <div className="text-2xl font-bold text-blue-600">{recommendations.recommendations.length}</div>
              <div className="text-sm text-gray-600">Recommendations</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-green-600">{recommendations.total_candidates_found}</div>
              <div className="text-sm text-gray-600">Candidates Analyzed</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-purple-600">{recommendations.processing_time_ms}ms</div>
              <div className="text-sm text-gray-600">Processing Time</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-orange-600">{recommendations.retrieval_strategies_used.length}</div>
              <div className="text-sm text-gray-600">Search Strategies</div>
            </div>
          </div>
        </div>

        {/* Patient Profile */}
        <div className="bg-white rounded-lg shadow-sm p-6 mb-8">
          <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
            <Users className="w-5 h-5 mr-2 text-blue-600" />
            Patient Profile
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <h3 className="font-medium text-gray-700 mb-2">Symptoms</h3>
              <div className="flex flex-wrap gap-2">
                {recommendations.patient_profile.symptoms.map((symptom, index) => (
                  <span key={index} className="bg-blue-100 text-blue-800 px-2 py-1 rounded text-sm">
                    {symptom}
                  </span>
                ))}
              </div>
            </div>
            <div>
              <h3 className="font-medium text-gray-700 mb-2">Specialties Needed</h3>
              <div className="flex flex-wrap gap-2">
                {recommendations.patient_profile.specialties_needed.map((specialty, index) => (
                  <span key={index} className="bg-green-100 text-green-800 px-2 py-1 rounded text-sm">
                    {specialty}
                  </span>
                ))}
              </div>
            </div>
            <div>

            </div>
            {recommendations.patient_profile.location_preference && (
              <div>
                <h3 className="font-medium text-gray-700 mb-2">Location Preference</h3>
                <span className="text-gray-600">{recommendations.patient_profile.location_preference}</span>
              </div>
            )}
          </div>
        </div>

        {/* Recommendations */}
        <div className="space-y-6">
          <h2 className="text-lg font-semibold text-gray-900 flex items-center">
            <Target className="w-5 h-5 mr-2 text-blue-600" />
            Specialist Recommendations
          </h2>
          
          {recommendations.recommendations.map((rec, index) => (
            <div key={index} className="bg-white rounded-lg shadow-sm p-6">
              <div className="flex items-start justify-between mb-4">
                <div>
                  <h3 className="text-xl font-semibold text-gray-900">{rec.name}</h3>
                  <p className="text-gray-600">{rec.specialty}</p>
                </div>
                <div className="text-right">
                  <div className="text-2xl font-bold text-blue-600">
                    {(rec.confidence_score * 100).toFixed(0)}%
                  </div>
                  <div className="text-sm text-gray-600">Confidence</div>
                </div>
              </div>
              
              <div className="mb-4">
                <h4 className="font-medium text-gray-700 mb-2 flex items-center">
                  <FileText className="w-4 h-4 mr-2" />
                  AI Reasoning
                </h4>
                <p className="text-gray-600 bg-gray-50 p-3 rounded-lg">
                  {rec.reasoning}
                </p>
              </div>
              
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <h4 className="font-medium text-gray-700 mb-2">Relevance Score</h4>
                  <div className="w-full bg-gray-200 rounded-full h-2">
                    <div 
                      className="bg-blue-600 h-2 rounded-full" 
                      style={{ width: `${rec.relevance_score * 100}%` }}
                    ></div>
                  </div>
                  <span className="text-sm text-gray-600">{(rec.relevance_score * 100).toFixed(1)}%</span>
                </div>
                <div>
                  <h4 className="font-medium text-gray-700 mb-2">Specialist ID</h4>
                  <code className="bg-gray-100 px-2 py-1 rounded text-sm">{rec.specialist_id}</code>
                </div>
              </div>
              
              {/* Metadata */}
              {rec.metadata && (
                <div className="mt-4">
                  <h4 className="font-medium text-gray-700 mb-2">Source Information</h4>
                  <div className="bg-gray-50 p-3 rounded-lg">
                    <pre className="text-xs text-gray-600 overflow-x-auto">
                      {JSON.stringify(rec.metadata, null, 2)}
                    </pre>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>

        {/* Footer */}
        <div className="mt-8 text-center text-gray-500 text-sm">
          <p>Generated on {new Date(recommendations.timestamp).toLocaleString()}</p>
          <p>Using {recommendations.retrieval_strategies_used.join(', ')}</p>
        </div>
      </div>
    </div>
  );
};

export default LangChainResultsPage;
