import Feather from '@expo/vector-icons/Feather';
import { useQuery } from '@tanstack/react-query';
import Constants from 'expo-constants';
import { router } from 'expo-router';
import { useEffect, useRef, useState } from 'react';
import { Animated, Dimensions, Modal, Pressable, ScrollView, StyleSheet, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { endpoints } from '../lib/api';
import { useAuth } from '../lib/auth';
import type { Citation } from '../lib/types';
import { useSaveToggle } from '../lib/useSave';
import { radius, space, useTheme, type ThemePref } from '../theme';
import { AppText, Avatar, Button, Eyebrow, InfoNote, ListRow, SectionLabel, Sheet, Tag } from './ui';

export const THEME_LABEL: Record<ThemePref, string> = { system: 'Sistem', light: 'Açık', dark: 'Koyu' };

export function displayName(u: { full_name?: string | null; username?: string | null; email: string } | null) {
  if (!u) return '';
  return u.full_name?.trim() || u.username || u.email.split('@')[0];
}

// ---------------------------------------------------------------------------
// O/01 — Profil çekmecesi
// ---------------------------------------------------------------------------
export function ProfileDrawer({ visible, onClose }: { visible: boolean; onClose: () => void }) {
  const { colors, pref } = useTheme();
  const { user, signOut } = useAuth();
  const insets = useSafeAreaInsets();
  const width = Math.min(Dimensions.get('window').width * 0.82, 360);
  const x = useRef(new Animated.Value(-width)).current;
  const fade = useRef(new Animated.Value(0)).current;
  const [mounted, setMounted] = useState(visible);
  const [themeOpen, setThemeOpen] = useState(false);
  const [aboutOpen, setAboutOpen] = useState(false);

  useEffect(() => {
    if (visible) {
      setMounted(true);
      Animated.parallel([
        Animated.timing(x, { toValue: 0, duration: 240, useNativeDriver: true }),
        Animated.timing(fade, { toValue: 1, duration: 240, useNativeDriver: true }),
      ]).start();
    } else if (mounted) {
      Animated.parallel([
        Animated.timing(x, { toValue: -width, duration: 200, useNativeDriver: true }),
        Animated.timing(fade, { toValue: 0, duration: 200, useNativeDriver: true }),
      ]).start(() => setMounted(false));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [visible]);

  const go = (path: Parameters<typeof router.push>[0]) => {
    onClose();
    setTimeout(() => router.push(path), 180);
  };

  return (
    <>
      <Modal visible={mounted} transparent animationType="none" onRequestClose={onClose} statusBarTranslucent>
        <Animated.View style={[StyleSheet.absoluteFill, { backgroundColor: colors.overlay, opacity: fade }]}>
          <Pressable style={StyleSheet.absoluteFill} onPress={onClose} accessibilityLabel="Menüyü kapat" />
        </Animated.View>
        <Animated.View
          style={[
            styles.drawer,
            { width, backgroundColor: colors.surface, paddingTop: insets.top + 20, paddingBottom: insets.bottom + 20, transform: [{ translateX: x }] },
          ]}
        >
          <View style={[styles.userCard, { backgroundColor: colors.primarySoft }]}>
            <Avatar name={displayName(user)} size={50} solid />
            <View style={{ flex: 1 }}>
              <AppText variant="heading" numberOfLines={1}>{displayName(user)}</AppText>
              <AppText variant="caption" color={colors.textMuted} numberOfLines={1}>{user?.email}</AppText>
            </View>
          </View>
          <SectionLabel title="Hesap ve tercihler" style={{ marginTop: space.lg, marginBottom: 6 }} />
          <ScrollView contentContainerStyle={{ gap: 2 }}>
            <ListRow icon="user" label="Kullanıcı adını değiştir" onPress={() => go('/profile')} />
            <ListRow icon="message-square" label="Sohbetler" onPress={() => go('/history')} />
            <ListRow icon="star" label="Kaydedilenler" onPress={() => go('/saved')} />
            <ListRow icon="briefcase" label="Projelerim" onPress={() => go('/projects')} />
            <ListRow icon="book-open" label="Standart kütüphanesi" onPress={() => go('/library')} />
            <ListRow icon="moon" label="Tema" value={THEME_LABEL[pref]} chevron={false} onPress={() => setThemeOpen(true)} />
            <ListRow icon="info" label="Hakkında" onPress={() => setAboutOpen(true)} />
          </ScrollView>
          <Button
            title="Çıkış yap"
            variant="soft"
            onPress={() => {
              onClose();
              void signOut();
            }}
          />
        </Animated.View>
        <ThemeSheet visible={themeOpen} onClose={() => setThemeOpen(false)} />
        <AboutSheet visible={aboutOpen} onClose={() => setAboutOpen(false)} />
      </Modal>
    </>
  );
}

// ---------------------------------------------------------------------------
// O/02 — Tema seçimi
// ---------------------------------------------------------------------------
const THEME_OPTIONS: { value: ThemePref; title: string; sub: string; icon: React.ComponentProps<typeof Feather>['name'] }[] = [
  { value: 'system', title: 'Sistem ayarını kullan', sub: 'Cihaz temasını takip eder', icon: 'smartphone' },
  { value: 'light', title: 'Açık', sub: 'Aydınlık çalışma alanı', icon: 'sun' },
  { value: 'dark', title: 'Koyu', sub: 'Düşük ışık için optimize edilmiş', icon: 'moon' },
];

export function ThemeSheet({ visible, onClose }: { visible: boolean; onClose: () => void }) {
  const { colors, pref, setPref } = useTheme();
  return (
    <Sheet visible={visible} onClose={onClose} title="Tema" subtitle="Uygulama görünümünü tercihlerinize göre seçin.">
      {THEME_OPTIONS.map((o) => {
        const on = pref === o.value;
        return (
          <Pressable
            key={o.value}
            onPress={() => setPref(o.value)}
            accessibilityRole="radio"
            accessibilityState={{ checked: on }}
            style={[styles.option, { borderColor: on ? colors.primary : colors.border, backgroundColor: on ? colors.primarySoft : colors.surface }]}
          >
            <View style={[styles.optionIcon, { backgroundColor: on ? colors.primary : colors.surfaceAlt }]}>
              <Feather name={o.icon} size={17} color={on ? '#fff' : colors.textMuted} />
            </View>
            <View style={{ flex: 1 }}>
              <AppText variant="label">{o.title}</AppText>
              <AppText variant="caption" color={colors.textMuted}>{o.sub}</AppText>
            </View>
            <View style={[styles.radio, { borderColor: on ? colors.primary : colors.textSubtle }]}>
              {on ? <View style={[styles.radioDot, { backgroundColor: colors.primary }]} /> : null}
            </View>
          </Pressable>
        );
      })}
    </Sheet>
  );
}

export function AboutSheet({ visible, onClose }: { visible: boolean; onClose: () => void }) {
  const { colors } = useTheme();
  const health = useQuery({ queryKey: ['health'], queryFn: endpoints.health, enabled: visible, retry: 0 });
  return (
    <Sheet visible={visible} onClose={onClose} title="Hakkında" showClose>
      <AppText color={colors.textMuted}>
        AeroStandart AI, sivil havacılık ve savunma standartlarında madde bazlı, kaynaklı cevaplar üreten RAG tabanlı bir asistandır.
      </AppText>
      <View style={[styles.infoBox, { backgroundColor: colors.bg }]}>
        <AppText variant="small">Sürüm: {Constants.expoConfig?.version ?? '1.0.0'}</AppText>
        <AppText variant="small">Yüklü standart: {health.data?.documents ?? '—'}</AppText>
        <AppText variant="small">Arama: {health.data ? (health.data.llm_enabled ? 'Hibrit (anlamsal + tam metin)' : 'Tam metin') : '—'}</AppText>
      </View>
      <InfoNote tone="warning">Operasyonel kararlar için güncel resmî metni doğrulayın.</InfoNote>
    </Sheet>
  );
}

// ---------------------------------------------------------------------------
// O/03 — Kaynak detayı
// ---------------------------------------------------------------------------
export function SourceSheet({ citation, onClose }: { citation: Citation | null; onClose: () => void }) {
  const { colors } = useTheme();
  const visible = !!citation;
  const detail = useQuery({
    queryKey: ['source', citation?.chunk_id],
    queryFn: () => endpoints.source(citation!.chunk_id),
    enabled: visible,
  });
  const save = useSaveToggle(citation?.document_id ?? 0, citation?.chunk_id ?? null, detail.data?.is_saved ?? false);
  if (!citation) return <Sheet visible={false} onClose={onClose} title="">{null}</Sheet>;

  const excerpt = detail.data?.chunk.content ?? citation.snippet;
  const short = excerpt.length > 520 ? `${excerpt.slice(0, 520).trim()}…` : excerpt;
  const version = detail.data?.document.version || citation.version;

  return (
    <Sheet visible={visible} onClose={onClose} title="Kaynak detayı" showClose>
      <Tag label={[citation.issuer, citation.code].filter(Boolean).join(' • ')} />
      <AppText variant="heading">{citation.doc_title}</AppText>
      <View style={[styles.infoBox, { backgroundColor: colors.bg }]}>
        <AppText variant="label">
          {citation.clause_ref ? `Madde: ${citation.clause_ref}${citation.heading ? ` — ${citation.heading}` : ''}` : citation.heading || 'Madde'}
        </AppText>
        <AppText variant="small" color={colors.textMuted}>Sürüm: {version || '—'}</AppText>
        <AppText variant="small" color={colors.textMuted}>Sayfa: {citation.page_start}</AppText>
      </View>
      <View style={[styles.excerpt, { backgroundColor: colors.primarySoft }]}>
        <Eyebrow>İlgili bölüm</Eyebrow>
        <AppText variant="small" selectable>{short}</AppText>
      </View>
      <AppText variant="caption" color={colors.textSubtle}>
        Sürüm ve yürürlük bilgisi operasyonel kullanımdan önce resmi kaynaktan doğrulanmalıdır.
      </AppText>
      <Button
        title="Belgede aç"
        onPress={() => {
          onClose();
          router.push(`/source/${citation.chunk_id}`);
        }}
      />
      <Button
        title={save.saved ? 'Kaydedildi' : 'Bu kaynağı kaydet'}
        icon="star"
        variant="secondary"
        onPress={save.busy ? undefined : save.toggle}
      />
    </Sheet>
  );
}

const styles = StyleSheet.create({
  drawer: { position: 'absolute', top: 0, bottom: 0, left: 0, paddingHorizontal: 18, borderTopRightRadius: 24, borderBottomRightRadius: 24, gap: 6 },
  userCard: { flexDirection: 'row', alignItems: 'center', gap: 14, padding: 16, borderRadius: radius.lg },
  option: { flexDirection: 'row', alignItems: 'center', gap: 12, padding: 14, borderRadius: radius.md, borderWidth: 1.5 },
  optionIcon: { width: 38, height: 38, borderRadius: 10, alignItems: 'center', justifyContent: 'center' },
  radio: { width: 18, height: 18, borderRadius: 9, borderWidth: 1.5, alignItems: 'center', justifyContent: 'center' },
  radioDot: { width: 10, height: 10, borderRadius: 5 },
  infoBox: { borderRadius: radius.md, padding: 14, gap: 6 },
  excerpt: { borderRadius: radius.md, padding: 14, gap: 8 },
});

