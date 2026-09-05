/**
 * סימן המצב של אלרגן. זהו האלמנט החוזר שסביבו בנוי כל הממשק.
 *
 * ארבעה מצבים, וכל אחד נבדל מהאחרים גם בצורה ולא רק בצבע, כדי שהוא
 * יעבוד גם בעיוורון צבעים וגם בשמש ישירה מול מדף:
 *
 *   מכיל          ריבוע מלא
 *   עלול להכיל    קווקוו אלכסוני
 *   אין מידע      מסגרת מקווקוות וריק במרכז
 *   הוצהר "ללא"   ריבוע ירוק עם סימן וי
 *
 * שני המצבים האחרונים הם לב העניין, וההבדל ביניהם הוא ההבדל בין
 * אפליקציה בטוחה למסוכנת:
 *
 * "אין מידע" מצויר בכוונה כמשהו רועש ולא כהיעדר שקט. זו הנקודה שבה
 * אפליקציות אחרות מציגות וי ירוק על סמך כלום.
 *
 * הירוק שמור אך ורק להצהרת "ללא" מפורשת שהיצרן הדפיס על האריזה, והוא
 * לעולם אינו מסקנה שלנו. הוא אומר "היצרן הצהיר", לא "בדקנו ומצאנו".
 * ראו CONTEXT.md, מונחים אסורים.
 */

import React from 'react';
import { View } from 'react-native';
import Svg, { Defs, Line, Path, Pattern, Rect } from 'react-native-svg';

import type { Level } from '../domain/filter';
import { color } from '../theme';

interface Props {
  level: Level;
  size?: number;
}

const HATCH_ID = 'allergen-hatch';

export function AllergenMark({ level, size = 22 }: Props): React.ReactElement {
  const inset = 1.5;
  const box = size - inset * 2;

  return (
    <View accessible={false} importantForAccessibility="no-hide-descendants">
      <Svg width={size} height={size}>
        {level === 'may_contain' && (
          <Defs>
            <Pattern
              id={HATCH_ID}
              patternUnits="userSpaceOnUse"
              width={5}
              height={5}
              patternTransform="rotate(45)"
            >
              <Line
                x1={0}
                y1={0}
                x2={0}
                y2={5}
                stroke={color.caution}
                strokeWidth={2.2}
              />
            </Pattern>
          </Defs>
        )}

        {level === 'contains' && (
          <Rect
            x={inset}
            y={inset}
            width={box}
            height={box}
            fill={color.alert}
            stroke={color.alert}
            strokeWidth={1.5}
          />
        )}

        {level === 'may_contain' && (
          <Rect
            x={inset}
            y={inset}
            width={box}
            height={box}
            fill={`url(#${HATCH_ID})`}
            stroke={color.caution}
            strokeWidth={1.5}
          />
        )}

        {level === 'unknown' && (
          <Rect
            x={inset}
            y={inset}
            width={box}
            height={box}
            fill={color.unknownSoft}
            stroke={color.unknown}
            strokeWidth={1.5}
            strokeDasharray="3 3"
          />
        )}

        {level === 'absent' && (
          <>
            <Rect
              x={inset}
              y={inset}
              width={box}
              height={box}
              fill={color.declaredFreeSoft}
              stroke={color.declaredFree}
              strokeWidth={1.5}
            />
            {/* הווי הוא ההבחנה שאינה תלויה בצבע. */}
            <Path
              d={`M ${size * 0.28} ${size * 0.52}
                  L ${size * 0.44} ${size * 0.68}
                  L ${size * 0.74} ${size * 0.33}`}
              stroke={color.declaredFree}
              strokeWidth={2.2}
              strokeLinecap="round"
              strokeLinejoin="round"
              fill="none"
            />
          </>
        )}
      </Svg>
    </View>
  );
}

/** צבע הטקסט שמלווה כל סימן. */
export function inkForLevel(level: Level): string {
  switch (level) {
    case 'contains':
      return color.alert;
    case 'may_contain':
      return color.caution;
    case 'unknown':
      return color.unknown;
    case 'absent':
      return color.declaredFree;
    default:
      return color.inkMuted;
  }
}
