import Feather from '@expo/vector-icons/Feather';
import { useQuery } from '@tanstack/react-query';
import { router } from 'expo-router';
import { Modal, Pressable, ScrollView, StyleSheet, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { endpoints } from '../lib/api';
import type { Project } from '../lib/types';
import { radius, useTheme } from '../theme';
import { AppText, Button, Loading } from './ui';

export function ProjectPicker({
  visible,
  selectedId,
  onSelect,
  onClose,
}: {
  visible: boolean;
  selectedId: number | null;
  onSelect: (p: Project | null) => void;
  onClose: () => void;
}) {
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const projects = useQuery({ queryKey: ['projects'], queryFn: endpoints.projects, enabled: visible });

  const Row = ({ p }: { p: Project | null }) => {
    const active = (p?.id ?? null) === selectedId;
    return (
      <Pressable
        onPress={() => {
          onSelect(p);
          onClose();
        }}
        style={({ pressed }) => [
          styles.row,
          { backgroundColor: active ? colors.primarySoft : pressed ? colors.surfaceAlt : 'transparent' },
        ]}
      >
        <View style={[styles.icon, { backgroundColor: p ? colors.primarySoft : colors.surfaceAlt }]}>
          <Feather name={p ? 'briefcase' : 'globe'} size={17} color={p ? colors.primary : colors.textMuted} />
        </View>
        <View style={{ flex: 1 }}>
          <AppText variant="bodyMedium" numberOfLines={1}>{p ? p.name : 'Genel (proje yok)'}</AppText>
          <AppText variant="small" color={colors.textMuted} numberOfLines={1}>
            {p ? p.description || 'Açıklama yok' : 'Tüm standartlarda eşit ağırlıkla ara'}
          </AppText>
        </View>
        {active ? <Feather name="check-circle" size={20} color={colors.primary} /> : null}
      </Pressable>
    );
  };

  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose}>
      <Pressable style={[styles.backdrop, { backgroundColor: colors.overlay }]} onPress={onClose}>
        <Pressable
          onPress={() => {}}
          style={[styles.sheet, { backgroundColor: colors.surface, paddingBottom: insets.bottom + 16 }]}
        >
          <View style={[styles.grabber, { backgroundColor: colors.border }]} />
          <AppText variant="title">Proje bağlamı</AppText>
          <AppText variant="small" color={colors.textMuted}>
            Seçtiğin projenin alanlarıyla eşleşen standartlar aramada öne çıkar.
          </AppText>
          <ScrollView style={{ maxHeight: 360 }} contentContainerStyle={{ gap: 4, paddingVertical: 8 }}>
            <Row p={null} />
            {projects.isLoading ? <Loading /> : projects.data?.map((p) => <Row key={p.id} p={p} />)}
          </ScrollView>
          <Button
            title="Yeni proje oluştur"
            icon="plus"
            variant="secondary"
            size="md"
            onPress={() => {
              onClose();
              router.push('/project/edit');
            }}
          />
        </Pressable>
      </Pressable>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: { flex: 1, justifyContent: 'flex-end' },
  sheet: { borderTopLeftRadius: radius.xl, borderTopRightRadius: radius.xl, padding: 20, gap: 10 },
  grabber: { width: 40, height: 4, borderRadius: 2, alignSelf: 'center', marginBottom: 6 },
  row: { flexDirection: 'row', alignItems: 'center', gap: 12, padding: 10, borderRadius: radius.md },
  icon: { width: 38, height: 38, borderRadius: 12, alignItems: 'center', justifyContent: 'center' },
});
