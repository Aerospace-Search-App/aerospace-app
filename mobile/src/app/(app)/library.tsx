import { useQuery } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { FlatList, RefreshControl, ScrollView, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { AppHeader } from '../../components/brand';
import { DocumentCard } from '../../components/DocumentCard';
import { Chip, EmptyState, ErrorBox, Loading, SearchField, Segmented } from '../../components/ui';
import { endpoints } from '../../lib/api';
import { space, useTheme } from '../../theme';

type Cat = 'all' | 'civil' | 'defense';

export default function LibraryScreen() {
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const [search, setSearch] = useState('');
  const [q, setQ] = useState('');
  const [cat, setCat] = useState<Cat>('all');
  const [domain, setDomain] = useState<string | null>(null);
  useEffect(() => {
    const t = setTimeout(() => setQ(search.trim()), 300);
    return () => clearTimeout(t);
  }, [search]);

  const domains = useQuery({ queryKey: ['domains'], queryFn: endpoints.domains, staleTime: Infinity });
  const docs = useQuery({
    queryKey: ['documents', q, cat, domain],
    queryFn: () => endpoints.documents({ q, category: cat === 'all' ? undefined : cat, domain: domain ?? undefined }),
  });
  const filtered = !!(q || domain || cat !== 'all');

  return (
    <View style={{ flex: 1, backgroundColor: colors.bg }}>
      <AppHeader title="Standart kütüphanesi" />
      <FlatList
        data={docs.isLoading || docs.isError ? [] : docs.data}
        keyExtractor={(d) => String(d.id)}
        contentContainerStyle={{ padding: space.lg, paddingBottom: insets.bottom + 24, gap: 12, flexGrow: 1 }}
        refreshControl={<RefreshControl refreshing={docs.isRefetching} onRefresh={() => void docs.refetch()} tintColor={colors.primary} />}
        ListHeaderComponent={
          <View style={{ gap: space.md, marginBottom: 4 }}>
            <SearchField value={search} onChangeText={setSearch} placeholder="Kod veya başlık ara (ör. DO-178, 882)" />
            <Segmented<Cat> value={cat} onChange={setCat} options={[{ value: 'all', label: 'Tümü' }, { value: 'civil', label: 'Sivil' }, { value: 'defense', label: 'Savunma' }]} />
            <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 8 }}>
              <Chip label="Tüm alanlar" selected={!domain} onPress={() => setDomain(null)} />
              {domains.data?.map((d) => (
                <Chip key={d.key} label={d.label} selected={domain === d.key} onPress={() => setDomain(domain === d.key ? null : d.key)} />
              ))}
            </ScrollView>
            {docs.isError ? <ErrorBox message={(docs.error as Error).message} onRetry={() => docs.refetch()} /> : null}
          </View>
        }
        renderItem={({ item }) => <DocumentCard doc={item} />}
        ListEmptyComponent={
          docs.isLoading ? <Loading label="Standartlar yükleniyor…" /> : docs.isError ? undefined : (
            <EmptyState
              icon="book-open"
              title={filtered ? 'Eşleşen standart yok' : 'Henüz standart yüklenmemiş'}
              message={filtered ? 'Filtreleri değiştirerek tekrar dene.' : 'Sunucu ilk açılışta kamuya açık standartları indirir; yönetim panelinden (http://<bilgisayar-ip>:8000/admin) PDF de yükleyebilirsin.'}
            />
          )
        }
      />
    </View>
  );
}
