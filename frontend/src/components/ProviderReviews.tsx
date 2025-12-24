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
  const [showAll, setShowAll] = useState(false);
  const [expandedReviews, setExpandedReviews] = useState<Set<number>>(new Set());
  const [viewMode, setViewMode] = useState<'relevant' | 'all'>('relevant');

  const PREVIEW_COUNT = 5; // Show 5 reviews by default

  // Filter reviews by is_relevant boolean (backend already calculated this)
  const filteredReviews = React.useMemo(() => {
    if (viewMode === 'all') {
      return allReviews;
    }
    
    // Filter by is_relevant boolean flag (set by backend)
    return allReviews.filter(review => review.is_relevant === true);
  }, [allReviews, viewMode]);

  const displayedReviews = showAll ? filteredReviews : filteredReviews.slice(0, PREVIEW_COUNT);
  const matchingCount = filteredReviews.length;
  const totalCount = allReviews.length;

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

  if (matchingCount === 0 && viewMode === 'relevant') {
    return (
      <div className="mt-2 p-4 bg-amber-50 border border-amber-200 rounded-lg">
        <div className="flex items-start gap-3">
          <Search className="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5" />
          <div className="flex-1">
            <p className="text-sm font-medium text-amber-900 mb-1">
              No Relevant Patient Reviews Found
            </p>
            <p className="text-sm text-amber-700">
              This provider has {totalCount} total {totalCount === 1 ? 'review' : 'reviews'}, but none mention the condition you're searching for.
            </p>
            <button
              onClick={() => setViewMode('all')}
              className="mt-2 text-sm text-amber-600 hover:text-amber-800 font-medium underline"
            >
              View all {totalCount} {totalCount === 1 ? 'review' : 'reviews'}
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="mt-2">
      {/* Clean Header */}
      <div className="flex items-center justify-between mb-3 pb-2 border-b border-gray-200">
        <div className="flex items-center gap-2">
          {viewMode === 'relevant' && matchingCount > 0 && (
            <span className="text-sm text-gray-700">
              Showing {matchingCount} review{matchingCount !== 1 ? 's' : ''} relevant to: <span className="font-semibold text-gray-900">{patientDiagnosis || 'your condition'}</span>
            </span>
          )}
          {viewMode === 'all' && (
            <span className="text-sm text-gray-700">
              Showing all {totalCount} review{totalCount !== 1 ? 's' : ''}
            </span>
          )}
        </div>
        {viewMode === 'relevant' && matchingCount < totalCount && (
          <button
            onClick={() => setViewMode('all')}
            className="text-sm text-blue-600 hover:text-blue-800 font-medium hover:underline flex items-center gap-1"
          >
            View all {totalCount} →
          </button>
        )}
        {viewMode === 'all' && matchingCount < totalCount && (
          <button
            onClick={() => setViewMode('relevant')}
            className="text-sm text-blue-600 hover:text-blue-800 font-medium hover:underline flex items-center gap-1"
          >
            Relevant only ({matchingCount}) →
          </button>
        )}
      </div>

      {/* Feed-Style Reviews */}
      {displayedReviews.length === 0 ? (
        <p className="text-sm text-gray-600 text-center py-4">
          No reviews available
        </p>
      ) : (
        <div className="space-y-0">
          {displayedReviews.map((review, index) => {
            const isExpanded = expandedReviews.has(review.id);
            const reviewText = review.review_text || '';
            const shouldTruncate = reviewText.length > MAX_REVIEW_LENGTH;
            const displayText = shouldTruncate && !isExpanded 
              ? truncateText(reviewText, MAX_REVIEW_LENGTH) 
              : reviewText;

            return (
              <div
                key={review.id}
                className={`py-4 ${index < displayedReviews.length - 1 ? 'border-b border-gray-200' : ''}`}
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
      )}

      {/* Show All Relevant Reviews CTA */}
      {filteredReviews.length > PREVIEW_COUNT && (
        <div className="mt-4 text-center pt-3 border-t border-gray-200">
          <button
            onClick={() => setShowAll(!showAll)}
            className="text-sm text-blue-600 hover:text-blue-800 font-medium flex items-center justify-center gap-1.5 mx-auto hover:underline"
          >
            {showAll ? (
              <>
                <ChevronUp className="w-4 h-4" />
                Show fewer reviews
              </>
            ) : (
              <>
                <ChevronDown className="w-4 h-4" />
                Show all {filteredReviews.length} relevant review{filteredReviews.length !== 1 ? 's' : ''}
              </>
            )}
          </button>
        </div>
      )}
    </div>
  );
}
