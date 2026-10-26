import { useQuery } from '@tanstack/react-query';
import { router } from 'expo-router';
import { useState, type ReactNode } from 'react';
import { Modal, Pressable, StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { api, endpoints } from '../lib/api';
import { fonts, radius, useTheme } from '../theme';
import { AppText, Avatar, Button, IconSquare, TextField } from './ui';

/** Figma logosu: kırmızı yuvarlatılmış kare içinde "A" ve altında nokta. */
export function LogoMark({ size = 64 }: { size?: number }) {
  const { colors } = useTheme();
  return (
    <View
      style={{
        width: size,
        height: size,
        borderRadius: size * 0.28,
        backgroundColor: colors.primary,
        alignItems: 'center',
        justifyContent: 'center',
      }}
      accessibilityLabel="AeroStandart logosu"
    >
      <Text style={{ fontFamily: fonts.semibold, fontSize: size * 0.52, color: '#fff', marginTop: -size * 0.08, lineHeight: size * 0.62 }}>A</Text>
      <View style={{ position: 'absolute', bottom: size * 0.2, width: size * 0.07, height: size * 0.07, borderRadius: size, backgroundColor: '#fff' }} />
    </View>
  );
}

export function BrandBlock() {
  const { colors } = useTheme();
  return (
    <View style={{ alignItems: 'center', gap: 10 }}>
      <LogoMark size={64} />
      <AppText variant="eyebrow" color={colors.primary} style={{ fontSize: 13, letterSpacing: 2 }}>AEROSTANDART AI</AppText>
      <AppText variant="small" color={colors.textMuted}>Standartlara güvenle erişin</AppText>
    </View>
  );
}

/** Uygulama başlık çubuğu. home: avatar + ortalı başlık + "+" · back: geri + başlık. */
export function AppHeader({
  title,
  variant = 'back',
  onAvatar,
  avatarName,
  right,
  onBack,
}: {
  title: string;
  variant?: 'home' | 'back';
  onAvatar?: () => void;
  avatarName?: string;
  right?: ReactNode;
  onBack?: () => void;
}) {
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  return (
    <View style={[styles.header, { paddingTop: insets.top + 8, backgroundColor: colors.surface, borderBottomColor: colors.border }]}>
      {variant === 'home' ? (
        <>
          <Pressable onPress={onAvatar} accessibilityRole="button" accessibilityLabel="Profil menüsü" hitSlop={6}>
            <Avatar name={avatarName ?? ''} size={38} />
          </Pressable>
          <AppText variant="heading" numberOfLines={1} style={{ flex: 1, textAlign: 'center', marginHorizontal: 8 }}>
            {title}
          </AppText>
          <View style={{ minWidth: 38, alignItems: 'flex-end' }}>{right}</View>
        </>
      ) : (
        <>
          <IconSquare icon="arrow-left" label="Geri" onPress={onBack ?? (() => (router.canGoBack() ? router.back() : router.replace('/')))} />
          <AppText variant="heading" numberOfLines={1} style={{ flex: 1, marginLeft: 6 }}>{title}</AppText>
          {right ? <View style={{ flexDirection: 'row', gap: 6 }}>{right}</View> : null}
        </>
      )}
    </View>
  );
}

/** Sunucu bağlantı durumu; dokununca adres değiştirilebilir (Expo Go'da sorun giderme). */
export function ServerStatus() {
  const { colors } = useTheme();
  const [open, setOpen] = useState(false);
  const health = useQuery({ queryKey: ['health', api.baseUrl], queryFn: endpoints.health, retry: 0, staleTime: 10_000 });
  const ok = health.isSuccess;
  const color = health.isLoading ? colors.textSubtle : ok ? colors.success : colors.danger;
  const label = health.isLoading
    ? 'Sunucu kontrol ediliyor…'
    : ok
      ? `Sunucuya bağlı · ${health.data.documents} standart`
      : 'Sunucuya ulaşılamıyor · adresi kontrol et';
  return (
    <>
      <Pressable onPress={() => setOpen(true)} accessibilityRole="button" style={[styles.pill, { borderColor: colors.border }]}>
        <View style={[styles.dot, { backgroundColor: color }]} />
        <AppText variant="caption" color={colors.textMuted} numberOfLines={1} style={{ flexShrink: 1 }}>{label}</AppText>
      </Pressable>
      <ServerDialog visible={open} onClose={() => setOpen(false)} onSaved={() => void health.refetch()} />
    </>
  );
}

export function ServerDialog({ visible, onClose, onSaved }: { visible: boolean; onClose: () => void; onSaved?: () => void }) {
  const { colors } = useTheme();
  const [url, setUrl] = useState(api.baseUrl);
  const [testing, setTesting] = useState(false);
  const [result, setResult] = useState<string | null>(null);

  const test = async (save: boolean) => {
    setTesting(true);
    setResult(null);
    const prev = api.baseUrl;
    await api.setServer(url);
    try {
      const h = await endpoints.health();
      setResult(`Bağlantı başarılı · ${h.documents} standart · Gemini ${h.llm_enabled ? 'açık' : 'kapalı'}`);
      if (save) {
        onSaved?.();
        onClose();
      } else await api.setServer(prev);
    } catch (e) {
      setResult((e as Error).message);
      await api.setServer(prev);
    } finally {
      setTesting(false);
    }
  };

  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={onClose} onShow={() => { setUrl(api.baseUrl); setResult(null); }}>
      <Pressable style={[styles.backdrop, { backgroundColor: colors.overlay }]} onPress={onClose}>
        <Pressable style={[styles.dialog, { backgroundColor: colors.surface }]} onPress={() => {}}>
          <AppText variant="heading">Sunucu adresi</AppText>
          <AppText variant="small" color={colors.textMuted}>
            Backend'in çalıştığı bilgisayarın yerel IP adresi ve 8000 portu. Telefon ve bilgisayar aynı Wi-Fi ağında olmalı.
          </AppText>
          <TextField value={url} onChangeText={setUrl} autoCapitalize="none" autoCorrect={false} keyboardType="url"
            placeholder="http://192.168.1.20:8000" icon="server" />
          {result ? <AppText variant="small" color={colors.textMuted}>{result}</AppText> : null}
          <View style={{ flexDirection: 'row', gap: 10 }}>
            <Button title="Test et" variant="secondary" size="md" style={{ flex: 1 }} onPress={() => test(false)} loading={testing} />
            <Button title="Kaydet" size="md" style={{ flex: 1 }} onPress={() => test(true)} disabled={testing} />
          </View>
          <Button title="Otomatik algılamaya dön" variant="ghost" size="sm"
            onPress={async () => { await api.setServer(null); setUrl(api.baseUrl); onSaved?.(); }} />
        </Pressable>
      </Pressable>
    </Modal>
  );
}

const styles = StyleSheet.create({
  header: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16, paddingBottom: 10, borderBottomWidth: StyleSheet.hairlineWidth, gap: 6 },
  pill: { flexDirection: 'row', alignItems: 'center', gap: 8, alignSelf: 'center', paddingHorizontal: 12, paddingVertical: 6, borderRadius: radius.pill, borderWidth: 1, maxWidth: '100%' },
  dot: { width: 7, height: 7, borderRadius: 4 },
  backdrop: { flex: 1, justifyContent: 'center', padding: 24 },
  dialog: { borderRadius: radius.xl, padding: 20, gap: 14 },
});
