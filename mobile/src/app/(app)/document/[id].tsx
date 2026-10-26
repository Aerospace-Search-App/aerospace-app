import { useQuery } from '@tanstack/react-query';
import { router, useLocalSearchParams } from 'expo-router';
import { useMemo, useState } from 'react';
import { FlatList, Pressable, StyleSheet, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { AppHeader } from '../../../components/brand';
import { AppText, Card, ErrorBox, Eyebrow, Icon, IconSquare, Loading, SearchField, SectionLabel, Star, Tag } from '../../../components/ui';
import { endpoints } from '../../../lib/api';
import { CATEGORY_LABEL } from '../../../lib/format';
import { useSaveToggle } from '../../../lib/useSave';
import { radius, space, useTheme } from '../../../theme';

const STATUS: Record<string, { label: string; tone: 'success' | 'warning' | 'info' | 'neutral' }> = {
  ready: { label: 'Hibrit arama hazır', tone: 'success' },
  lexical_only: { label: 'Tam metin arama', tone: 'info' },
  embedding: { label: 'İndeksleniyor', tone: 'warning' },
  parsing: { label: 'Ayrıştırılıyor', tone: 'warning' },
  queued: { label: 'Sırada', tone: 'neutral' },
};

export default function DocumentScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const docId = Number(id);
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const doc = useQuery({ queryKey: ['document', docId], queryFn: () => endpoints.document(docId) });
  const clauses = useQuery({ queryKey: ['clauses', docId], queryFn: () => endpoints.clauses(docId) });
  const domains = useQuery({ queryKey: ['domains'], queryFn: endpoints.domains, staleTime: Infinity });
  const save = useSaveToggle(docId, null, doc.data?.is_saved ?? false);
  const [filter, setFilter] = useState('');

  const filtered = useMemo(() => {
    const f = filter.trim().toLocaleLowerCase('tr-TR');
    if (!f) return clauses.data ?? [];
    return (clauses.data ?? []).filter((c) => `${c.clause_ref} ${c.heading}`.toLocaleLowerCase('tr-TR').includes(f));
  }, [clauses.data, filter]);

  const d = doc.data;
  const header = d ? (
    <View style={{ gap: space.lg, marginBottom: space.md }}>
      <Card style={{ gap: 12 }}>
        <Eyebrow>{[d.issuer, d.code].filter(Boolean).join(' • ')}</Eyebrow>
        <AppText variant="title">{d.title}</AppText>
        <View style={{ flexDirection: 'row', gap: 6, flexWrap: 'wrap' }}>
          <Tag label={CATEGORY_LABEL[d.category]} tone={d.category === 'defense' ? 'neutral' : 'primary'} />
          <Tag label={(STATUS[d.status] ?? { label: d.status }).label} tone={(STATUS[d.status] ?? { tone: 'neutral' as const }).tone} />
          {d.domains.map((k) => <Tag key={k} label={domains.data?.find((x) => x.key === k)?.label ?? k} tone="neutral" />)}
        </View>
        {d.summary ? <AppText variant="small" color={colors.textMuted}>{d.summary}</AppText> : null}
        <View style={[styles.facts, { backgroundColor: colors.bg }]}>
          <Fact label="Sürüm" value={d.version || '—'} />
          <Fact label="Tarih" value={d.published_on || '—'} />
          <Fact label="Sayfa" value={String(d.page_count)} />
          <Fact label="Madde" value={String(d.chunk_count)} />
        </View>
        {d.status === 'embedding' && d.chunk_count ? (
          <View style={{ gap: 6 }}>
            <View style={[styles.bar, { backgroundColor: colors.surfaceAlt }]}>
              <View style={{ width: `${Math.round((100 * d.embedded_count) / d.chunk_count)}%`, height: '100%', backgroundColor: colors.warning }} />
            </View>
            <AppText variant="caption" color={colors.textMuted}>Anlamsal indeks: {d.embedded_count}/{d.chunk_count}</AppText>
          </View>
        ) : null}
      </Card>
      <SectionLabel title={`Maddeler (${clauses.data?.length ?? 0})`} />
      <SearchField value={filter} onChangeText={setFilter} placeholder="Madde no veya başlıkta filtrele" />
    </View>
  ) : undefined;

  return (
    <View style={{ flex: 1, backgroundColor: colors.bg }}>
      <AppHeader
        title={d?.code ?? 'Standart'}
        right={d ? (
          <IconSquare icon="star" node={<Star filled={save.saved} size={18} color={save.saved ? colors.primary : colors.text} />}
            label={save.saved ? 'Kaydı kaldır' : 'Standardı kaydet'} bg={save.saved ? colors.primarySoft : undefined}
            onPress={save.busy ? undefined : save.toggle} />
        ) : undefined}
      />
      {doc.isLoading ? (
        <Loading />
      ) : doc.isError || !d ? (
        <View style={{ padding: 16 }}><ErrorBox message={(doc.error as Error)?.message ?? 'Bulunamadı'} onRetry={() => doc.refetch()} /></View>
      ) : (
        <FlatList
          data={filtered}
          keyExtractor={(c) => String(c.id)}
          ListHeaderComponent={header}
          contentContainerStyle={{ padding: space.lg, paddingBottom: insets.bottom + 32 }}
          ItemSeparatorComponent={() => <View style={{ height: 1, backgroundColor: colors.border, marginLeft: 70 }} />}
          ListEmptyComponent={clauses.isLoading ? <Loading /> : <AppText color={colors.textMuted}>Madde bulunamadı.</AppText>}
          renderItem={({ item }) => (
            <Pressable onPress={() => router.push(`/source/${item.id}`)}
              style={({ pressed }) => [styles.clause, { backgroundColor: pressed ? colors.surfaceAlt : 'transparent' }]}>
              <View style={[styles.ref, { backgroundColor: colors.primarySoft }]}>
                <AppText variant="mono" color={colors.primary} numberOfLines={1} style={{ fontSize: 11 }}>{item.clause_ref || '•'}</AppText>
              </View>
              <View style={{ flex: 1 }}>
                <AppText variant="label" numberOfLines={2}>{item.heading || (item.clause_ref ? item.clause_ref : 'Ön bölüm')}</AppText>
                <AppText variant="caption" color={colors.textSubtle}>Sayfa {item.page_start}</AppText>
              </View>
              <Icon name="chevron-right" size={16} color={colors.textSubtle} />
            </Pressable>
          )}
        />
      )}
    </View>
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  const { colors } = useTheme();
  return (
    <View style={{ width: '48%', gap: 2 }}>
      <AppText variant="eyebrow" color={colors.textSubtle}>{label.toLocaleUpperCase('tr-TR')}</AppText>
      <AppText variant="smallMedium">{value}</AppText>
    </View>
  );
}

const styles = StyleSheet.create({
  facts: { flexDirection: 'row', flexWrap: 'wrap', rowGap: 12, justifyContent: 'space-between', padding: 14, borderRadius: radius.md },
  bar: { height: 6, borderRadius: 3, overflow: 'hidden' },
  clause: { flexDirection: 'row', alignItems: 'center', gap: 12, paddingVertical: 12, paddingHorizontal: 4, borderRadius: radius.sm },
  ref: { width: 56, minHeight: 30, borderRadius: 8, alignItems: 'center', justifyContent: 'center', paddingHorizontal: 4 },
});
