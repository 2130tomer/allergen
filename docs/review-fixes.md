# Review fixes

Base: `bc1d52d85560bc662a5cdc1eb3457d9cc5259c7b` from `2130tomer/allergen`.

## Changes

- Correct ingredient presence, group filtering, and gluten-free oats handling.
- Keep unknown observation dates unknown; persist dates when collecting data.
- Include Rami Levy ingredients in the generated catalog even when no allergen
  was found; retain old positive observations when a source goes silent.
- Refresh dated, versioned caches; expire negative lookups; apply collection
  limits after cache filtering and return a failure exit code for failed runs.
- Validate retailer payloads before storing a missing-product result.
- Package retailer JSON dictionaries in wheels.
- Reject unverified retailer free-from claims as absence evidence.
- Validate catalog publication and on-device updates, preserve a backup and
  recover interrupted replacements. Catalog schema is now version 2.
- Offer three exclusion policies per allergen and explain group exclusions.
- Distinguish remote/network/local errors from confirmed missing products.
- Replace inert reporting controls with a GitHub report draft opened in the
  browser. Nothing is submitted automatically. Camera capture and an upload
  moderation service are not implemented or advertised as available.
- Share the OFF tag dictionary with the app, with a test preventing drift.
- Add CI for Python, app tests, type checking, wheel data and a web bundle.

## Validation performed locally

- 308 Python tests passed.
- 68 Jest tests passed.
- TypeScript `tsc --noEmit` passed.
- Expo web export passed.
- Built a wheel, verified both retailer dictionaries, and loaded the code map
  from the extracted wheel outside the source tree.
- No live retailer harvesting, physical-device test, native APK/IPA build,
  PostgreSQL deployment or GitHub workflow run was performed.

## Rebuild before native release

Previously built version 1 catalogs are intentionally not accepted by the
updated native app. Generate and inspect a new catalog from your source caches:

```bash
cd pipeline
python -m allergen_pipeline.build_catalog --allergens --cache-only
python -m allergen_pipeline.publish_snapshot
```

This requires the project's real source caches and current price catalog access.
The checked-in web fixture is only a preview; its old extracted absences are
suppressed. It is not a replacement for a fresh native catalog.

For subsequent Rami Levy collection:

```bash
python -m allergen_pipeline.fetch_rami_levy_allergens --limit 300
python -m allergen_pipeline.fetch_rami_levy_allergens --all --refresh --limit 300 --requests-per-minute 12
```

The first command advances through uncached/expired candidates on each run.
The second explicitly refreshes existing catalog observations. OFF defaults to
12 requests per minute; legacy cached images refresh on the next online
allergen-enrichment run, not on a cache-only build.

If using the optional PostgreSQL schema, reapply `storage/schema.sql` to allow
NULL observation dates on existing claims. No database migration was executed
as part of this source change.

## Apply the patch to a fork

Clone your GitHub fork, create a branch from the base commit above, and run:

```bash
git switch -c fix/review-findings bc1d52d85560bc662a5cdc1eb3457d9cc5259c7b
git apply --index /path/to/allergen-review-fixes.patch
git commit -m "Fix allergen evidence, cache freshness and catalog updates"
git push -u origin fix/review-findings
```

The patch includes these notes and all changed/new source and test files.
