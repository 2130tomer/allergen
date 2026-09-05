/**
 * תיבת בחירה למסך הסינון.
 *
 * רכיב נפרד מ-AllergenMark במכוון, למרות שהשניים נראים דומים. השניים
 * עונים על שאלות שונות: AllergenMark אומר מה מצב המוצר, ותיבה זו
 * אומרת מה המשתמש בחר להסתיר.
 *
 * ההפרדה נולדה מתקלה ממשית. מסך הסינון השתמש ב-AllergenMark עם
 * level="absent" עבור שורה לא מסומנת, וכשמצב "absent" קיבל משמעות של
 * הצהרת "ללא" וסימון ירוק, כל אלרגן שהמשתמש לא סימן קיבל וי ירוק.
 * כלומר מסך הסינון הודיע למשתמש שהמוצרים נקיים מכל מה שלא בחר.
 *
 * מכאן הכלל: לרכיב הזה אין ולא יהיה מצב ירוק.
 */

import React from 'react';
import { View } from 'react-native';
import Svg, { Line, Rect } from 'react-native-svg';

import { color } from '../theme';

interface Props {
  selected: boolean;
  /** קובע את גוון הסימון בהתאם לרמת הסינון הנערכת. */
  tone: 'contains' | 'mayContain';
  size?: number;
}

export function SelectionBox({
  selected,
  tone,
  size = 22,
}: Props): React.ReactElement {
  const inset = 1.5;
  const box = size - inset * 2;
  const tint = tone === 'contains' ? color.alert : color.caution;

  return (
    <View accessible={false} importantForAccessibility="no-hide-descendants">
      <Svg width={size} height={size}>
        <Rect
          x={inset}
          y={inset}
          width={box}
          height={box}
          fill={selected ? tint : color.surface}
          stroke={selected ? tint : color.rule}
          strokeWidth={1.5}
        />
        {selected ? (
          <>
            <Line
              x1={size * 0.3}
              y1={size * 0.52}
              x2={size * 0.44}
              y2={size * 0.68}
              stroke={color.onAction}
              strokeWidth={2.2}
              strokeLinecap="round"
            />
            <Line
              x1={size * 0.44}
              y1={size * 0.68}
              x2={size * 0.72}
              y2={size * 0.34}
              stroke={color.onAction}
              strokeWidth={2.2}
              strokeLinecap="round"
            />
          </>
        ) : null}
      </Svg>
    </View>
  );
}
