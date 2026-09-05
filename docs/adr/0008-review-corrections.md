# ADR-0008: Preserve evidence, freshness and catalog availability

Status: accepted in the review-fixes branch.

This decision supersedes conflicting behavior described in ADR-0007 and the
older independent-filter documentation.

- Text scraped from a retailer name or ingredients field is not verified
  packaging evidence. It cannot emit an ABSENT claim, even if a free-from
  phrase is detected. Reduced-content claims remain attributed to the retailer.
- An allergen explicitly found in ingredients produces CONTAINS even when a
  structured field says MAY_CONTAIN. The resolution layer chooses the stricter
  claim among claims of equal standing.
- An absent subtype does not establish absence of its entire group. Oats are
  independently selectable and do not automatically propagate to gluten.
- Selecting exclusion of MAY_CONTAIN also excludes CONTAINS. Existing stored
  may-only selections use this behavior immediately. The UI offers one policy
  per allergen and explains inherited group selections.
- Collection dates belong to source observations. Undated legacy observations
  remain undated. Rebuilding or reading a cache cannot advance their dates.
- OFF and Rami Levy caches are versioned. Positive entries expire after 14 days,
  negative entries after one day; old cache formats trigger a network refresh.
  Network failures preserve previous records. A missing or silent response
  preserves old positive evidence with its old date and flags it for review.
  Cache-only builds never require a refresh.
- New catalogs use schema version 2 to prevent older extracted absence claims
  from being used as verified evidence. Existing catalogs must be rebuilt.
- Catalog publication validates integrity, schema and counts. It rejects zero
  allergen coverage and drops above 20% in product count or products with data,
  unless explicitly forced. Force never bypasses integrity/schema validation.
- On-device updates validate a staging database before replacing the active
  file. A backup supports rollback on failure and recovery after interruption.

Automated checks exercise both source-to-SQLite integration and a shared
Python/TypeScript filter contract. Device filesystem tests use mocks; physical
Android/iOS interruption testing is still required before a release.
