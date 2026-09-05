#!/usr/bin/env bash
# מסנכרן את קוד האפליקציה לעותק הבנייה בנתיב ASCII.
#
# הפרויקט יושב תחת נתיב עם שם תיקייה בעברית, וכלי הבנייה של אנדרואיד
# נכשלים עליו. לכן הבנייה רצה מעותק ב-C:\allergen-build, והסקריפט הזה
# דוחף אליו את מה שהשתנה. node_modules ו-android אינם מסונכרנים: הם
# נבנים בעותק פעם אחת ואין טעם להעתיק אותם בכל פעם.
set -euo pipefail
SRC="/c/Users/Tomer Menashe/Documents/אלרגן/app"
DST="/c/allergen-build"
for item in App.tsx app.json eas.json babel.config.js metro.config.js package.json tsconfig.json build-android.ps1; do
  [ -e "$SRC/$item" ] && cp -f "$SRC/$item" "$DST/$item"
done
rm -rf "$DST/src"
cp -r "$SRC/src" "$DST/src"
mkdir -p "$DST/assets"
cp -f "$SRC/assets/allergen-snapshot.sqlite" "$DST/assets/allergen-snapshot.sqlite"
echo "synced app -> $DST"
