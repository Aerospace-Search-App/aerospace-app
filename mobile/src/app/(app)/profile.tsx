import { router } from 'expo-router';
import { useEffect, useState } from 'react';
import { KeyboardAvoidingView, Platform, ScrollView, StyleSheet, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { AppHeader, ServerDialog } from '../../components/brand';
import { displayName, THEME_LABEL, ThemeSheet } from '../../components/overlays';
import { AppText, Avatar, Button, ErrorBox, ListRow, SectionLabel, TextField } from '../../components/ui';
import { api, endpoints } from '../../lib/api';
import { useAuth } from '../../lib/auth';
import { radius, space, useTheme } from '../../theme';

const USERNAME_RE = /^[a-zA-Z0-9._-]{3,30}$/;

/** M/05 — Profil ve ayarlar */
export default function ProfileScreen() {
  const { colors, pref } = useTheme();
  const { user, updateUser, signOut } = useAuth();
  const insets = useSafeAreaInsets();
  const [username, setUsername] = useState(user?.username ?? '');
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [themeOpen, setThemeOpen] = useState(false);
  const [serverOpen, setServerOpen] = useState(false);

  useEffect(() => setUsername(user?.username ?? ''), [user?.username]);

  const invalid = username && !USERNAME_RE.test(username.trim()) ? '3-30 karakter; harf, rakam, nokta, alt çizgi.' : null;
  const changed = username.trim() !== (user?.username ?? '');

  const save = async () => {
    if (!changed || invalid || saving) return;
    setSaving(true);
    setMsg(null);
    try {
      const u = await endpoints.updateMe({ username: username.trim() });
      updateUser(u);
      setMsg({ ok: true, text: 'Kullanıcı adın güncellendi.' });
    } catch (e) {
      setMsg({ ok: false, text: (e as Error).message });
    } finally {
      setSaving(false);
    }
  };

  return (
    <View style={{ flex: 1, backgroundColor: colors.surface }}>
      <AppHeader title="Profil ve ayarlar" />
      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
        <ScrollView contentContainerStyle={{ padding: space.xl, gap: space.lg, paddingBottom: insets.bottom + 32 }} keyboardShouldPersistTaps="handled">
          <View style={[styles.userCard, { backgroundColor: colors.primarySoft }]}>
            <Avatar name={displayName(user)} size={56} solid />
            <View style={{ flex: 1 }}>
              <AppText variant="heading" numberOfLines={1} style={{ fontSize: 18 }}>{displayName(user)}</AppText>
              <AppText variant="small" color={colors.textMuted} numberOfLines={1}>{user?.email}</AppText>
            </View>
          </View>

          <SectionLabel title="Hesap" />
          <TextField label="Kullanıcı adı" value={username} onChangeText={(t) => { setUsername(t); setMsg(null); }} placeholder="ayse.kaya"
            autoCapitalize="none" autoCorrect={false} error={invalid} returnKeyType="done" onSubmitEditing={save} />
          {msg ? (
            msg.ok ? <AppText variant="small" color={colors.success}>{msg.text}</AppText> : <ErrorBox message={msg.text} />
          ) : null}
          <Button title="Değişiklikleri kaydet" onPress={save} loading={saving} disabled={!changed || !!invalid} />

          <SectionLabel title="Tercihler" style={{ marginTop: space.md }} />
          <View style={{ gap: 2 }}>
            <ListRow icon="moon" label="Tema" value={THEME_LABEL[pref]} onPress={() => setThemeOpen(true)} />
            <ListRow icon="message-square" label="Sohbetler" onPress={() => router.push('/history')} />
            <ListRow icon="star" label="Kaydedilenler" onPress={() => router.push('/saved')} />
            <ListRow icon="briefcase" label="Projelerim" onPress={() => router.push('/projects')} />
            <ListRow icon="book-open" label="Standart kütüphanesi" onPress={() => router.push('/library')} />
            <ListRow icon="server" label="Sunucu adresi" value={api.baseUrl.replace(/^https?:\/\//, '')} onPress={() => setServerOpen(true)} />
          </View>

          <Button title="Çıkış yap" variant="soft" onPress={() => void signOut()} style={{ marginTop: space.md }} />
        </ScrollView>
      </KeyboardAvoidingView>
      <ThemeSheet visible={themeOpen} onClose={() => setThemeOpen(false)} />
      <ServerDialog visible={serverOpen} onClose={() => setServerOpen(false)} />
    </View>
  );
}

const styles = StyleSheet.create({
  userCard: { flexDirection: 'row', alignItems: 'center', gap: 14, padding: 18, borderRadius: radius.lg },
});
