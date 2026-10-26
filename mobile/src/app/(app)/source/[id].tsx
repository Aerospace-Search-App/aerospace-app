import { useQuery } from '@tanstack/react-query';
import * as WebBrowser from 'expo-web-browser';
import { router, useLocalSearchParams } from 'expo-router';
import { useState } from 'react';
import { ActivityIndicator, Image, Pressable, ScrollView, StyleSheet, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { AppHeader } from '../../../components/brand';
import { AppText, Button, ErrorBox, Eyebrow, Icon, IconSquare, InfoNote, Loading, Star, Tag } from '../../../components/ui';
import { api, endpoints } from '../../../lib/api';
import { useSaveToggle } from '../../../lib/useSave';
import { radius, space, useTheme } from '../../../theme';

/** Kaynak madde — tam metin, vurgulu orijinal sayfa, PDF ve komşu maddeler. */
export default function SourceScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const chunkId = Number(id);
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const q = useQuery({ queryKey: ['source', chunkId], queryFn: () => endpoints.source(chunkId) });
  const save = useSaveToggle(q.data?.document.id ?? 0, chunkId, q.data?.is_saved ?? false);
  const [ratio, setRatio] = useState(0.77);
  const [img, setImg] = useState<'loading' | 'ok' | 'error'>('loading');

  const data = q.data;
  const title = data ? [data.document.code, data.chunk.clause_ref].filter(Boolean).join(' · ') : 'Kaynak';
  const go = (nid: number | null) => nid && router.replace(`/source/${nid}`);

  return (
    <View style={{ flex: 1, backgroundColor: colors.bg }}>
      <AppHeader
        title={title}
        right={data ? (
          <IconSquare icon="star" node={<Star filled={save.saved} size={18} color={save.saved ? colors.primary : colors.text} />}
            label={save.saved ? 'Maddeyi kayıtlılardan çıkar' : 'Maddeyi kaydet'} bg={save.saved ? colors.primarySoft : undefined}
            onPress={save.busy ? undefined : save.toggle} />
        ) : undefined}
      />
      {q.isLoading ? (
        <Loading label="Madde yükleniyor…" />
      ) : q.isError || !data ? (
        <View style={{ padding: 16 }}><ErrorBox message={(q.error as Error)?.message ?? 'Bulunamadı'} onRetry={() => q.refetch()} /></View>
      ) : (
        <ScrollView contentContainerStyle={{ padding: space.lg, gap: space.lg, paddingBottom: insets.bottom + 32 }}>
          <Pressable onPress={() => router.push(`/document/${data.document.id}`)} style={{ gap: 8 }}>
            <Tag label={[data.document.issuer, data.document.code].filter(Boolean).join(' • ')} />
            <AppText variant="heading">{data.document.title}</AppText>
          </Pressable>

          <View style={[styles.info, { backgroundColor: colors.surface, borderColor: colors.border }]}>
            <AppText variant="label">Madde: {data.chunk.clause_ref || '—'}{data.chunk.part > 1 ? ` (bölüm ${data.chunk.part})` : ''}</AppText>
            <AppText variant="small" color={colors.textMuted}>Sürüm: {data.document.version || '—'}</AppText>
            <AppText variant="small" color={colors.textMuted}>
              Sayfa: {data.chunk.page_start === data.chunk.page_end ? data.chunk.page_start : `${data.chunk.page_start}–${data.chunk.page_end}`}
            </AppText>
            {data.chunk.heading_path ? <AppText variant="caption" color={colors.textSubtle}>{data.chunk.heading_path}</AppText> : null}
          </View>

          <View style={[styles.excerpt, { backgroundColor: colors.primarySoft }]}>
            <Eyebrow>İlgili bölüm</Eyebrow>
            {data.chunk.heading ? <AppText variant="label">{data.chunk.heading}</AppText> : null}
            <AppText selectable style={{ lineHeight: 23 }}>{data.chunk.content}</AppText>
          </View>

          <View style={{ gap: 8 }}>
            <Eyebrow color={colors.textMuted}>{`Orijinal sayfa · ${data.chunk.page_start}`}</Eyebrow>
            <Pressable
              onPress={() => WebBrowser.openBrowserAsync(api.absolute(data.file_url))}
              style={[styles.page, { borderColor: colors.border, aspectRatio: ratio }]}
              accessibilityLabel="Sayfayı PDF'te aç"
            >
              <Image
                source={{ uri: api.absolute(data.page_image_url) }}
                style={StyleSheet.absoluteFill}
                resizeMode="contain"
                onLoad={(e) => {
                  const s = e.nativeEvent?.source;
                  if (s?.width && s?.height) setRatio(s.width / s.height);
                  setImg('ok');
                }}
                onError={() => setImg('error')}
              />
              {img === 'loading' ? <ActivityIndicator style={StyleSheet.absoluteFill} color={colors.primary} /> : null}
              {img === 'error' ? (
                <View style={[StyleSheet.absoluteFill, { alignItems: 'center', justifyContent: 'center', gap: 6 }]}>
                  <Icon name="image" size={26} color={colors.textSubtle} />
                  <AppText variant="small" color={colors.textMuted}>Sayfa görüntüsü yüklenemedi</AppText>
                </View>
              ) : null}
            </Pressable>
            <AppText variant="caption" color={colors.textSubtle}>Madde metni sayfada sarıyla vurgulanır.</AppText>
          </View>

          <InfoNote tone="warning">Sürüm ve yürürlük bilgisi operasyonel kullanımdan önce resmi kaynaktan doğrulanmalıdır.</InfoNote>
          <Button title="Belgede aç" icon="external-link" onPress={() => WebBrowser.openBrowserAsync(api.absolute(data.file_url))} />
          <Button title={save.saved ? 'Kaydedildi' : 'Bu kaynağı kaydet'} icon="star" variant="secondary" onPress={save.busy ? undefined : save.toggle} />
          <View style={{ flexDirection: 'row', gap: 10 }}>
            <Button title="Önceki" icon="chevron-left" variant="secondary" size="md" style={{ flex: 1 }} disabled={!data.prev_id} onPress={() => go(data.prev_id)} />
            <Button title="Sonraki" icon="chevron-right" variant="secondary" size="md" style={{ flex: 1 }} disabled={!data.next_id} onPress={() => go(data.next_id)} />
          </View>
        </ScrollView>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  info: { borderRadius: radius.md, borderWidth: 1, padding: 14, gap: 6 },
  excerpt: { borderRadius: radius.md, padding: 16, gap: 8 },
  page: { width: '100%', borderWidth: 1, borderRadius: radius.md, overflow: 'hidden', backgroundColor: '#fff' },
});
