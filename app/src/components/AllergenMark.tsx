/**
 * סימן המצב של אלרגן. זהו האלמנט החוזר שסביבו בנוי כל הממשק.
 *
 * ארבעה מצבים, וכל אחד נבדל מהאחרים גם בצורה ולא רק בצבע, כדי שהוא
 * יעבוד גם בעיוורון צבעים וגם בשמש ישירה מול מדף:
 *
 *   מכיל        ריבוע מלא
 *   עלול להכיל  קווקוו אלכסוני
 *   אין מידע    מסגרת מקווקוות וריק במרכז
 *   לא צוין     מסגרת דקה ושקטה
 *
 * המצב "אין מידע" מצויר בכוונה כמשהו רועש ולא כהיעדר. זו הנקודה שבה
 * אפליקציות אחרות מציגות וי ירוק, ואצלנו אסור להציג שום דבר שנקרא
 * כאישור. ראו CONTEXT.md, מונחים אסורים.
 */

import React from 'react';
import { View } from 'react-native';
import Svg, { Defs, Line, Pattern, Rect } from 'react-native-svg';

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
          <Rect
            x={inset}
            y={inset}
            width={box}
            height={box}
            fill="none"
            stroke={color.rule}
            strokeWidth={1.5}
          />
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
    default:
      return color.inkMuted;
  }
}
