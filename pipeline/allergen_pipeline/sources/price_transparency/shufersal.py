"""הורדת קבצי שקיפות מחירים משופרסל.

לשופרסל פורטל ייעודי משלה, בלי התחברות. הדף מציג טבלה עם קישורים
חתומים לאחסון בענן, והקישורים פגים אחרי זמן קצר, ולכן צריך לקרוא את
הדף ולהוריד מיד ולא לשמור כתובות.

catID=2 הוא PriceFull, כלומר הקטלוג המלא של הסניף. catID=1 הוא עדכוני
מחיר בלבד ואינו מכיל את כל הפריטים, ולכן אינו מתאים לבניית קטלוג.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import httpx

PORTAL_URL = "https://prices.shufersal.co.il/FileObject/UpdateCategory"

# הקטגוריות בפורטל. אנחנו צריכים רק את הקטלוג המלא.
CATEGORY_PRICE_FULL = 2
CATEGORY_STORES = 5

_FILE_LINK = re.compile(
    r'href="(https://pricesprodpublic\.blob\.core\.windows\.net/[^"]+?\.gz[^"]*)"',
    re.IGNORECASE,
)
_FILENAME = re.compile(r"/(?P<name>[A-Za-z]+\d+-\d+-\d+-\d+-\d+\.gz)", re.IGNORECASE)

USER_AGENT = "allergen-il/0.1 (+catalog builder; contact via repository)"
REQUEST_TIMEOUT = 90.0


@dataclass(frozen=True)
class RemoteFile:
    url: str
    filename: str
    store_id: str | None


def _filename_of(url: str) -> str:
    match = _FILENAME.search(url)
    return match.group("name") if match else url.rsplit("/", 1)[-1].split("?")[0]


def _store_of(filename: str) -> str | None:
    parts = filename.split("-")
    return parts[2] if len(parts) >= 3 else None


def list_price_full_files(
    client: httpx.Client,
    page: int = 1,
    store_id: int = 0,
) -> list[RemoteFile]:
    """קורא עמוד אחד מהפורטל ומחזיר את הקישורים שבו."""
    response = client.get(
        PORTAL_URL,
        params={"catID": CATEGORY_PRICE_FULL, "storeId": store_id, "page": page},
    )
    response.raise_for_status()

    files: list[RemoteFile] = []
    seen: set[str] = set()
    for raw_url in _FILE_LINK.findall(response.text):
        url = raw_url.replace("&amp;", "&")
        filename = _filename_of(url)
        if filename in seen:
            continue
        seen.add(filename)
        files.append(RemoteFile(url=url, filename=filename, store_id=_store_of(filename)))
    return files


def download(client: httpx.Client, remote: RemoteFile) -> bytes:
    """מוריד קובץ אחד. הקישור חתום ופג, ולכן ההורדה מיידית."""
    response = client.get(remote.url)
    response.raise_for_status()
    return response.content


def make_client() -> httpx.Client:
    """לקוח HTTP שמזהה את עצמו. אנחנו קוראים נתונים שפרסומם מחויב בחוק."""
    return httpx.Client(
        headers={"User-Agent": USER_AGENT},
        timeout=REQUEST_TIMEOUT,
        follow_redirects=True,
    )
