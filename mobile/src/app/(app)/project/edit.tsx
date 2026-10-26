import { useQuery, useQueryClient } from '@tanstack/react-query';
import { router, useLocalSearchParams } from 'expo-router';
import { useEffect, useState } from 'react';
import { KeyboardAvoidingView, Platform, Pressable, ScrollView, StyleSheet, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { AppHeader } from '../../../components/brand';
import { AppText, Button, ErrorBox, Icon, Segmented, TextField, type IconName } from '../../../components/ui';
import { endpoints } from '../../../lib/api';
import type { ProjectInput } from '../../../lib/types';
import { radius, space, useTheme } from '../../../theme';

type Cat = ProjectInput['category'];

const DOMAIN_ICONS: Record<string, IconName> = {
  software: 'code', hardware: 'cpu', systems: 'git-branch', safety: 'shield', emc: 'activity',
  environmental: 'thermometer', maintenance: 'tool', sms: 'bar-chart-2', airworthiness: 'navigation',
};

export default function ProjectEditScreen() {
  const { id } = useLocalSearchParams<{ id?: string }>();
  const editId = id ? Number(id) : null;
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const qc = useQueryClient();
  const domains = useQuery({ queryKey: ['domains'], queryFn: endpoints.domains, staleTime: Infinity });
  const existing = useQuery({ queryKey: ['project', editId], queryFn: () => endpoints.project(editId!), enabled: !!editId });

  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [category, setCategory] = useState<Cat>('civil');
  const [selected, setSelected] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (existing.data) {
      setName(existing.data.name);
      setDescription(existing.data.description);
      setCategory(existing.data.category);
      setSelected(existing.data.domains);
    }
  }, [existing.data]);

  const toggle = (k: string) => setSelected((s) => (s.includes(k) ? s.filter((x) => x !== k) : [...s, k]));
  const valid = name.trim().length >= 2;

  const submit = async () => {
    if (!valid || saving) return;
    setSaving(true);
    setError(null);
    const body = { name: name.trim(), description: description.trim(), category, domains: selected };
    try {
      const p = editId ? await endpoints.updateProject(editId, body) : await endpoints.createProject(body);
      await qc.invalidateQueries({ queryKey: ['projects'] });
      await qc.invalidateQueries({ queryKey: ['project', p.id] });
      await qc.invalidateQueries({ queryKey: ['recommendations', p.id] });
      if (editId) router.back();
      else router.replace(`/project/${p.id}`);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <View style={{ flex: 1, backgroundColor: colors.surface }}>
      <AppHeader title={editId ? 'Projeyi düzenle' : 'Yeni proje'} />
      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
        <ScrollView contentContainerStyle={{ padding: space.xl, gap: space.lg, paddingBottom: insets.bottom + 32 }} keyboardShouldPersistTaps="handled">
          <TextField label="Proje adı" value={name} onChangeText={setName} placeholder="ör. İHA uçuş kontrol yazılımı" maxLength={120} />
          <TextField
            label="Kısa açıklama"
            value={description}
            onChangeText={setDescription}
            placeholder="Ne geliştiriyorsun? Hangi sistem, hangi aşama? Öneriler bu metne göre yapılır."
            multiline
            maxLength={2000}
            style={{ minHeight: 96, textAlignVertical: 'top' }}
          />
          <View style={{ gap: 8 }}>
            <AppText variant="label">Kapsam</AppText>
            <Segmented<Cat> value={category} onChange={setCategory}
              options={[{ value: 'civil', label: 'Sivil' }, { value: 'defense', label: 'Savunma' }, { value: 'both', label: 'İkisi de' }]} />
          </View>
          <View style={{ gap: 8 }}>
            <AppText variant="label">Çalışma alanları</AppText>
            {domains.data?.map((d) => {
              const on = selected.includes(d.key);
              return (
                <Pressable key={d.key} onPress={() => toggle(d.key)} accessibilityRole="checkbox" accessibilityState={{ checked: on }}
                  style={[styles.domain, { borderColor: on ? colors.primary : colors.border, backgroundColor: on ? colors.primarySoft : colors.surface }]}>
                  <View style={[styles.icon, { backgroundColor: on ? colors.primary : colors.surfaceAlt }]}>
                    <Icon name={DOMAIN_ICONS[d.key] ?? 'circle'} size={16} color={on ? '#fff' : colors.textMuted} />
                  </View>
                  <View style={{ flex: 1 }}>
                    <AppText variant="label">{d.label}</AppText>
                    <AppText variant="caption" color={colors.textMuted} numberOfLines={1}>{d.hint}</AppText>
                  </View>
                  <Icon name={on ? 'check-square' : 'square'} size={18} color={on ? colors.primary : colors.textSubtle} />
                </Pressable>
              );
            })}
          </View>
          {error ? <ErrorBox message={error} /> : null}
          <Button title={editId ? 'Değişiklikleri kaydet' : 'Projeyi oluştur'} onPress={submit} loading={saving} disabled={!valid} />
        </ScrollView>
      </KeyboardAvoidingView>
    </View>
  );
}

const styles = StyleSheet.create({
  domain: { flexDirection: 'row', alignItems: 'center', gap: 12, padding: 12, borderRadius: radius.md, borderWidth: 1.5 },
  icon: { width: 34, height: 34, borderRadius: 10, alignItems: 'center', justifyContent: 'center' },
});
