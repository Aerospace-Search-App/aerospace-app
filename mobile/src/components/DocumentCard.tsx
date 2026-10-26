import { router } from 'expo-router';
import type { ReactNode } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';

import { CATEGORY_LABEL } from '../lib/format';
import type { DocumentItem } from '../lib/types';
import { useSaveToggle } from '../lib/useSave';
import { useTheme } from '../theme';
import { AppText, Card, Eyebrow, Icon, IconTile, Star, Tag } from './ui';

export function DocumentCard({ doc, footer }: { doc: DocumentItem; footer?: ReactNode }) {
  const { colors } = useTheme();
  const { saved, toggle, busy } = useSaveToggle(doc.id, null, doc.is_saved);
  return (
    <Card onPress={() => router.push(`/document/${doc.id}`)} style={{ gap: 10 }}>
      <View style={styles.top}>
        <IconTile icon={doc.category === 'defense' ? 'shield' : 'navigation'} size={40} tone={doc.category === 'defense' ? 'neutral' : 'primary'} />
        <View style={{ flex: 1, gap: 4 }}>
          <Eyebrow>{[doc.issuer, doc.code].filter(Boolean).join(' • ')}</Eyebrow>
          <AppText variant="label" numberOfLines={2}>{doc.title}</AppText>
        </View>
        <Pressable onPress={busy ? undefined : toggle} hitSlop={10} accessibilityLabel={saved ? 'Kaydı kaldır' : 'Standardı kaydet'}>
          <Star filled={saved} size={19} />
        </Pressable>
      </View>
      <View style={styles.meta}>
        <Tag label={CATEGORY_LABEL[doc.category]} tone={doc.category === 'defense' ? 'neutral' : 'primary'} />
        {doc.language === 'tr' ? <Tag label="Türkçe" tone="info" /> : null}
        <Meta icon="file-text" text={`${doc.page_count} sayfa`} />
        <Meta icon="list" text={`${doc.chunk_count} madde`} />
      </View>
      {footer}
    </Card>
  );
}

function Meta({ icon, text }: { icon: 'file-text' | 'list'; text: string }) {
  const { colors } = useTheme();
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 4 }}>
      <Icon name={icon} size={12} color={colors.textSubtle} />
      <AppText variant="caption" color={colors.textMuted}>{text}</AppText>
    </View>
  );
}

const styles = StyleSheet.create({
  top: { flexDirection: 'row', gap: 12, alignItems: 'flex-start' },
  meta: { flexDirection: 'row', gap: 10, flexWrap: 'wrap', alignItems: 'center' },
});
