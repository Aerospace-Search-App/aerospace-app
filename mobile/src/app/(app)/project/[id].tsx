import { useQuery, useQueryClient } from '@tanstack/react-query';
import { router, useLocalSearchParams } from 'expo-router';
import { Alert, Platform, Pressable, RefreshControl, ScrollView, StyleSheet, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { AppHeader } from '../../../components/brand';
import { DocumentCard } from '../../../components/DocumentCard';
import { AppText, Button, Card, EmptyState, ErrorBox, Icon, IconSquare, Loading, SectionLabel, Tag } from '../../../components/ui';
import { endpoints } from '../../../lib/api';
import { CATEGORY_LABEL } from '../../../lib/format';
import { radius, space, useTheme } from '../../../theme';

export default function ProjectScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const pid = Number(id);
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const qc = useQueryClient();
  const project = useQuery({ queryKey: ['project', pid], queryFn: () => endpoints.project(pid) });
  const recs = useQuery({ queryKey: ['recommendations', pid], queryFn: () => endpoints.recommendations(pid) });
  const domains = useQuery({ queryKey: ['domains'], queryFn: endpoints.domains, staleTime: Infinity });

  const remove = async () => {
    await endpoints.deleteProject(pid);
    await qc.invalidateQueries({ queryKey: ['projects'] });
    router.back();
  };
  const confirmRemove = () => {
    if (Platform.OS === 'web') return void remove();
    Alert.alert('Proje silinsin mi?', 'Sohbetler ve kayıtlar silinmez, yalnızca proje bağlantısı kalkar.', [
      { text: 'Vazgeç', style: 'cancel' },
      { text: 'Sil', style: 'destructive', onPress: () => void remove() },
    ]);
  };

  const p = project.data;
  return (
    <View style={{ flex: 1, backgroundColor: colors.bg }}>
      <AppHeader
        title={p?.name ?? 'Proje'}
        right={p ? (
          <>
            <IconSquare icon="edit-2" label="Düzenle" onPress={() => router.push({ pathname: '/project/edit', params: { id: String(pid) } })} />
            <IconSquare icon="trash-2" label="Sil" color={colors.danger} onPress={confirmRemove} />
          </>
        ) : undefined}
      />
      {project.isLoading ? (
        <Loading />
      ) : project.isError || !p ? (
        <View style={{ padding: 16 }}><ErrorBox message={(project.error as Error)?.message ?? 'Bulunamadı'} onRetry={() => project.refetch()} /></View>
      ) : (
        <ScrollView
          contentContainerStyle={{ padding: space.lg, gap: space.lg, paddingBottom: insets.bottom + 32 }}
          refreshControl={<RefreshControl refreshing={recs.isRefetching} onRefresh={() => { void project.refetch(); void recs.refetch(); }} tintColor={colors.primary} />}
        >
          <Card style={{ gap: 12 }}>
            <View style={{ flexDirection: 'row', gap: 6, flexWrap: 'wrap' }}>
              <Tag label={CATEGORY_LABEL[p.category]} tone="neutral" />
              {p.domains.map((d) => <Tag key={d} label={domains.data?.find((x) => x.key === d)?.label ?? d} />)}
            </View>
            {p.description ? <AppText variant="small" color={colors.textMuted}>{p.description}</AppText> : null}
            <Button title="Bu proje hakkında sor" icon="message-square" size="md"
              onPress={() => router.dismissTo({ pathname: '/home', params: { project: String(pid), t: String(Date.now()) } })} />
          </Card>

          <SectionLabel title="Bilmen gereken standartlar" />
          {recs.isLoading ? (
            <Loading label="Projen için standartlar analiz ediliyor…" />
          ) : recs.isError ? (
            <ErrorBox message={(recs.error as Error).message} onRetry={() => recs.refetch()} />
          ) : !recs.data?.length ? (
            <EmptyState icon="search" title="Henüz öneri yok"
              message="Proje açıklamasını detaylandır veya çalışma alanı seç; ilgili standart henüz yüklü olmayabilir." />
          ) : (
            recs.data.map((r, i) => (
              <DocumentCard
                key={r.document.id}
                doc={r.document}
                footer={
                  <View style={{ gap: 8 }}>
                    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
                      <View style={[styles.rank, { backgroundColor: i < 3 ? colors.primary : colors.surfaceAlt }]}>
                        <AppText variant="eyebrow" color={i < 3 ? '#fff' : colors.textMuted}>{i + 1}</AppText>
                      </View>
                      <AppText variant="caption" color={colors.textMuted} style={{ flex: 1 }}>{r.reasons.join(' · ')}</AppText>
                    </View>
                    {r.clauses.map((c) => (
                      <Pressable key={c.chunk_id} onPress={() => router.push(`/source/${c.chunk_id}`)}
                        style={({ pressed }) => [styles.clause, { backgroundColor: colors.bg, opacity: pressed ? 0.7 : 1 }]}>
                        <Icon name="file-text" size={14} color={colors.primary} />
                        <AppText variant="caption" numberOfLines={1} style={{ flex: 1 }}>
                          <AppText variant="caption" style={{ fontWeight: '700' }}>{c.clause_ref || `s. ${c.page_start}`}</AppText>
                          {c.heading ? `  ${c.heading}` : ''}
                        </AppText>
                        <Icon name="chevron-right" size={14} color={colors.textSubtle} />
                      </Pressable>
                    ))}
                  </View>
                }
              />
            ))
          )}
        </ScrollView>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  rank: { width: 20, height: 20, borderRadius: 10, alignItems: 'center', justifyContent: 'center' },
  clause: { flexDirection: 'row', alignItems: 'center', gap: 8, paddingVertical: 9, paddingHorizontal: 10, borderRadius: radius.sm },
});
