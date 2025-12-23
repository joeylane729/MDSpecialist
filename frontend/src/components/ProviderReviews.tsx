import React, { useState } from 'react';
import { MessageSquare, ChevronDown, ChevronUp, Search } from 'lucide-react';
import { HealthgradesReview } from '../services/api';

interface ProviderReviewsProps {
  npi: string | number;
  searchQuery?: string;  // Optional, kept for backward compatibility but not used for filtering
  reviews: HealthgradesReview[];  // Pre-fetched reviews from backend with is_relevant flag
}

export default function ProviderReviews({ reviews: allReviews }: ProviderReviewsProps) {
  const [showAll, setShowAll] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const [viewMode, setViewMode] = useState<'relevant' | 'all'>('relevant');

  const PREVIEW_COUNT = 2; // Show 2 reviews by default

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

  if (allReviews.length === 0) {
    return null; // No reviews available
  }

  if (matchingCount === 0 && viewMode === 'relevant') {
    return (
      <div className="mt-4 p-4 bg-amber-50 border border-amber-200 rounded-lg">
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

  const headerText = viewMode === 'relevant' && matchingCount > 0
    ? `Relevant Patient Reviews (${matchingCount} of ${totalCount})`
    : `Patient Reviews (${totalCount})`;

  return (
    <div className="mt-2">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between p-2 bg-blue-50 hover:bg-blue-100 rounded transition-colors"
      >
        <div className="flex items-center gap-1.5">
          <MessageSquare className="w-4 h-4 text-blue-600" />
          <span className="text-xs font-medium text-blue-900">{headerText}</span>
        </div>
        {expanded ? (
          <ChevronUp className="w-4 h-4 text-blue-600" />
        ) : (
          <ChevronDown className="w-4 h-4 text-blue-600" />
        )}
      </button>

      {expanded && (
        <div className="mt-2 p-2.5 bg-gray-50 rounded space-y-2">
          {viewMode === 'relevant' && matchingCount < totalCount && (
            <div className="flex items-center justify-between p-1.5 bg-blue-50 rounded border border-blue-100">
              <span className="text-xs text-blue-800">
                Showing relevant reviews
              </span>
              <button
                onClick={() => setViewMode('all')}
                className="text-xs text-blue-600 hover:text-blue-800 font-medium underline"
              >
                View all {totalCount}
              </button>
            </div>
          )}

          {viewMode === 'all' && matchingCount < totalCount && (
            <div className="flex items-center justify-between p-1.5 bg-gray-100 rounded border border-gray-200">
              <span className="text-xs text-gray-700">
                Showing all reviews
              </span>
              <button
                onClick={() => setViewMode('relevant')}
                className="text-xs text-blue-600 hover:text-blue-800 font-medium underline"
              >
                Relevant only ({matchingCount})
              </button>
            </div>
          )}

          {displayedReviews.length === 0 ? (
            <p className="text-xs text-gray-600 text-center py-2">
              No reviews available
            </p>
          ) : (
            <>
              {displayedReviews.map((review) => (
            <div
              key={review.id}
                  className="p-2 bg-white rounded border border-gray-200"
            >
                  <div className="flex items-start justify-between mb-1">
                    <div className="flex items-center gap-1.5 flex-wrap">
                      {review.review_rating != null && review.review_rating !== undefined && (
                        <div className="flex items-center gap-0.5">
                          <span className="text-xs font-medium text-yellow-600">★</span>
                          <span className="text-xs font-medium text-gray-900">
                            {review.review_rating}
                          </span>
                        </div>
                      )}
                  {review.review_author && (
                        <span className="font-medium text-gray-900 text-xs">
                      {review.review_author}
                        </span>
                  )}
                  {review.review_date && (
                        <span className="text-xs text-gray-500">
                          • {review.review_date}
                        </span>
                  )}
                </div>
              </div>
                  <p className="text-xs text-gray-700 leading-relaxed whitespace-pre-wrap line-clamp-3">
                {review.review_text}
              </p>
            </div>
          ))}

              {filteredReviews.length > PREVIEW_COUNT && (
            <button
              onClick={() => setShowAll(!showAll)}
                  className="w-full mt-1.5 py-1.5 text-xs text-blue-600 hover:text-blue-800 font-medium flex items-center justify-center gap-1"
            >
                  {showAll ? (
                    <>
                      <ChevronUp className="w-3.5 h-3.5" />
                      Show fewer
                    </>
                  ) : (
                    <>
                      <ChevronDown className="w-3.5 h-3.5" />
                      Show all {filteredReviews.length}
                    </>
                  )}
            </button>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}
