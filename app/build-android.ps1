<#
    בניית APK מקומית, בלי תלות בשירות ענן.

    הסקריפט קיים בגלל תקלה אחת ספציפית למכונה הזו, שלקח זמן לאתר ולכן
    מתועדת כאן במלואה.

    Gradle נפל על "Unable to establish loopback connection" בכל הרצה.
    השגיאה מטעה: אין לה קשר לרשת, לחומת אש או ל-Gradle. מאחוריה עומד
    java.nio.channels.Pipe, ש-JDK מממש ב-Windows דרך שקע AF_UNIX. קובץ
    השקע נוצר בתיקיית ה-TEMP, ובתיקיית ה-TEMP של הפרופיל הזה יצירתו
    נכשלת ב-"Invalid argument". התוצאה היא שכל JVM שפותח Selector מת,
    וזה כולל את דמון Gradle כולו.

    הפתרון הוא להפנות את TEMP לתיקייה נקייה. שימו לב שהפניית מאפיין
    ה-Java בלבד (java.io.tmpdir) אינה מספיקה, כי ברירת המחדל של AF_UNIX
    נגזרת מנתיב ה-TEMP המערכתי ולא מהמאפיין.

    אזהרה למי שיתקן זאת בעתיד: אל תשתמשו ב-JAVA_TOOL_OPTIONS כדי להזריק
    את התיקון. הוא אמנם עובד, אך הוא מדפיס שורה ל-stderr של כל תהליך
    Java, ו-AGP קורא את ה-stderr של prefab. התוצאה היא כישלון שני,
    מטעה לא פחות: "[CXX1210] No compatible library found".
#>

[CmdletBinding()]
param(
    [ValidateSet('debug', 'release')]
    [string]$Variant = 'release',

    [string]$JavaHome = 'C:\Program Files\Eclipse Adoptium\jdk-17.0.20.101-hotspot',
    [string]$AndroidSdk = 'C:\Android\Sdk',
    [string]$BuildTemp = 'C:\jtmp'
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$androidDir = Join-Path $projectRoot 'android'

if (-not (Test-Path $androidDir)) {
    throw "לא נמצאה תיקיית android תחת $projectRoot. יש להריץ 'npx expo prebuild' תחילה."
}
if (-not (Test-Path $JavaHome)) { throw "JDK לא נמצא: $JavaHome" }
if (-not (Test-Path $AndroidSdk)) { throw "Android SDK לא נמצא: $AndroidSdk" }
if (-not (Test-Path $BuildTemp)) { New-Item -ItemType Directory -Path $BuildTemp | Out-Null }

$env:JAVA_HOME = $JavaHome
$env:ANDROID_HOME = $AndroidSdk
$env:ANDROID_SDK_ROOT = $AndroidSdk
$env:TEMP = $BuildTemp
$env:TMP = $BuildTemp
# ראו את האזהרה בראש הקובץ. הזרקה דרך המשתנה הזה שוברת את prefab.
Remove-Item Env:\JAVA_TOOL_OPTIONS -ErrorAction SilentlyContinue

$task = if ($Variant -eq 'release') { 'assembleRelease' } else { 'assembleDebug' }
Write-Host "בונה $Variant. תיקיית עבודה זמנית: $BuildTemp" -ForegroundColor Cyan

Push-Location $androidDir
try {
    & .\gradlew.bat $task --console=plain
    if ($LASTEXITCODE -ne 0) { throw "הבנייה נכשלה (קוד $LASTEXITCODE)." }
}
finally {
    Pop-Location
}

$apk = Get-ChildItem -Path (Join-Path $androidDir "app\build\outputs\apk\$Variant") -Filter *.apk -Recurse |
    Sort-Object LastWriteTime -Descending | Select-Object -First 1

if (-not $apk) { throw 'הבנייה הסתיימה אך לא נמצא קובץ APK.' }

Write-Host ''
Write-Host ('APK מוכן: {0}' -f $apk.FullName) -ForegroundColor Green
Write-Host ('גודל: {0:N1} MB' -f ($apk.Length / 1MB)) -ForegroundColor Green
