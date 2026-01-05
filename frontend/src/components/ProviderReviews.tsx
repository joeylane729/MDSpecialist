import React, { useState } from 'react';
import { MessageSquare, ChevronDown, ChevronUp, Search } from 'lucide-react';
import { HealthgradesReview } from '../services/api';

interface ProviderReviewsProps {
  npi: string | number;
  searchQuery?: string;  // Optional, kept for backward compatibility but not used for filtering
  reviews: HealthgradesReview[];  // Pre-fetched reviews from backend with is_relevant flag
  patientDiagnosis?: string;  // For displaying condition name in header
}

const MAX_REVIEW_LENGTH = 240;  // Characters before truncation

export default function ProviderReviews({ reviews: allReviews, patientDiagnosis }: ProviderReviewsProps) {
  const [expandedReviews, setExpandedReviews] = useState<Set<number>>(new Set());
  const [viewMode, setViewMode] = useState<'relevant' | 'all'>('relevant');

  // Filter reviews by is_relevant boolean (backend already calculated this)
  const relevantReviews = React.useMemo(() => {
    return allReviews.filter(review => review.is_relevant === true);
  }, [allReviews]);
  
  const matchingCount = relevantReviews.length;
  const totalCount = allReviews.length;
  
  // Calculate average rating for relevant reviews
  const avgRelevantRating = React.useMemo(() => {
    const ratingsWithValues = relevantReviews
      .map(review => review.review_rating)
      .filter((rating): rating is number => rating != null && rating !== undefined && typeof rating === 'number');
    
    if (ratingsWithValues.length === 0) return null;
    
    const sum = ratingsWithValues.reduce((acc, rating) => acc + rating, 0);
    return sum / ratingsWithValues.length;
  }, [relevantReviews]);
  
  // Don't automatically switch to 'all' mode - stay in 'relevant' mode and show message
  const effectiveViewMode = viewMode;
  const filteredReviews = effectiveViewMode === 'all' ? allReviews : relevantReviews;

  const toggleReviewExpansion = (reviewId: number) => {
    const newExpanded = new Set(expandedReviews);
    if (newExpanded.has(reviewId)) {
      newExpanded.delete(reviewId);
    } else {
      newExpanded.add(reviewId);
    }
    setExpandedReviews(newExpanded);
  };

  const formatDate = (dateString?: string) => {
    if (!dateString) return '';
    try {
      const date = new Date(dateString);
      return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
    } catch {
      return dateString;
    }
  };

  const truncateText = (text: string, maxLength: number) => {
    if (text.length <= maxLength) return text;
    return text.slice(0, maxLength).trim() + '...';
  };

  if (allReviews.length === 0) {
    return null; // No reviews available
  }

  return (
    <div className="mt-2">
      {/* Clean Header */}
      <div className="flex items-center justify-between mb-3 pb-2 border-b border-gray-200">
        <div className="flex items-center gap-2">
          {matchingCount === 0 && effectiveViewMode === 'relevant' ? (
            <span className="text-sm text-gray-700">
              No reviews relevant to: <span className="font-semibold text-gray-900">{patientDiagnosis || 'your condition'}</span>
            </span>
          ) : matchingCount > 0 && effectiveViewMode === 'relevant' ? (
            <span className="text-sm text-gray-700">
              Showing {matchingCount} review{matchingCount !== 1 ? 's' : ''} relevant to: <span className="font-semibold text-gray-900">{patientDiagnosis || 'your condition'}</span>
              {avgRelevantRating !== null && (
                <>
                  {' · '}
                  <span className="flex items-center gap-1">
                    <span className="text-yellow-500 text-sm">★</span>
                    <span className="font-semibold text-gray-900">{avgRelevantRating.toFixed(1)}</span>
                    <span className="text-gray-500">avg rating</span>
                  </span>
                </>
              )}
            </span>
          ) : (
            <span className="text-sm text-gray-700">
              Showing all {totalCount} review{totalCount !== 1 ? 's' : ''}
            </span>
          )}
        </div>
        {matchingCount === 0 && effectiveViewMode === 'relevant' ? (
          <button
            onClick={() => setViewMode('all')}
            className="text-sm text-blue-600 hover:text-blue-800 font-medium hover:underline flex items-center gap-1"
          >
            View all {totalCount} →
          </button>
        ) : matchingCount > 0 && effectiveViewMode === 'relevant' && matchingCount < totalCount ? (
          <button
            onClick={() => setViewMode('all')}
            className="text-sm text-blue-600 hover:text-blue-800 font-medium hover:underline flex items-center gap-1"
          >
            View all {totalCount} →
          </button>
        ) : matchingCount > 0 && effectiveViewMode === 'all' ? (
          <button
            onClick={() => setViewMode('relevant')}
            className="text-sm text-blue-600 hover:text-blue-800 font-medium hover:underline flex items-center gap-1"
          >
            Relevant only ({matchingCount}) →
          </button>
        ) : null}
      </div>

      {/* Feed-Style Reviews - Contained Scrollable */}
      {matchingCount === 0 && effectiveViewMode === 'relevant' ? (
        <div className="text-center py-6">
          <p className="text-sm text-gray-600 mb-3">
            There are no reviews relevant to <span className="font-semibold text-gray-900">{patientDiagnosis || 'your condition'}</span>.
          </p>
          <button
            onClick={() => setViewMode('all')}
            className="text-sm text-blue-600 hover:text-blue-800 font-medium hover:underline"
          >
            Click to view all {totalCount} review{totalCount !== 1 ? 's' : ''}
          </button>
        </div>
      ) : filteredReviews.length === 0 ? (
        <p className="text-sm text-gray-600 text-center py-4">
          No reviews available
        </p>
      ) : (
        <div className="max-h-96 overflow-y-auto pr-2">
          <div className="space-y-0">
            {filteredReviews.map((review, index) => {
              const isExpanded = expandedReviews.has(review.id);
              const reviewText = review.review_text || '';
              const shouldTruncate = reviewText.length > MAX_REVIEW_LENGTH;
              const displayText = shouldTruncate && !isExpanded 
                ? truncateText(reviewText, MAX_REVIEW_LENGTH) 
                : reviewText;

              return (
                <div
                  key={review.id}
                  className={`py-4 ${index < filteredReviews.length - 1 ? 'border-b border-gray-200' : ''}`}
                >
                  {/* Review Header */}
                  <div className="flex items-start gap-2 mb-2">
                    {review.review_rating != null && review.review_rating !== undefined && (
                      <div className="flex items-center gap-1">
                        <span className="text-yellow-500 text-sm">★</span>
                        <span className="text-sm font-semibold text-gray-900">
                          {review.review_rating}
                        </span>
                      </div>
                    )}
                    {review.review_author && (
                      <>
                        <span className="text-gray-400">—</span>
                        <span className="font-medium text-gray-900 text-sm">
                          {review.review_author}
                        </span>
                      </>
                    )}
                    {review.review_date && (
                      <>
                        <span className="text-gray-400">·</span>
                        <span className="text-sm text-gray-500">
                          {formatDate(review.review_date)}
                        </span>
                      </>
                    )}
                  </div>

                  {/* Review Text */}
                  <p className="text-sm text-gray-700 leading-relaxed whitespace-pre-wrap mb-2">
                    {displayText}
                  </p>

                  {/* Read More/Less Toggle */}
                  {shouldTruncate && (
                    <button
                      onClick={() => toggleReviewExpansion(review.id)}
                      className="text-sm text-blue-600 hover:text-blue-800 font-medium hover:underline"
                    >
                      {isExpanded ? 'Read less' : 'Read more'}
                    </button>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
