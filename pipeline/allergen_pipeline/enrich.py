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
REQUESTS_PER_MINUTE = 30
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
        return barcode in self._entries

    def get(self, barcode: str) -> dict | None:
        entry = self._entries.get(barcode)
        return entry or None

    def remember(self, barcode: str, payload: dict | None) -> None:
        # מוצר שלא נמצא נשמר כאובייקט ריק, כדי שלא נחזור לשאול עליו.
        self._entries[barcode] = payload or {}

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self._entries, ensure_ascii=False), encoding="utf-8"
        )

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
    observed_on: date,
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

        claims = off.to_claims(product, observed_on)
        hidden = _hidden_from_ingredients(product, claims, ingredient_map, observed_on)
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


def load_manufacturer_claims(path: Path) -> dict[str, list[AllergenClaim]]:
    """קורא קביעות יצרן שנשמרו על ידי fetch_manufacturers.

    הקביעות נטענות מקובץ ולא נמשכות ברשת בכל בנייה, כי אתרי היצרנים
    איטיים ואין סיבה להטריד אותם בכל ריצה.
    """
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}

    claims_by_barcode: dict[str, list[AllergenClaim]] = {}
    for barcode, record in raw.items():
        observed_on = date.fromisoformat(record["observed_on"])
        claims_by_barcode[barcode] = [
            AllergenClaim(
                allergen_id=entry["allergen_id"],
                level=Level(entry["level"]),
                source=Source.MANUFACTURER,
                observed_on=observed_on,
                source_ref=record.get("page_url"),
                level_inferred=bool(entry.get("level_inferred")),
            )
            for entry in record.get("claims", [])
        ]
    return claims_by_barcode


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
    observed_on: date,
) -> list[AllergenClaim]:
    """אלרגנים שברשימת הרכיבים ולא בהצהרת התגיות.

    זה המקרה של לציטין סויה שההצהרה החמיצה. הקביעה מיוחסת ל-Open Food
    Facts ולא ליצרן, כי משם הגיע טקסט הרכיבים.
    """
    if not product.ingredients_text:
        return []
    declared = {claim.allergen_id for claim in existing}
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
