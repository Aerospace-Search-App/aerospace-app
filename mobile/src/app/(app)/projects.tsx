import { useQuery } from '@tanstack/react-query';
import { router } from 'expo-router';
import { FlatList, RefreshControl, StyleSheet, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { AppHeader } from '../../components/brand';
import { AppText, Button, Card, EmptyState, ErrorBox, Icon, IconSquare, IconTile, InfoNote, Loading, Tag } from '../../components/ui';
import { endpoints } from '../../lib/api';
import { CATEGORY_LABEL, shortTime } from '../../lib/format';
import { space, useTheme } from '../../theme';

export default function ProjectsScreen() {
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const projects = useQuery({ queryKey: ['projects'], queryFn: endpoints.projects });
  const domains = useQuery({ queryKey: ['domains'], queryFn: endpoints.domains, staleTime: Infinity });
  const label = (k: string) => domains.data?.find((d) => d.key === k)?.label ?? k;

  return (
    <View style={{ flex: 1, backgroundColor: colors.bg }}>
      <AppHeader title="Projelerim" right={<IconSquare icon="plus" label="Yeni proje" onPress={() => router.push('/project/edit')} />} />
      <FlatList
        data={projects.isLoading || projects.isError ? [] : projects.data}
        keyExtractor={(p) => String(p.id)}
        contentContainerStyle={{ padding: space.lg, gap: 12, flexGrow: 1, paddingBottom: insets.bottom + 24 }}
        refreshControl={<RefreshControl refreshing={projects.isRefetching} onRefresh={() => void projects.refetch()} tintColor={colors.primary} />}
        ListHeaderComponent={
          <View style={{ gap: 12 }}>
            <InfoNote>Projeni ve çalışma alanlarını tanımla; ilgili standartları ve kritik maddeleri önerelim.</InfoNote>
            {projects.isError ? <ErrorBox message={(projects.error as Error).message} onRetry={() => projects.refetch()} /> : null}
          </View>
        }
        ListEmptyComponent={
          projects.isLoading ? <Loading /> : projects.isError ? undefined : (
            <EmptyState icon="briefcase" title="İlk projeni oluştur" message="Örn. “İHA uçuş kontrol yazılımı — DO-178C seviye B”."
              action={<Button title="Proje oluştur" icon="plus" onPress={() => router.push('/project/edit')} style={{ marginTop: 8 }} />} />
          )
        }
        renderItem={({ item }) => (
          <Card onPress={() => router.push(`/project/${item.id}`)} style={{ gap: 10 }}>
            <View style={styles.row}>
              <IconTile icon="briefcase" size={40} />
              <View style={{ flex: 1, gap: 2 }}>
                <AppText variant="label" numberOfLines={1}>{item.name}</AppText>
                <AppText variant="caption" color={colors.textMuted}>{CATEGORY_LABEL[item.category]} • {shortTime(item.updated_at)}</AppText>
              </View>
              <Icon name="chevron-right" size={18} color={colors.textSubtle} />
            </View>
            {item.description ? <AppText variant="caption" color={colors.textMuted} numberOfLines={2}>{item.description}</AppText> : null}
            {item.domains.length ? (
              <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6 }}>
                {item.domains.map((d) => <Tag key={d} label={label(d)} />)}
              </View>
            ) : null}
            <AppText variant="caption" color={colors.textSubtle}>{item.conversation_count} sohbet • {item.saved_count} kayıt</AppText>
          </Card>
        )}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center', gap: 12 },
});
