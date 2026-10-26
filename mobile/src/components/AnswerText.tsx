import { Fragment, type ReactNode } from 'react';
import { Text, View } from 'react-native';

import { fonts, type, useTheme } from '../theme';

/**
 * Model cevabını hafif bir markdown alt kümesiyle çizer:
 *  - "- " / "* " / "1. " ile başlayan satırlar → madde işaretli liste
 *  - **kalın**
 *  - [3] → dokunulabilir kaynak atfı
 */
export function AnswerText({
  text,
  color,
  onCitation,
  validCitations,
}: {
  text: string;
  color?: string;
  onCitation?: (n: number) => void;
  validCitations?: Set<number>;
}) {
  const { colors } = useTheme();
  const fg = color ?? colors.text;
  const lines = text.split('\n').filter((l, i, arr) => l.trim() !== '' || (i > 0 && arr[i - 1].trim() !== ''));

  const inline = (s: string, keyBase: string): ReactNode[] => {
    const parts = s.split(/(\*\*[^*]+\*\*|\[\d{1,2}\])/g).filter(Boolean);
    return parts.map((p, i) => {
      const key = `${keyBase}-${i}`;
      const bold = /^\*\*(.+)\*\*$/.exec(p);
      if (bold) return <Text key={key} style={{ fontFamily: fonts.semibold }}>{bold[1]}</Text>;
      const cite = /^\[(\d{1,2})\]$/.exec(p);
      if (cite) {
        const n = Number(cite[1]);
        if (validCitations && !validCitations.has(n)) return null;
        return (
          <Text
            key={key}
            onPress={onCitation ? () => onCitation(n) : undefined}
            accessibilityRole="link"
            accessibilityLabel={`Kaynak ${n}`}
            style={{ fontFamily: fonts.bold, fontSize: 12, color: colors.primary, backgroundColor: colors.primarySoft }}
          >
            {` ${n} `}
          </Text>
        );
      }
      return <Fragment key={key}>{p}</Fragment>;
    });
  };

  return (
    <View style={{ gap: 6 }}>
      {lines.map((raw, i) => {
        const line = raw.trimEnd();
        const bullet = /^\s*(?:[-*•]|(\d+)[.)])\s+(.*)$/.exec(line);
        if (bullet) {
          const marker = bullet[1] ? `${bullet[1]}.` : '•';
          return (
            <View key={i} style={{ flexDirection: 'row', gap: 8, paddingLeft: raw.startsWith('  ') ? 14 : 2 }}>
              <Text style={[type.body, { color: colors.primary, fontFamily: fonts.semibold, minWidth: 12 }]}>{marker}</Text>
              <Text style={[type.body, { color: fg, flex: 1 }]} selectable>
                {inline(bullet[2], `l${i}`)}
              </Text>
            </View>
          );
        }
        if (!line.trim()) return <View key={i} style={{ height: 2 }} />;
        return (
          <Text key={i} style={[type.body, { color: fg }]} selectable>
            {inline(line.replace(/^#+\s*/, ''), `l${i}`)}
          </Text>
        );
      })}
    </View>
  );
}
