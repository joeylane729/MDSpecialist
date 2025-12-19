import React, { useState, useEffect } from 'react';
import { MessageSquare, ChevronDown, ChevronUp, Star } from 'lucide-react';
import { HealthgradesReview, getReviewsByNPI, getReviewCount } from '../services/api';

interface ProviderReviewsProps {
  npi: string | number;
}

export default function ProviderReviews({ npi }: ProviderReviewsProps) {
  const [reviews, setReviews] = useState<HealthgradesReview[]>([]);
  const [totalCount, setTotalCount] = useState<number>(0);
  const [initialLoading, setInitialLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [showAll, setShowAll] = useState(false);
  const [expanded, setExpanded] = useState(false);

  const PREVIEW_COUNT = 2; // Show 2 reviews by default

  useEffect(() => {
    const fetchReviewData = async () => {
      console.log(`🔍 [ProviderReviews] Fetching reviews for NPI: ${npi} (type: ${typeof npi})`);
      
      // Only show full loading on initial load
      if (reviews.length === 0) {
        setInitialLoading(true);
      } else {
        setLoadingMore(true);
      }
      
      try {
        const [reviewsData, count] = await Promise.all([
          getReviewsByNPI(npi, showAll ? 100 : PREVIEW_COUNT),
          getReviewCount(npi)
        ]);
        console.log(`✅ [ProviderReviews] Received ${reviewsData.length} reviews, count: ${count} for NPI: ${npi}`);
        setReviews(reviewsData);
        setTotalCount(count);
      } catch (error) {
        console.error('❌ [ProviderReviews] Error loading reviews:', error);
      } finally {
        setInitialLoading(false);
        setLoadingMore(false);
      }
    };

    fetchReviewData();
  }, [npi, showAll]);

  if (initialLoading) {
    return (
      <div className="mt-4 p-4 bg-gray-50 rounded-lg">
        <div className="flex items-center gap-2 text-gray-600">
          <MessageSquare className="w-5 h-5" />
          <span>Loading reviews...</span>
        </div>
      </div>
    );
  }

  if (totalCount === 0) {
    return null; // Don't show section if no reviews
  }

  const displayedReviews = showAll ? reviews : reviews.slice(0, PREVIEW_COUNT);

  return (
    <div className="mt-4 border-t pt-4">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between text-left hover:bg-gray-50 p-2 rounded transition-colors"
      >
        <div className="flex items-center gap-2">
          <MessageSquare className="w-5 h-5 text-blue-600" />
          <h3 className="font-semibold text-gray-900">
            Patient Reviews ({totalCount})
          </h3>
        </div>
        {expanded ? (
          <ChevronUp className="w-5 h-5 text-gray-400" />
        ) : (
          <ChevronDown className="w-5 h-5 text-gray-400" />
        )}
      </button>

      {expanded && (
        <div className="mt-3 space-y-3">
          {loadingMore ? (
            <div className="flex items-center justify-center gap-2 text-gray-600 py-4">
              <MessageSquare className="w-5 h-5 animate-pulse" />
              <span>Loading all reviews...</span>
            </div>
          ) : (
            <>
              {displayedReviews.map((review, index) => (
                <div
                  key={review.id}
                  className="bg-gray-50 rounded-lg p-4 border border-gray-200"
                >
                  <div className="flex items-start justify-between mb-2">
                    <div className="flex-1">
                      {review.review_author && (
                        <p className="text-sm font-medium text-gray-700">
                          {review.review_author}
                        </p>
                      )}
                      {review.review_date && (
                        <p className="text-xs text-gray-500">{review.review_date}</p>
                      )}
                    </div>
                  </div>
                  
                  <p className="text-sm text-gray-700 leading-relaxed line-clamp-4">
                    {review.review_text}
                  </p>
                </div>
              ))}

              {totalCount > PREVIEW_COUNT && (
                <button
                  onClick={() => setShowAll(!showAll)}
                  disabled={loadingMore}
                  className="w-full py-2 px-4 text-sm text-blue-600 hover:text-blue-700 hover:bg-blue-50 rounded-lg transition-colors font-medium disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {showAll
                    ? `Show Less`
                    : `Show All ${totalCount} Reviews`}
                </button>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}

