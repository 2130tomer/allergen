from __future__ import annotations
import json
import sqlite3
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from allergen_pipeline import build_catalog, fetch_rami_levy_allergens as harvest
from allergen_pipeline.cache import CACHE_VERSION, is_fresh, observed_record
from allergen_pipeline.catalog.product import Product, RetailerOffer
from allergen_pipeline.domain.claims import AllergenClaim, Level, Source
from allergen_pipeline.domain.filtering import FilterSelection
from allergen_pipeline.domain.resolution import ResolvedAllergen, ResolvedAllergens, resolve
from allergen_pipeline.enrich import OffCache, collect_from_open_food_facts, load_rami_levy_claims
from allergen_pipeline.ingredients.free_from import FreeFromDetector
from allergen_pipeline.ingredients.mapping import IngredientAllergenMap
from allergen_pipeline.snapshot.build import build
from allergen_pipeline.sources.retailers import rami_levy_online as rami
from allergen_pipeline.sources.retailers.claims import rami_levy_to_claims
from allergen_pipeline import publish_snapshot

BARCODE = '7290000066318'
TODAY = date(2026, 9, 5)

def product(contains=(), may=(), ingredients=None, name='test'):
    return rami.parse_product({'data': [{'barcode': BARCODE, 'name': name, 'gs': {
        rami.CONTAINS_FIELD: list(contains), rami.MAY_CONTAIN_FIELD: list(may),
        'Ingredient_Sequence_and_Name': ingredients,
    }}]}, BARCODE)

@pytest.mark.parametrize('code', [6912, 6998])
def test_gluten_free_oats_through_resolution_snapshot_and_filter(tmp_path, code):
    claims = rami_levy_to_claims(product([code]), IngredientAllergenMap.load(), TODAY)
    resolved = resolve(claims)
    assert resolved.level_of('gluten') is Level.UNKNOWN
    path = tmp_path / 'snapshot.sqlite'
    build(path, [Product(BARCODE, 'test')], {BARCODE: resolved})
    with sqlite3.connect(path) as db:
        rows = db.execute('SELECT allergen_id, level FROM product_allergens').fetchall()
    loaded = ResolvedAllergens({key: ResolvedAllergen(key, Level(level)) for key, level in rows})
    assert FilterSelection(contains_exclusions=frozenset({'gluten'})).apply(loaded).visibility.value == 'unknown'

def test_ingredient_presence_upgrades_may_contain():
    claims = rami_levy_to_claims(product(may=[6821], ingredients='לציטין סויה, מים'), IngredientAllergenMap.load(), TODAY)
    resolved = resolve(claims)
    assert resolved.level_of('soy') is Level.CONTAINS
    assert not FilterSelection(contains_exclusions=frozenset({'soy'})).apply(resolved).is_visible

def test_retailer_copy_cannot_assert_absence():
    claims = rami_levy_to_claims(product(name='ללא חלב'), IngredientAllergenMap.load(), TODAY, FreeFromDetector.load())
    assert all(claim.level is not Level.ABSENT for claim in claims)

@pytest.mark.parametrize('payload', [{}, {'error': 'unavailable'}, {'data': None}, {'data': {}}, {'data': [None]}])
def test_malformed_response_is_not_a_negative_cache_result(payload):
    with pytest.raises(ValueError):
        rami.parse_product(payload, BARCODE)

def test_undated_legacy_claim_stays_undated(tmp_path):
    path = tmp_path / 'rami.json'
    path.write_text(json.dumps({BARCODE: {'contains': ['peanuts']}}))
    claims = load_rami_levy_claims(path, IngredientAllergenMap.load())[BARCODE]
    assert claims[0].observed_on is None
    assert resolve(claims).by_allergen['peanuts'].observed_on is None

def test_negative_cache_expires_and_legacy_cache_needs_refresh():
    assert not is_fresh({})
    assert not is_fresh({'code': BARCODE})
    fresh = observed_record(None)
    assert is_fresh(fresh)
    assert not is_fresh(fresh, date.today() + timedelta(days=1))

def test_negative_refresh_preserves_old_positive_and_its_date():
    previous = {'contains': ['peanuts'], 'observed_on': '2020-01-01'}
    updated = observed_record(None, previous)
    assert updated['contains'] == ['peanuts']
    assert updated['observed_on'] == '2020-01-01'
    assert updated['_stale']

def test_off_legacy_cache_keeps_date_unknown_in_cache_only_mode(tmp_path):
    p = tmp_path / 'off.json'
    p.write_text(json.dumps({BARCODE: {'code': BARCODE, 'allergen_ids': ['peanuts']}}))
    claims, _, _ = collect_from_open_food_facts([BARCODE], OffCache(p), TODAY, IngredientAllergenMap.load(), cache_only=True, verbose=False)
    assert claims[BARCODE][0].observed_on is None

def test_off_old_image_is_refetched(tmp_path, monkeypatch):
    p = tmp_path / 'off.json'
    p.write_text(json.dumps({BARCODE: {'code': BARCODE, 'image_front_url': 'old'}}))
    def fetch(barcodes, cache, *_):
        assert barcodes == [BARCODE]
        cache.remember(BARCODE, {'code': BARCODE, 'image_front_url': 'official'})
    monkeypatch.setattr('allergen_pipeline.enrich._fetch_missing', fetch)
    _, products, _ = collect_from_open_food_facts([BARCODE], OffCache(p), TODAY, IngredientAllergenMap.load(), verbose=False)
    assert products[BARCODE].image_url == 'official'

def test_rami_ingredients_reach_catalog_without_detected_allergens(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(build_catalog, 'collect_shufersal_offers', lambda **_: ([RetailerOffer('shufersal', BARCODE, 'מלח')], 0))
    monkeypatch.setattr(build_catalog, 'check_run', lambda *a, **kw: None)
    cache = tmp_path / 'rami.json'
    cache.write_text(json.dumps({BARCODE: {'ingredients_text': 'מים, מלח'}}))
    out = tmp_path / 'snapshot.sqlite'
    assert build_catalog.main(['--allergens', '--cache-only', '--rami-levy-claims', str(cache), '--output', str(out)]) == 0
    with sqlite3.connect(out) as db:
        assert db.execute('SELECT ingredients_known, has_allergen_data FROM products').fetchone() == (1, 0)

def prepare_harvest(tmp_path, monkeypatch):
    snap = tmp_path / 'catalog.sqlite'
    with sqlite3.connect(snap) as db:
        db.execute('CREATE TABLE products(barcode TEXT, is_active INTEGER, department_id TEXT, has_allergen_data INTEGER)')
        db.executemany("INSERT INTO products VALUES (?,1,'food',0)", [(str(n),) for n in range(6)])
    monkeypatch.setattr(harvest.httpx, 'Client', MagicMock())
    monkeypatch.setattr(harvest.time, 'sleep', lambda _: None)
    return snap, tmp_path / 'cache.json'

def test_limit_applies_after_cache_filtering(tmp_path, monkeypatch):
    snap, cache = prepare_harvest(tmp_path, monkeypatch)
    first = harvest.load_barcodes(snap, 2, True)
    cache.write_text(json.dumps({b: observed_record(None) for b in first}))
    calls = []
    def fetch(client, barcode):
        calls.append(barcode)
        return None
    monkeypatch.setattr(harvest, '_fetch_one', fetch)
    assert harvest.main(['--snapshot', str(snap), '--cache', str(cache), '--limit', '2']) == 0
    assert len(calls) == 2 and not set(calls).intersection(first)

def test_failed_harvest_returns_failure_without_negative_entries(tmp_path, monkeypatch):
    snap, cache = prepare_harvest(tmp_path, monkeypatch)
    def fail(*_): raise RuntimeError('network')
    monkeypatch.setattr(harvest, '_fetch_one', fail)
    assert harvest.main(['--snapshot', str(snap), '--cache', str(cache)]) == 1
    assert json.loads(cache.read_text()) == {}

def test_harvest_persists_observation_date(tmp_path, monkeypatch):
    snap, cache = prepare_harvest(tmp_path, monkeypatch)
    monkeypatch.setattr(harvest, '_fetch_one', lambda *_: product([6807]))
    assert harvest.main(['--snapshot', str(snap), '--cache', str(cache), '--limit', '1']) == 0
    entry = next(iter(json.loads(cache.read_text()).values()))
    assert entry['observed_on'] == date.today().isoformat()
    assert entry['_cache_version'] == CACHE_VERSION

def test_publish_rejects_zero_allergen_data_and_keeps_existing_file(tmp_path, monkeypatch):
    source = tmp_path / 'source.sqlite'; target = tmp_path / 'target.sqlite'
    build(source, [Product(BARCODE, 'test')], {})
    target.write_bytes(b'unchanged')
    monkeypatch.setattr(publish_snapshot, 'MIN_PRODUCTS', 1)
    assert publish_snapshot.main(['--source', str(source), '--target', str(target)]) == 2
    assert target.read_bytes() == b'unchanged'

def test_publish_rejects_corrupt_candidate_even_with_force(tmp_path):
    source = tmp_path / 'broken.sqlite'; target = tmp_path / 'target.sqlite'
    source.write_bytes(b'broken'); target.write_bytes(b'unchanged')
    assert publish_snapshot.main(['--source', str(source), '--target', str(target), '--force']) == 1
    assert target.read_bytes() == b'unchanged'

CASES = json.loads((Path(__file__).parents[2] / 'shared/filter-cases.json').read_text())
@pytest.mark.parametrize('case', CASES, ids=lambda c: c['name'])
def test_shared_filter_contract(case):
    resolved = ResolvedAllergens({key: ResolvedAllergen(key, Level(level)) for key, level in case['levels'].items()})
    selection = FilterSelection(frozenset(case['contains']), frozenset(case['may']))
    assert selection.apply(resolved).visibility.value == case['visibility']

def test_mobile_off_dictionary_matches_pipeline():
    from allergen_pipeline.sources.openfoodfacts import _TAG_TO_ALLERGEN
    path = Path(__file__).parents[2] / 'app/src/domain/offTagMap.json'
    assert json.loads(path.read_text()) == _TAG_TO_ALLERGEN

def test_silent_refresh_preserves_positive_observation():
    updated = observed_record({'contains': [], 'may_contain': []}, {
        'contains': ['peanuts'], 'observed_on': '2020-01-01',
    })
    assert updated['contains'] == ['peanuts']
    assert updated['observed_on'] == '2020-01-01'
    assert updated['_stale']
