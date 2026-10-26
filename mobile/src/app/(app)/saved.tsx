import { useQuery, useQueryClient } from '@tanstack/react-query';
import * as Haptics from 'expo-haptics';
import { router } from 'expo-router';
import { useEffect, useMemo, useState } from 'react';
import { FlatList, Pressable, RefreshControl, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { AppHeader } from '../../components/brand';
import { AppText, Card, EmptyState, ErrorBox, InfoNote, Star, Loading, SearchField, SectionLabel, Segmented, Tag } from '../../components/ui';
import { endpoints } from '../../lib/api';
import { savedTime, shortTime } from '../../lib/format';
import { space, useTheme } from '../../theme';

type Tab = 'answers' | 'standards' | 'chats';

interface Row {
  key: string;
  tag: string;
  title: string;
  snippet: string;
  meta: string;
  open: () => void;
  unsave: () => Promise<void>;
}

/** M/07 — Kaydedilenler */
export default function SavedScreen() {
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const qc = useQueryClient();
  const [tab, setTab] = useState<Tab>('answers');
  const [search, setSearch] = useState('');
  const [q, setQ] = useState('');
  useEffect(() => {
    const t = setTimeout(() => setQ(search.trim()), 300);
    return () => clearTimeout(t);
  }, [search]);

  const answers = useQuery({ queryKey: ['saved-answers', q], queryFn: () => endpoints.savedAnswers(q || undefined), enabled: tab === 'answers' });
  const standards = useQuery({ queryKey: ['saved'], queryFn: () => endpoints.saved(), enabled: tab === 'standards' });
  const chats = useQuery({ queryKey: ['conversations', 'starred', q], queryFn: () => endpoints.conversations({ starred: true, q: q || undefined }), enabled: tab === 'chats' });
  const active = { answers, standards, chats }[tab];

  const refresh = () => {
    void qc.invalidateQueries({ queryKey: ['saved-answers'] });
    void qc.invalidateQueries({ queryKey: ['saved'] });
    void qc.invalidateQueries({ queryKey: ['conversations'] });
    void qc.invalidateQueries({ queryKey: ['documents'] });
  };

  const rows: Row[] = useMemo(() => {
    if (tab === 'answers')
      return (answers.data ?? []).map((a) => ({
        key: `a${a.message_id}`,
        tag: a.sources[0] ?? 'Yanıt',
        title: a.question,
        snippet: a.snippet,
        meta: `${a.source_count} kaynak • ${savedTime(a.saved_at)}`,
        open: () => router.push(`/chat/${a.conversation_id}`),
        unsave: () => endpoints.saveAnswer(a.message_id, false),
      }));
    if (tab === 'standards') {
      const f = q.toLocaleLowerCase('tr-TR');
      return (standards.data ?? [])
        .filter((s) => !f || `${s.code} ${s.doc_title} ${s.heading ?? ''} ${s.snippet ?? ''}`.toLocaleLowerCase('tr-TR').includes(f))
        .map((s) => ({
          key: `s${s.id}`,
          tag: [s.issuer, s.code].filter(Boolean).join(' • '),
          title: s.chunk_id ? [s.clause_ref, s.heading].filter(Boolean).join(' — ') || s.doc_title : s.doc_title,
          snippet: s.chunk_id ? (s.snippet ?? '') : 'Standardın tamamı kaydedildi.',
          meta: `${s.chunk_id ? `Madde • s. ${s.page_start}` : 'Standart'} • ${savedTime(s.created_at)}`,
          open: () => router.push(s.chunk_id ? `/source/${s.chunk_id}` : `/document/${s.document_id}`),
          unsave: () => endpoints.deleteSaved(s.id),
        }));
    }
    return (chats.data ?? []).map((c) => ({
      key: `c${c.id}`,
      tag: c.sources[0] ?? 'Sohbet',
      title: c.title,
      snippet: (c.last_message ?? '').replace(/\*\*/g, '').replace(/\[\d+\]/g, '').slice(0, 200),
      meta: `${Math.ceil(c.message_count / 2)} soru • ${shortTime(c.updated_at)}`,
      open: () => router.push(`/chat/${c.id}`),
      unsave: () => endpoints.starConversation(c.id, false),
    }));
  }, [tab, answers.data, standards.data, chats.data, q]);

  const label = { answers: 'Kaydedilen yanıtlar', standards: 'Kaydedilen standartlar ve maddeler', chats: 'Kaydedilen sohbetler' }[tab];
  const emptyMsg = {
    answers: 'Bir yanıtın altındaki "Kaydet" ile önemli cevapları burada toplayabilirsin.',
    standards: 'Kaynak detayında "Bu kaynağı kaydet" veya standart sayfasındaki yer imi ile kaydedebilirsin.',
    chats: 'Sohbet ekranının üstündeki yıldız ile sohbetleri kaydedebilirsin.',
  }[tab];

  return (
    <View style={{ flex: 1, backgroundColor: colors.bg }}>
      <AppHeader title="Kaydedilenler" />
      <FlatList
        data={active.isLoading || active.isError ? [] : rows}
        keyExtractor={(r) => r.key}
        contentContainerStyle={{ padding: space.lg, gap: 12, paddingBottom: insets.bottom + 24, flexGrow: 1 }}
        refreshControl={<RefreshControl refreshing={active.isRefetching} onRefresh={() => void active.refetch()} tintColor={colors.primary} />}
        ListHeaderComponent={
          <View style={{ gap: space.md }}>
            <Segmented<Tab>
              value={tab}
              onChange={setTab}
              options={[
                { value: 'answers', label: 'Yanıtlar' },
                { value: 'standards', label: 'Standartlar' },
                { value: 'chats', label: 'Sohbetler' },
              ]}
            />
            <SearchField value={search} onChangeText={setSearch} placeholder="Kaydedilenlerde ara" />
            <SectionLabel title={label} />
            {active.isError ? <ErrorBox message={(active.error as Error).message} onRetry={() => active.refetch()} /> : null}
          </View>
        }
        ListEmptyComponent={active.isLoading ? <Loading /> : active.isError ? undefined : <EmptyState icon="star" title="Henüz kayıt yok" message={q ? 'Aramanla eşleşen kayıt bulunamadı.' : emptyMsg} />}
        ListFooterComponent={rows.length ? <InfoNote>Kaydedilenler, önemli yanıtları ve standartları tek yerde tutar.</InfoNote> : undefined}
        renderItem={({ item }) => (
          <Card onPress={item.open} style={{ gap: 8 }}>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
              <View style={{ flex: 1 }}>
                <Tag label={item.tag} />
              </View>
              <Pressable
                hitSlop={10}
                accessibilityLabel="Kaydı kaldır"
                onPress={async () => {
                  void Haptics.selectionAsync().catch(() => {});
                  await item.unsave();
                  refresh();
                }}
              >
                <Star filled size={18} />
              </Pressable>
            </View>
            <AppText variant="label" numberOfLines={2}>{item.title}</AppText>
            {item.snippet ? <AppText variant="caption" color={colors.textMuted} numberOfLines={3}>{item.snippet}</AppText> : null}
            <AppText variant="caption" color={colors.textSubtle}>{item.meta}</AppText>
          </Card>
        )}
      />
    </View>
  );
}
