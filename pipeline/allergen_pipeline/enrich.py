"""שלב 3: העשרת הקטלוג בקביעות אלרגן.

מקבץ את כל המקורות למקום אחד ומחזיר קביעות לכל ברקוד. ההכרעה ביניהן
אינה נעשית כאן אלא ב-domain.resolution, וזה מכוון: המודול הזה אוסף
עדויות, ולא מחליט.

שני מקורות פעילים בגרסה 1:

* Open Food Facts, שהוא היחיד ששומר את ההבחנה בין מכיל לעלול להכיל
  בשני שדות נפרדים, ולכן קביעותיו מפורשות ולא נגזרות.
* מיפוי רשימת הרכיבים, שמגלה אלרגנים שההצהרה החמיצה. הוא רץ על טקסט
  הרכיבים מ-Open Food Facts, ולכן מסומן כאותו מקור ולא כיצרן.
"""

from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import httpx

from .cache import is_fresh, observation_date, observed_record, write_json
from .domain.claims import AllergenClaim, Level, Source
from .ingredients.mapping import IngredientAllergenMap
from .sources import openfoodfacts as off

"""מגבלת הקצב של Open Food Facts, ומה שלמדנו עליה בדרך הקשה.

המאגר מתוחזק בהתנדבות ומגביל קריאות. ריצה ראשונה עם שמונה חוטים בלי
ויסות ייצרה כ-35 בקשות בשנייה, ו-83 אחוז מהבקשות נכשלו; המספרים שהיא
החזירה היו חסרי משמעות. ניסיון שני בתשעים לדקה עדיין קיבל 429, כנראה
בגלל חלון עונשין שנפתח בעקבות הראשון.

הקצב כאן מכוון לשלושים לדקה. המשמעות היא שהעשרה מלאה של קטלוג בגודל
אמיתי אורכת שעות, ולכן היא עבודת רקע מתוזמנת ולא פעולה אינטראקטיבית.
המטמון על הדיסק הוא מה שהופך את זה לנסבל: כל ריצה ממשיכה מאיפה
שהקודמת עצרה.

ההעשרה אף פעם אינה תנאי לבניית הקטלוג. מוצר בלי מידע נכנס לאפליקציה
עם "אין מידע", וזה מצב תקין. ראו ADR-0001.
"""
REQUESTS_PER_MINUTE = 12
WORKERS = 2
MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = 10.0
REQUEST_TIMEOUT = 60.0

# מעל שיעור הכשלים הזה ההעשרה נעצרת מעצמה. אין טעם להמשיך להטריד שרת
# שכבר אמר לנו לא, והמספרים שיתקבלו יהיו ממילא חסרי משמעות.
ABORT_ABOVE_FAILURE_RATE = 0.5
MIN_ATTEMPTS_BEFORE_ABORT = 100


class RateLimiter:
    """ויסות פשוט שמבטיח מרווח מינימלי בין בקשות, גם בין חוטים."""

    def __init__(self, per_minute: int) -> None:
        self._min_interval = 60.0 / max(per_minute, 1)
        self._lock = Lock()
        self._next_allowed = 0.0

    def acquire(self) -> None:
        with self._lock:
            now = time.monotonic()
            wait = self._next_allowed - now
            if wait <= 0:
                self._next_allowed = now + self._min_interval
                wait = 0.0
            else:
                self._next_allowed += self._min_interval
        if wait > 0:
            time.sleep(wait)


@dataclass
class EnrichmentStats:
    requested: int = 0
    found: int = 0
    with_allergens: int = 0
    hidden_allergens_found: int = 0
    unmapped_tags: dict[str, int] = field(default_factory=dict)
    failures: int = 0

    @property
    def hit_rate(self) -> float:
        return self.found / self.requested if self.requested else 0.0

    @property
    def allergen_rate(self) -> float:
        return self.with_allergens / self.requested if self.requested else 0.0


class OffCache:
    """מטמון תשובות על הדיסק, כדי שריצה חוזרת לא תכה שוב במאגר."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._entries: dict[str, dict] = {}
        if path.exists():
            try:
                self._entries = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                self._entries = {}

    def known(self, barcode: str) -> bool:
        return is_fresh(self._entries.get(barcode))

    def get(self, barcode: str) -> dict | None:
        entry = self._entries.get(barcode)
        return entry if entry and not entry.get("_not_found") else None

    def remember(self, barcode: str, payload: dict | None) -> None:
        # מוצר שלא נמצא נשמר כאובייקט ריק, כדי שלא נחזור לשאול עליו.
        self._entries[barcode] = observed_record(payload, self.get(barcode))

    def save(self) -> None:
        write_json(self.path, self._entries)

    def __len__(self) -> int:
        return len(self._entries)


def _as_payload(product: off.OffProduct) -> dict:
    return {
        "code": product.barcode,
        "product_name": product.name,
        "brands": product.brands,
        "ingredients_text": product.ingredients_text,
        "image_front_url": product.image_url,
        "allergen_ids": list(product.allergen_ids),
        "trace_ids": list(product.trace_ids),
        "unmapped_tags": list(product.unmapped_tags),
    }


def _from_payload(payload: dict) -> off.OffProduct | None:
    if not payload:
        return None
    return off.OffProduct(
        barcode=payload["code"],
        name=payload.get("product_name"),
        brands=payload.get("brands"),
        ingredients_text=payload.get("ingredients_text"),
        image_url=payload.get("image_front_url"),
        allergen_ids=tuple(payload.get("allergen_ids") or ()),
        trace_ids=tuple(payload.get("trace_ids") or ()),
        unmapped_tags=tuple(payload.get("unmapped_tags") or ()),
    )


def collect_from_open_food_facts(
    barcodes: list[str],
    cache: OffCache,
    observed_on: date | None,
    ingredient_map: IngredientAllergenMap,
    progress_every: int = 20,
    verbose: bool = True,
    cache_only: bool = False,
) -> tuple[dict[str, list[AllergenClaim]], dict[str, off.OffProduct], EnrichmentStats]:
    """אוסף קביעות לכל הברקודים, בקבוצות, עם מטמון."""
    stats = EnrichmentStats(requested=len(barcodes))
    claims_by_barcode: dict[str, list[AllergenClaim]] = {}
    products_by_barcode: dict[str, off.OffProduct] = {}

    missing = [barcode for barcode in barcodes if not cache.known(barcode)]

    if cache_only:
        if verbose:
            print(
                f"  {len(barcodes) - len(missing)} מהמטמון, "
                f"{len(missing)} ללא מידע (מצב מטמון בלבד, אין פנייה לרשת)"
            )
    else:
        if missing and verbose:
            print(f"  {len(barcodes) - len(missing)} מהמטמון, {len(missing)} לשאילתה")
        if missing:
            _fetch_missing(missing, cache, stats, progress_every, verbose)
        cache.save()

    for barcode in barcodes:
        product = _from_payload(cache.get(barcode) or {})
        if product is None:
            continue
        stats.found += 1
        products_by_barcode[barcode] = product

        for tag in product.unmapped_tags:
            stats.unmapped_tags[tag] = stats.unmapped_tags.get(tag, 0) + 1

        source_date = observation_date((cache.get(barcode) or {}).get("observed_on"))
        claims = off.to_claims(product, source_date)
        hidden = _hidden_from_ingredients(product, claims, ingredient_map, source_date)
        if hidden:
            stats.hidden_allergens_found += len(hidden)
        claims.extend(hidden)

        if claims:
            stats.with_allergens += 1
            claims_by_barcode[barcode] = claims

    return claims_by_barcode, products_by_barcode, stats


def _fetch_missing(
    barcodes: list[str],
    cache: OffCache,
    stats: EnrichmentStats,
    progress_every: int,
    verbose: bool,
) -> None:
    """מושך את מה שאינו במטמון, במקביל ועם ניסיונות חוזרים.

    הקצב מווסת לשלושים בקשות לדקה. שני חוטים מספיקים בהחלט בקצב הזה,
    והם קיימים רק כדי שהמתנה לתשובה אחת לא תעצור את התור.
    """
    completed = 0
    limiter = RateLimiter(REQUESTS_PER_MINUTE)
    started = time.monotonic()

    with httpx.Client(
        headers={"User-Agent": off.USER_AGENT},
        timeout=REQUEST_TIMEOUT,
        follow_redirects=True,
        limits=httpx.Limits(max_connections=WORKERS, max_keepalive_connections=WORKERS),
    ) as client:
        with ThreadPoolExecutor(max_workers=WORKERS) as pool:
            futures = {
                pool.submit(_fetch_with_retry, client, barcode, limiter): barcode
                for barcode in barcodes
            }
            for future in as_completed(futures):
                barcode = futures[future]
                completed += 1
                try:
                    product = future.result()
                except Exception:  # noqa: BLE001 - נספר ולא נשמר כאילו אין אלרגנים
                    stats.failures += 1
                    if _should_abort(completed, stats.failures):
                        for pending in futures:
                            pending.cancel()
                        break
                    continue
                cache.remember(barcode, _as_payload(product) if product else None)

                # שמירת ביניים, כדי שהפסקה באמצע לא תאבד שעה של עבודה.
                if completed % 100 == 0:
                    cache.save()
                    if verbose:
                        elapsed = (time.monotonic() - started) / 60
                        rate = completed / elapsed if elapsed else 0
                        print(
                            f"  {completed}/{len(barcodes)} "
                            f"({rate:.0f} לדקה, {stats.failures} כשלים)",
                            flush=True,
                        )

                if _should_abort(completed, stats.failures):
                    print(
                        f"  שיעור כשלים {stats.failures}/{completed}. "
                        "המקור חוסם אותנו; עוצר ושומר את מה שהתקבל.",
                        flush=True,
                    )
                    for pending in futures:
                        pending.cancel()
                    break


def _should_abort(completed: int, failures: int) -> bool:
    """עצירה עצמית כשברור שהמקור חוסם.

    בלי זה ריצה ממשיכה שעות, מייצרת אלפי בקשות דחויות, ומחזירה מספרי
    כיסוי שנראים כמו נתונים ואינם.
    """
    if completed < MIN_ATTEMPTS_BEFORE_ABORT:
        return False
    return failures / completed > ABORT_ABOVE_FAILURE_RATE


def _fetch_with_retry(
    client: httpx.Client, barcode: str, limiter: RateLimiter
) -> off.OffProduct | None:
    """ניסיונות חוזרים עם השהיה גדלה, תחת ויסות קצב.

    כישלון סופי מורם החוצה ונספר. הוא לעולם אינו נרשם במטמון כמוצר
    ללא אלרגנים, כי זו בדיוק הטעות המסוכנת. ראו ADR-0002.
    """
    last_error: Exception | None = None
    for attempt in range(MAX_RETRIES):
        limiter.acquire()
        try:
            return off.fetch_one(client, barcode)
        except Exception as error:  # noqa: BLE001
            last_error = error
            time.sleep(RETRY_BACKOFF_SECONDS * (attempt + 1))
    raise last_error if last_error else RuntimeError(barcode)


def _site_group(page_url: str | None):
    """הקבוצה התאגידית שהאתר הזה שייך לה, או None כשאינו במרשם."""
    from urllib.parse import urlsplit

    from .catalog import manufacturers

    if not page_url:
        return None
    host = urlsplit(page_url).netloc.lower().removeprefix("www.")
    if not host:
        return None
    for group in manufacturers.GROUPS:
        if not group.website:
            continue
        known = urlsplit(group.website).netloc.lower().removeprefix("www.")
        if known and known == host:
            return group
    return None


def _declaration_is_by_the_products_manufacturer(
    page_url: str | None, catalog_manufacturer: str | None
) -> bool:
    """האם ההצהרה הגיעה מאתר היצרן של המוצר הזה.

    שתי הזהויות נבדקות ולא אחת. לא די בכך שהטקסט הגיע מאתר יצרן כלשהו:
    דף של אסם אינו מעיד על מוצר של תנובה, וזה בדיוק מה שקורה כשברקוד
    ממוחזר או משויך בטעות. היעדר זיהוי משני הצדדים נחשב כישלון, כי
    היעדר ידיעה אינו ראיה.
    """
    from .catalog import manufacturers

    site = _site_group(page_url)
    if site is None:
        return False
    owner = manufacturers.group_of(catalog_manufacturer)
    return owner is not None and owner.id == site.id


def load_manufacturer_claims(
    path: Path,
    manufacturer_by_barcode: dict[str, str | None] | None = None,
) -> dict[str, list[AllergenClaim]]:
    """קורא קביעות יצרן שנשמרו על ידי fetch_manufacturers.

    הקביעות נטענות מקובץ ולא נמשכות ברשת בכל בנייה, כי אתרי היצרנים
    איטיים ואין סיבה להטריד אותם בכל ריצה.

    כאן גם המקום היחיד שבו נולדת קביעת היעדר, כלומר הסימון הירוק.
    ADR-0008 חוסם טקסט קמעונאי כראיית אריזה, ובצדק: שם מוצר בקובץ
    שקיפות הוא מחרוזת קופה קטועה. דף היצרן הוא הצהרת היצרן עצמו על
    המוצר שלו, וזו הראיה היחידה ש-ADR-0007 מתיר לצבוע בה ירוק.

    התנאי מחמיר בכוונה ודורש את שתי הזהויות: שהדף שייך ליצרן שבמרשם,
    ושהיצרן שרשום על המוצר בקטלוג הוא אותו יצרן. בלי הקטלוג אין את מי
    לאמת, ואז אין ירוק כלל.
    """
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}

    from .ingredients.free_from import FreeFromDetector

    detector = FreeFromDetector.load()
    known = manufacturer_by_barcode or {}

    claims_by_barcode: dict[str, list[AllergenClaim]] = {}
    for barcode, record in raw.items():
        observed_on = date.fromisoformat(record["observed_on"])
        page_url = record.get("page_url")
        claims = [
            AllergenClaim(
                allergen_id=entry["allergen_id"],
                level=Level(entry["level"]),
                source=Source.MANUFACTURER,
                observed_on=observed_on,
                source_ref=page_url,
                level_inferred=bool(entry.get("level_inferred")),
            )
            for entry in record.get("claims", [])
        ]

        declared, reduced = detector.detect(
            record.get("name"), record.get("ingredients_text")
        )
        # הפחתה היא נוכחות, ולכן היא נרשמת בלי קשר לאימות הזהות.
        claims.extend(
            AllergenClaim(
                allergen_id=claim.allergen_id,
                level=Level.CONTAINS,
                source=Source.MANUFACTURER,
                observed_on=observed_on,
                source_ref=page_url,
            )
            for claim in reduced
        )
        if declared and _declaration_is_by_the_products_manufacturer(
            page_url, known.get(barcode)
        ):
            reduced_ids = {claim.allergen_id for claim in reduced}
            claims.extend(
                AllergenClaim(
                    allergen_id=claim.allergen_id,
                    level=Level.ABSENT,
                    source=Source.DECLARED_FREE_FROM,
                    observed_on=observed_on,
                    source_ref=page_url,
                )
                for claim in declared
                if claim.allergen_id not in reduced_ids
            )

        claims_by_barcode[barcode] = claims
    return claims_by_barcode


def load_retailer_claims(
    path: Path, ingredient_map: IngredientAllergenMap
) -> dict[str, list[AllergenClaim]]:
    """קורא קביעות קמעונאי שנשמרו על ידי fetch_retailer_allergens.

    זהו מקור האלרגנים העיקרי של גרסה 1. הוא מפריד במפורש בין מכיל
    לעלול להכיל, ולכן הקביעות שלו מפורשות ולא נגזרות. ראו ADR-0006.
    """
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}

    from .ingredients.free_from import FreeFromDetector
    from .sources.retailers import claims as retailer_claims
    from .sources.retailers.shufersal_online import ShufersalProduct

    free_from = FreeFromDetector.load()

    by_barcode: dict[str, list[AllergenClaim]] = {}
    for barcode, record in raw.items():
        if not record or record.get("_not_found"):
            continue
        product = ShufersalProduct(
            barcode=record.get("barcode", barcode),
            page_url=record.get("page_url", ""),
            name=record.get("name"),
            brand=record.get("brand"),
            is_food=bool(record.get("is_food", True)),
            ingredients_text=record.get("ingredients_text"),
            contains_terms=tuple(record.get("contains_terms") or ()),
            may_contain_terms=tuple(record.get("may_contain_terms") or ()),
        )
        observed_on = observation_date(record.get("observed_on"))
        found = retailer_claims.to_claims(
            product, ingredient_map, observed_on, free_from=free_from
        )
        if found:
            by_barcode[barcode] = found
    return by_barcode


def load_rami_levy_claims(
    path: Path, ingredient_map: IngredientAllergenMap
) -> dict[str, list[AllergenClaim]]:
    """קורא קביעות שנשמרו על ידי fetch_rami_levy_allergens.

    הקמעונאי השני. הקביעות כאן כבר מפוענחות מקודים לרשימה הסגורה בזמן
    הקצירה, ולכן אין כאן מיפוי מונחים; הרמה הגיעה מהשדה שבו הקוד הופיע
    ולכן היא מפורשת ולא נגזרת, בדיוק כמו אצל שופרסל. ראו ADR-0006.
    """
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}

    from .ingredients.free_from import FreeFromDetector
    from .sources.retailers import claims as retailer_claims
    from .sources.retailers.rami_levy_online import PRODUCT_URL, RamiLevyProduct

    free_from = FreeFromDetector.load()

    by_barcode: dict[str, list[AllergenClaim]] = {}
    for barcode, record in raw.items():
        if not record or record.get("_not_found"):
            continue
        product = RamiLevyProduct(
            barcode=record.get("barcode", barcode),
            name=record.get("name"),
            brand=record.get("brand"),
            ingredients_text=record.get("ingredients_text"),
            contains_ids=tuple(record.get("contains") or ()),
            may_contain_ids=tuple(record.get("may_contain") or ()),
            page_url=record.get("page_url") or PRODUCT_URL.format(barcode=barcode),
            unknown_codes=tuple(record.get("unknown_codes") or ()),
        )
        observed_on = observation_date(record.get("observed_on"))
        found = retailer_claims.rami_levy_to_claims(
            product, ingredient_map, observed_on, free_from=free_from
        )
        if found:
            by_barcode[barcode] = found
    return by_barcode


def free_from_claims_from_names(
    names_by_barcode: dict[str, str | None],
    observed_on: date,
) -> dict[str, list[AllergenClaim]]:
    """הצהרות הפחתה שמופיעות בשם המוצר. היעדר אינו נגזר מכאן.

    הגרסה הראשונה של הפונקציה הזו ייצרה גם קביעות היעדר, בנימוק ששם
    המוצר בקובץ השקיפות הוא השם שהיצרן מפרסם. הנימוק לא החזיק: השמות
    האלה הם מחרוזות קופה, קטועות ומקוצרות, כמו "עוג.ללא גלוטן שוקו150ג"
    ו"סולת תמי ללא גלוטן 3". סימון ירוק אומר למשתמש שהיצרן הצהיר על
    האריזה, ומחרוזת קופה אינה האריזה.

    ADR-0008 מכריע זאת במפורש: טקסט שנגרד משם קמעונאי או משדה רכיבים
    אינו ראיית אריזה מאומתת ואינו יכול לייצר ABSENT. הצהרת הפחתה נשארת,
    כי היא הכיוון המחמיר: מוצר "דל לקטוז" מכיל לקטוז.

    הנראות של מוצרי המדף הייעודי לאלרגיים נפתרת בסיווג ולא כאן. מוצר
    ששמו אומר "ללא גלוטן" מגיע למחלקת "ללא גלוטן וטבעוני" וניתן לעיון,
    בלי שנסמן אותו כבטוח.
    """
    from .ingredients.free_from import FreeFromDetector

    detector = FreeFromDetector.load()
    claims: dict[str, list[AllergenClaim]] = {}

    for barcode, name in names_by_barcode.items():
        if not name:
            continue
        _, reduced = detector.detect(name)
        found = [
            AllergenClaim(
                allergen_id=claim.allergen_id,
                level=Level.CONTAINS,
                source=Source.RETAILER,
                observed_on=observed_on,
                source_ref="שם המוצר",
            )
            for claim in reduced
        ]
        if found:
            claims[barcode] = found
    return claims


def merge_claim_sources(
    *sources: dict[str, list[AllergenClaim]],
) -> dict[str, list[AllergenClaim]]:
    """מאחד קביעות מכמה מקורות לכל ברקוד.

    לא מכריע ביניהן. ההכרעה שייכת ל-domain.resolution, שיודע להעדיף
    קביעה מפורשת על נגזרת ולסמן סתירות.
    """
    merged: dict[str, list[AllergenClaim]] = {}
    for source in sources:
        for barcode, claims in source.items():
            merged.setdefault(barcode, []).extend(claims)
    return merged


def _hidden_from_ingredients(
    product: off.OffProduct,
    existing: list[AllergenClaim],
    ingredient_map: IngredientAllergenMap,
    observed_on: date | None,
) -> list[AllergenClaim]:
    """אלרגנים שברשימת הרכיבים ולא בהצהרת התגיות.

    זה המקרה של לציטין סויה שההצהרה החמיצה. הקביעה מיוחסת ל-Open Food
    Facts ולא ליצרן, כי משם הגיע טקסט הרכיבים.
    """
    if not product.ingredients_text:
        return []
    declared = {claim.allergen_id for claim in existing if claim.level is Level.CONTAINS}
    from_ingredients = ingredient_map.allergen_ids(product.ingredients_text)
    return [
        AllergenClaim(
            allergen_id=allergen_id,
            level=Level.CONTAINS,
            source=Source.OPEN_FOOD_FACTS,
            observed_on=observed_on,
            source_ref=f"off-ingredients:{product.barcode}",
        )
        for allergen_id in sorted(from_ingredients - declared)
    ]
