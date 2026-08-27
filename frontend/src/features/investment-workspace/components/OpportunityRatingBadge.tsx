import { opportunityRating } from '../utils/investmentDecision';
import type { OpportunityRating, SuggestedAction } from '../utils/investmentDecision';

type OpportunityRatingBadgeProps = {
  recommendationScore?: number | string | null;
  confidenceScore?: number | string | null;
  action?: SuggestedAction['label'];
  rating?: OpportunityRating;
};

export function OpportunityRatingBadge({ recommendationScore, confidenceScore, action, rating }: OpportunityRatingBadgeProps) {
  const resolvedRating = rating ?? opportunityRating(recommendationScore, confidenceScore, action);
  const stars = `${'★'.repeat(resolvedRating.stars)}${'☆'.repeat(5 - resolvedRating.stars)}`;

  return (
    <div className={`vn-opportunity-rating vn-opportunity-rating--${resolvedRating.tone}`} title="Rating visual baseado nos scores e alinhado à ação sugerida">
      <span className="vn-opportunity-rating__stars" aria-hidden="true">{stars}</span>
      <span className="vn-opportunity-rating__label">{resolvedRating.label}</span>
      <span className="vn-sr-only">{resolvedRating.stars} de 5 estrelas: {resolvedRating.label}</span>
    </div>
  );
}
