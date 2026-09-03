// eslint-disable-next-line @typescript-eslint/no-var-requires
const { getDefaultConfig } = require('expo/metro-config');

const config = getDefaultConfig(__dirname);

// תמונת המצב נשלחת ארוזה עם האפליקציה כדי שהיא תעבוד מהשנייה הראשונה
// ובלי רשת. בלי ההרחבה הזו המאגד מתעלם מקובץ ה-sqlite.
config.resolver.assetExts.push('sqlite');

module.exports = config;
