"""הפורטל המשותף של רוב רשתות המזון.

רמי לוי, ויקטורי, יוחננוף וחצי חינם מפרסמים דרך url.publishedprices.co.il,
שהוא לקוח קבצים מסוג Cerberus. הגישה דורשת התחברות, אבל אין כאן סוד:
שם המשתמש פומבי ומופיע בהנחיות של רשות התחרות, והסיסמה ריקה. זו דרישה
טכנית של הפורטל ולא מחסום.

שלושת השלבים: דף התחברות לקבלת אסימון CSRF, שליחת טופס, ואז דף רשימת
הקבצים שמכיל קישורי הורדה ישירים. קבצי PriceFull הם הקטלוג המלא;
קבצי Price הם עדכוני מחיר בלבד ואינם מתאימים לבניית קטלוג.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import httpx

BASE_URL = "https://url.publishedprices.co.il"
LOGIN_PAGE = f"{BASE_URL}/login"
LOGIN_ACTION = f"{BASE_URL}/login/user"
FILE_LIST = f"{BASE_URL}/file"
FILE_LIST_JSON = f"{BASE_URL}/file/json/dir"
DOWNLOAD = f"{BASE_URL}/file/d/{{filename}}"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)
REQUEST_TIMEOUT = 90.0

_CSRF = re.compile(r'name="csrftoken"\s+content="([^"]+)"', re.IGNORECASE)


class LoginFailed(Exception):
    """ההתחברות לפורטל נכשלה. אין טעם להמשיך לבקש קבצים."""


@dataclass(frozen=True)
class RemoteFile:
    filename: str
    store_id: str | None

    @property
    def url(self) -> str:
        return DOWNLOAD.format(filename=self.filename)


def _store_of(filename: str) -> str | None:
    parts = filename.split("-")
    return parts[2] if len(parts) >= 3 else None


def make_client() -> httpx.Client:
    return httpx.Client(
        headers={"User-Agent": USER_AGENT},
        timeout=REQUEST_TIMEOUT,
        follow_redirects=True,
    )


def login(client: httpx.Client, username: str) -> None:
    """מתחבר לפורטל. הסיסמה ריקה בכוונה; כך הוא מוגדר."""
    page = client.get(LOGIN_PAGE)
    page.raise_for_status()
    match = _CSRF.search(page.text)
    if not match:
        raise LoginFailed("לא נמצא אסימון CSRF בדף ההתחברות")

    response = client.post(
        LOGIN_ACTION,
        data={
            "r": "",
            "username": username,
            "password": "",
            "csrftoken": match.group(1),
        },
    )
    response.raise_for_status()
    if "csrftoken" not in response.text or "login-form" in response.text:
        raise LoginFailed(f"ההתחברות כ-{username} נדחתה")


def list_price_full_files(
    client: httpx.Client, page_size: int = 2000
) -> list[RemoteFile]:
    """קבצי הקטלוג המלא בלבד.

    רשימת הקבצים אינה ב-HTML אלא נטענת מנקודת JSON. ניסיון לגרד את
    הדף מחזיר אפס קבצים ונראה כאילו הפורטל ריק.

    הפורטל מגיש גם קבצי Price, שהם עדכוני מחיר חלקיים. שימוש בהם
    לבניית קטלוג היה מייצר קטלוג חסר שנראה שלם.
    """
    page = client.get(FILE_LIST)
    page.raise_for_status()
    match = _CSRF.search(page.text)
    if not match:
        raise LoginFailed("לא נמצא אסימון CSRF בדף הקבצים")

    response = client.post(
        FILE_LIST_JSON,
        data={
            "sEcho": "1",
            "iDisplayStart": "0",
            "iDisplayLength": str(page_size),
            "csrftoken": match.group(1),
        },
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("error"):
        raise LoginFailed(str(payload["error"]))

    seen: dict[str, None] = {}
    for row in payload.get("aaData") or []:
        filename = str(row.get("fname") or "")
        if filename.lower().startswith("pricefull") and filename.endswith(".gz"):
            seen.setdefault(filename, None)
    return [RemoteFile(filename=name, store_id=_store_of(name)) for name in seen]


def download(client: httpx.Client, remote: RemoteFile) -> bytes:
    response = client.get(remote.url)
    response.raise_for_status()
    return response.content
