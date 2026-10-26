import { useQuery, useQueryClient } from '@tanstack/react-query';
import { router } from 'expo-router';
import { useEffect, useMemo, useState } from 'react';
import { Alert, Platform, RefreshControl, SectionList, StyleSheet, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { AppHeader } from '../../components/brand';
import { AppText, Button, Card, EmptyState, ErrorBox, IconTile, Star, InfoNote, Loading, SearchField, SectionLabel } from '../../components/ui';
import { endpoints } from '../../lib/api';
import { dayBucket, shortTime } from '../../lib/format';
import type { Conversation } from '../../lib/types';
import { space, useTheme } from '../../theme';

/** M/06 — Sohbetler */
export default function HistoryScreen() {
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const qc = useQueryClient();
  const [search, setSearch] = useState('');
  const [q, setQ] = useState('');
  useEffect(() => {
    const t = setTimeout(() => setQ(search.trim()), 300);
    return () => clearTimeout(t);
  }, [search]);

  const list = useQuery({ queryKey: ['conversations', q], queryFn: () => endpoints.conversations({ q: q || undefined }) });

  const sections = useMemo(() => {
    const groups = new Map<string, Conversation[]>();
    for (const c of list.data ?? []) {
      const k = dayBucket(c.updated_at);
      groups.set(k, [...(groups.get(k) ?? []), c]);
    }
    return ['BUGÜN', 'SON 7 GÜN', 'DAHA ÖNCE'].filter((k) => groups.has(k)).map((k) => ({ title: k, data: groups.get(k)! }));
  }, [list.data]);

  const remove = (c: Conversation) => {
    const run = async () => {
      await endpoints.deleteConversation(c.id);
      void qc.invalidateQueries({ queryKey: ['conversations'] });
    };
    if (Platform.OS === 'web') return void run();
    Alert.alert('Sohbet silinsin mi?', `"${c.title}" kalıcı olarak silinecek.`, [
      { text: 'Vazgeç', style: 'cancel' },
      { text: 'Sil', style: 'destructive', onPress: () => void run() },
    ]);
  };

  const header = (
    <View style={{ gap: space.md, marginBottom: space.sm }}>
      <SearchField value={search} onChangeText={setSearch} placeholder="Sohbetlerde ara" />
      <Button title="Yeni sohbet" icon="plus" variant="secondary" onPress={() => router.dismissTo({ pathname: '/home', params: { t: String(Date.now()) } })} />
    </View>
  );

  return (
    <View style={{ flex: 1, backgroundColor: colors.bg }}>
      <AppHeader title="Sohbetler" />
      {list.isLoading ? (
        <Loading />
      ) : list.isError ? (
        <View style={{ padding: space.lg }}><ErrorBox message={(list.error as Error).message} onRetry={() => list.refetch()} /></View>
      ) : (
        <SectionList
          sections={sections}
          keyExtractor={(c) => String(c.id)}
          stickySectionHeadersEnabled={false}
          contentContainerStyle={{ padding: space.lg, paddingBottom: insets.bottom + 24, gap: 10 }}
          ListHeaderComponent={header}
          refreshControl={<RefreshControl refreshing={list.isRefetching} onRefresh={() => void list.refetch()} tintColor={colors.primary} />}
          renderSectionHeader={({ section }) => <SectionLabel title={section.title} style={{ marginTop: 10 }} />}
          ListEmptyComponent={
            <EmptyState icon="message-square" title={q ? 'Eşleşen sohbet yok' : 'Henüz sohbet yok'}
              message={q ? 'Farklı bir kelimeyle aramayı dene.' : 'Ana ekrandan ilk sorunu sorduğunda sohbetlerin burada listelenir.'} />
          }
          ListFooterComponent={list.data?.length ? <View style={{ marginTop: 6 }}><InfoNote>Sohbetler otomatik olarak geçmişe eklenir. Silmek için basılı tutun.</InfoNote></View> : undefined}
          renderItem={({ item }) => (
            <Card onPress={() => router.push(`/chat/${item.id}`)} onLongPress={() => remove(item)} style={styles.row}>
              <IconTile letter="A" size={40} />
              <View style={{ flex: 1, gap: 2 }}>
                <AppText variant="label" numberOfLines={1}>{item.title}</AppText>
                <AppText variant="caption" color={colors.textMuted} numberOfLines={1}>
                  {[item.project_name, item.sources[0], shortTime(item.updated_at)].filter(Boolean).join(' • ')}
                </AppText>
              </View>
              {item.starred ? <Star filled size={15} /> : null}
            </Card>
          )}
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center', gap: 12, paddingVertical: 14 },
});
