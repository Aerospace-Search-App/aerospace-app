import Feather from '@expo/vector-icons/Feather';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import * as Clipboard from 'expo-clipboard';
import * as Haptics from 'expo-haptics';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { FlatList, Platform, Pressable, ScrollView, StyleSheet, TextInput, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { endpoints } from '../lib/api';
import type { Citation, Message, Project } from '../lib/types';
import { useKeyboardInset } from '../lib/useKeyboardInset';
import { fonts, radius, space, type, useTheme } from '../theme';
import { AnswerText } from './AnswerText';
import { SourceSheet } from './overlays';
import { ProjectPicker } from './ProjectPicker';
import { AppText, Card, Chip, ErrorBox, Eyebrow, IconTile, InfoNote, Loading, Star, Tag, TypingDots } from './ui';

const EXAMPLES = [
  { title: 'Yazılım güvence seviyeleri', sub: 'FAA • AC 20-115D', q: 'DO-178C yazılım seviyeleri (Level A-E) nasıl belirlenir ve AC 20-115D ne öngörür?' },
  { title: 'Tehlike şiddet kategorileri', sub: 'DoD • MIL-STD-882E', q: 'MIL-STD-882E\'ye göre tehlike şiddet ve olasılık kategorileri nelerdir?' },
  { title: 'Bakım kuruluşu personel şartları', sub: 'SHGM • SHT-145', q: 'SHT-145\'e göre onaylı bakım kuruluşunda sorumlu müdür ve sertifikalandırma personeli şartları nelerdir?' },
  { title: 'EMI emisyon testleri', sub: 'DoD • MIL-STD-461G', q: 'MIL-STD-461G RE102 ışınım emisyonu testi neyi ölçer ve hangi limitler uygulanır?' },
];

let tempId = -1;

function dayLabel(iso: string) {
  const d = new Date(iso);
  const today = new Date();
  const y = new Date();
  y.setDate(today.getDate() - 1);
  const time = d.toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit' });
  const same = (a: Date, b: Date) => a.toDateString() === b.toDateString();
  const day = same(d, today) ? 'BUGÜN' : same(d, y) ? 'DÜN' : d.toLocaleDateString('tr-TR', { day: 'numeric', month: 'long' }).toLocaleUpperCase('tr-TR');
  return `${day} • ${time}`;
}

export interface ChatViewHandle {
  conversationId: number | null;
}

export function ChatView({
  conversationId: initialId,
  initialProjectId,
  onConversation,
}: {
  conversationId?: number | null;
  initialProjectId?: number | null;
  onConversation?: (c: { id: number; title: string; starred?: boolean }) => void;
}) {
  const { colors } = useTheme();
  const qc = useQueryClient();
  const [conversationId, setConversationId] = useState<number | null>(initialId ?? null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [focused, setFocused] = useState(false);
  const [sending, setSending] = useState(false);
  const [issuer, setIssuer] = useState<string | null>(null);
  const [project, setProject] = useState<Project | null>(null);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [sheet, setSheet] = useState<Citation | null>(null);
  const listRef = useRef<FlatList<Message>>(null);
  const lastQuestion = useRef('');
  const { ref: rootRef, inset } = useKeyboardInset();
  const safe = useSafeAreaInsets();

  const existing = useQuery({ queryKey: ['conversation', initialId], queryFn: () => endpoints.conversation(initialId!), enabled: !!initialId });
  const issuers = useQuery({ queryKey: ['issuers'], queryFn: endpoints.issuers, staleTime: 60_000 });
  const projects = useQuery({ queryKey: ['projects'], queryFn: endpoints.projects });

  useEffect(() => {
    if (existing.data) {
      setMessages(existing.data.messages);
      onConversation?.({ id: existing.data.id, title: existing.data.title, starred: existing.data.starred });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [existing.data]);

  useEffect(() => {
    const pid = existing.data?.project_id ?? initialProjectId;
    if (pid && projects.data && !project) setProject(projects.data.find((p) => p.id === pid) ?? null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projects.data, existing.data, initialProjectId]);

  const stickToBottom = useRef(true);
  useEffect(() => {
    stickToBottom.current = true;
    if (messages.length) requestAnimationFrame(() => listRef.current?.scrollToEnd({ animated: true }));
  }, [messages.length, inset]);

  const send = useCallback(
    async (text?: string) => {
      const q = (text ?? input).trim();
      if (!q || sending) return;
      lastQuestion.current = q;
      setInput('');
      setSending(true);
      void Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light).catch(() => {});
      const now = new Date().toISOString();
      const uid = tempId--;
      const aid = tempId--;
      setMessages((m) => [
        ...m.filter((x) => !x.failed),
        { id: uid, role: 'user', content: q, citations: [], meta: {}, saved: false, created_at: now },
        { id: aid, role: 'assistant', content: '', citations: [], meta: {}, saved: false, created_at: now, pending: true },
      ]);
      try {
        const r = await endpoints.chat(q, { conversation_id: conversationId, project_id: project?.id ?? null, issuer });
        setConversationId(r.conversation_id);
        onConversation?.({ id: r.conversation_id, title: r.title });
        setMessages((m) => m.map((x) => (x.id === uid ? r.user_message : x.id === aid ? r.answer : x)));
        void qc.invalidateQueries({ queryKey: ['conversations'] });
        void qc.invalidateQueries({ queryKey: ['projects'] });
      } catch (e) {
        setMessages((m) => m.filter((x) => x.id !== uid).map((x) => (x.id === aid ? { ...x, pending: false, failed: true, content: (e as Error).message } : x)));
        setInput(q);
      } finally {
        setSending(false);
      }
    },
    [input, sending, conversationId, project, issuer, qc, onConversation],
  );

  const toggleSaved = async (m: Message) => {
    const next = !m.saved;
    setMessages((all) => all.map((x) => (x.id === m.id ? { ...x, saved: next } : x)));
    void Haptics.selectionAsync().catch(() => {});
    try {
      await endpoints.saveAnswer(m.id, next);
      void qc.invalidateQueries({ queryKey: ['saved-answers'] });
    } catch {
      setMessages((all) => all.map((x) => (x.id === m.id ? { ...x, saved: !next } : x)));
    }
  };

  const issuerList = issuers.data?.map((i) => i.issuer) ?? [];
  const lastAssistant = [...messages].reverse().find((m) => m.role === 'assistant' && !m.pending && !m.failed);

  const empty = (
    <View style={{ gap: space.lg }}>
      <View style={[styles.hero, { backgroundColor: colors.hero }]}>
        <View pointerEvents="none" style={styles.rings}>
          {[150, 110, 70].map((s) => (
            <View key={s} style={{ position: 'absolute', width: s, height: s, borderRadius: s / 2, borderWidth: 1, borderColor: colors.primary, opacity: 0.12 }} />
          ))}
        </View>
        <Eyebrow>RAG destekli standart arama</Eyebrow>
        <AppText variant="display" style={{ fontSize: 26, lineHeight: 32 }}>Hangi standardı arıyorsun?</AppText>
        <AppText variant="small" color={colors.textMuted}>
          {issuerList.length ? `${issuerList.join(', ')} kaynaklarında madde bazlı arama yapın.` : 'Kaynak, madde ve sürüm bilgileriyle yanıt alın.'}
        </AppText>
      </View>
      {issuerList.length ? (
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 8 }}>
          <Chip label="Tümü" selected={!issuer} onPress={() => setIssuer(null)} />
          {issuerList.map((i) => (
            <Chip key={i} label={i} selected={issuer === i} onPress={() => setIssuer(issuer === i ? null : i)} />
          ))}
        </ScrollView>
      ) : null}
      <AppText variant="heading" style={{ marginTop: space.sm }}>Örnek sorular</AppText>
      <View style={{ gap: 10 }}>
        {EXAMPLES.map((e) => (
          <Card key={e.title} onPress={() => send(e.q)} style={styles.example}>
            <IconTile icon="arrow-up-right" size={38} />
            <View style={{ flex: 1, gap: 2 }}>
              <AppText variant="label">{e.title}</AppText>
              <AppText variant="caption" color={colors.textMuted}>{e.sub}</AppText>
            </View>
            <Feather name="chevron-right" size={18} color={colors.textSubtle} />
          </Card>
        ))}
      </View>
      <InfoNote>Belge, madde ve sürüm bilgileri görünür kalır.</InfoNote>
    </View>
  );

  const renderItem = ({ item, index }: { item: Message; index: number }) => {
    const prev = messages[index - 1];
    const showDate = item.role === 'user' && (!prev || new Date(item.created_at).toDateString() !== new Date(prev.created_at).toDateString() || index === 0);
    return (
      <View style={{ gap: space.md }}>
        {showDate ? (
          <AppText variant="caption" color={colors.textSubtle} style={{ textAlign: 'center', letterSpacing: 0.8 }}>
            {dayLabel(item.created_at)}
          </AppText>
        ) : null}
        {item.role === 'user' ? (
          <View style={[styles.userBubble, { backgroundColor: colors.primary }]}>
            <AppText color="#fff" selectable>{item.content}</AppText>
          </View>
        ) : (
          <AssistantMessage
            message={item}
            onCitation={setSheet}
            onRetry={() => send(lastQuestion.current)}
            onToggleSave={() => toggleSaved(item)}
            showDisclaimer={item.id === lastAssistant?.id}
          />
        )}
      </View>
    );
  };

  return (
    <View ref={rootRef} style={{ flex: 1, backgroundColor: colors.bg }}>
      {existing.isLoading ? (
        <Loading label="Sohbet yükleniyor…" />
      ) : existing.isError ? (
        <View style={{ padding: 16 }}>
          <ErrorBox message={(existing.error as Error).message} onRetry={() => existing.refetch()} />
        </View>
      ) : (
        <FlatList
          ref={listRef}
          data={messages}
          keyExtractor={(m) => String(m.id)}
          contentContainerStyle={styles.list}
          ListEmptyComponent={empty}
          keyboardShouldPersistTaps="handled"
          keyboardDismissMode="interactive"
          onContentSizeChange={(_w, h) => {
            // Yeni içerik geldiğinde (soru/cevap) en alta kay; kullanıcı yukarıdaysa zorlamaz
            if (messages.length && stickToBottom.current) listRef.current?.scrollToOffset({ offset: h, animated: true });
          }}
          onScrollEndDrag={(e) => {
            // Yalnızca kullanıcı sürüklediğinde: yukarı kaydırdıysa otomatik kaydırmayı bırak
            const { contentOffset, contentSize, layoutMeasurement } = e.nativeEvent;
            stickToBottom.current = contentSize.height - (contentOffset.y + layoutMeasurement.height) < 160;
          }}
          renderItem={renderItem}
        />
      )}

      <View style={[styles.composerBar, { backgroundColor: colors.surface, borderTopColor: colors.border, paddingBottom: 10 + (inset > 0 ? inset : safe.bottom) }]}>
        <View style={styles.contextRow}>
          <Pressable onPress={() => setPickerOpen(true)} style={[styles.ctx, { borderColor: project ? colors.primary : colors.border }]} accessibilityRole="button">
            <Feather name="briefcase" size={12} color={project ? colors.primary : colors.textMuted} />
            <AppText variant="caption" color={project ? colors.primary : colors.textMuted} numberOfLines={1} style={{ maxWidth: 170 }}>
              {project ? project.name : 'Proje: Genel'}
            </AppText>
            <Feather name="chevron-down" size={12} color={project ? colors.primary : colors.textMuted} />
          </Pressable>
          {issuer ? (
            <Pressable onPress={() => setIssuer(null)} style={[styles.ctx, { borderColor: colors.primary }]} accessibilityLabel="Kaynak filtresini kaldır">
              <Feather name="filter" size={12} color={colors.primary} />
              <AppText variant="caption" color={colors.primary}>{issuer}</AppText>
              <Feather name="x" size={12} color={colors.primary} />
            </Pressable>
          ) : null}
        </View>
        <View style={[styles.composer, { backgroundColor: colors.surface, borderColor: focused ? colors.primary : colors.border, borderWidth: focused ? 1.5 : 1 }]}>
          <TextInput
            value={input}
            onChangeText={setInput}
            onFocus={() => setFocused(true)}
            onBlur={() => setFocused(false)}
            placeholder={messages.length ? 'Takip sorusu sorun...' : 'Bir standart veya madde sorun...'}
            placeholderTextColor={colors.textSubtle}
            multiline
            maxLength={2000}
            style={[styles.input, { color: colors.text }]}
            onSubmitEditing={Platform.OS === 'web' ? () => send() : undefined}
            blurOnSubmit={Platform.OS === 'web'}
            accessibilityLabel="Mesaj"
          />
          <Pressable
            onPress={() => send()}
            disabled={!input.trim() || sending}
            accessibilityRole="button"
            accessibilityLabel="Gönder"
            style={({ pressed }) => [styles.send, { backgroundColor: input.trim() && !sending ? colors.primary : colors.disabled, opacity: pressed ? 0.8 : 1 }]}
          >
            <Feather name="arrow-up" size={18} color={input.trim() && !sending ? '#fff' : colors.onDisabled} />
          </Pressable>
        </View>
      </View>

      <ProjectPicker visible={pickerOpen} selectedId={project?.id ?? null} onSelect={setProject} onClose={() => setPickerOpen(false)} />
      <SourceSheet citation={sheet} onClose={() => setSheet(null)} />
    </View>
  );
}

function AssistantMessage({
  message,
  onCitation,
  onRetry,
  onToggleSave,
  showDisclaimer,
}: {
  message: Message;
  onCitation: (c: Citation) => void;
  onRetry: () => void;
  onToggleSave: () => void;
  showDisclaimer: boolean;
}) {
  const { colors } = useTheme();
  const [copied, setCopied] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const byN = useMemo(() => new Map(message.citations.map((c) => [c.n, c])), [message.citations]);

  if (message.pending) {
    return (
      <View style={[styles.assistant, { backgroundColor: colors.surface, borderColor: colors.border, borderLeftColor: colors.primary }]}>
        <Eyebrow>Aero AI • Standartlar taranıyor</Eyebrow>
        <TypingDots />
      </View>
    );
  }
  if (message.failed) return <ErrorBox message={message.content} onRetry={onRetry} />;

  const scanned = message.meta?.sources_scanned ?? message.citations.length;
  const visibleSources = expanded ? message.citations : message.citations.slice(0, 1);

  return (
    <View style={{ gap: space.md }}>
      <View style={[styles.assistant, { backgroundColor: colors.surface, borderColor: colors.border, borderLeftColor: colors.primary }]}>
        <Eyebrow>{`Aero AI • ${scanned} kaynak tarandı`}</Eyebrow>
        <AnswerText
          text={message.content}
          validCitations={new Set(byN.keys())}
          onCitation={(n) => {
            const c = byN.get(n);
            if (c) onCitation(c);
          }}
        />
        {message.citations.length ? (
          <View style={styles.tags}>
            {message.citations.map((c) => (
              <Tag key={c.n} label={c.clause_ref ? `${c.code} • ${c.clause_ref}` : `${c.code} • s.${c.page_start}`} onPress={() => onCitation(c)} />
            ))}
          </View>
        ) : null}
        <View style={styles.actions}>
          <Action icon="star" label={message.saved ? 'Kaydedildi' : 'Kaydet'} active={message.saved} onPress={onToggleSave} />
          <Action
            icon={copied ? 'check' : 'copy'}
            label={copied ? 'Kopyalandı' : 'Kopyala'}
            onPress={async () => {
              await Clipboard.setStringAsync(message.content.replace(/\*\*/g, ''));
              setCopied(true);
              setTimeout(() => setCopied(false), 1500);
            }}
          />
          {message.citations.length > 1 ? (
            <Action
              icon={expanded ? 'chevron-up' : 'layers'}
              label={expanded ? 'Kaynakları gizle' : `Kaynakları göster (${message.citations.length})`}
              onPress={() => setExpanded((e) => !e)}
            />
          ) : null}
        </View>
      </View>
      {visibleSources.map((c) => (
        <Card key={c.n} onPress={() => onCitation(c)} style={{ gap: 6 }}>
          <View style={{ flexDirection: 'row', alignItems: 'center' }}>
            <Eyebrow style={{ flex: 1 }}>{[c.issuer, c.code].filter(Boolean).join(' • ')}</Eyebrow>
            {c.version ? <AppText variant="eyebrow" color={colors.textSubtle}>{`REV. ${c.version}`.toUpperCase()}</AppText> : null}
          </View>
          <AppText variant="label">
            {[c.clause_ref, c.heading].filter(Boolean).join(' — ') || `Sayfa ${c.page_start}`}
          </AppText>
          <AppText variant="caption" color={colors.textMuted} numberOfLines={3}>{c.snippet}</AppText>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 4 }}>
            <AppText variant="label" color={colors.primary}>Kaynak detayını aç</AppText>
            <Feather name="arrow-right" size={14} color={colors.primary} />
          </View>
        </Card>
      ))}
      {showDisclaimer ? <InfoNote tone="warning">Operasyonel kararlar için güncel resmî metni doğrulayın.</InfoNote> : null}
    </View>
  );
}

function Action({ icon, label, onPress, active }: { icon: React.ComponentProps<typeof Feather>['name']; label: string; onPress: () => void; active?: boolean }) {
  const { colors } = useTheme();
  const color = active ? colors.primary : colors.textMuted;
  return (
    <Pressable onPress={onPress} hitSlop={6} style={({ pressed }) => [styles.action, { opacity: pressed ? 0.6 : 1 }]} accessibilityRole="button">
      {icon === 'star' ? <Star filled={active} size={13} color={color} /> : <Feather name={icon} size={13} color={color} />}
      <AppText variant="caption" color={color} style={{ fontFamily: fonts.medium }}>{label}</AppText>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  list: { padding: space.lg, gap: space.lg, paddingBottom: space.xl, flexGrow: 1 },
  hero: { borderRadius: 18, padding: 20, gap: 8, overflow: 'hidden' },
  rings: { position: 'absolute', right: -40, top: -30, width: 150, height: 150, alignItems: 'center', justifyContent: 'center' },
  example: { flexDirection: 'row', alignItems: 'center', gap: 12, paddingVertical: 14 },
  userBubble: { alignSelf: 'flex-end', maxWidth: '82%', paddingHorizontal: 16, paddingVertical: 12, borderRadius: 16 },
  assistant: { borderRadius: 14, borderWidth: 1, borderLeftWidth: 3, padding: 14, gap: 10 },
  tags: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  actions: { flexDirection: 'row', flexWrap: 'wrap', gap: 14, marginTop: 2 },
  action: { flexDirection: 'row', alignItems: 'center', gap: 5 },
  composerBar: { paddingHorizontal: space.md, paddingTop: 8, borderTopWidth: StyleSheet.hairlineWidth, gap: 8 },
  contextRow: { flexDirection: 'row', gap: 8, flexWrap: 'wrap' },
  ctx: { flexDirection: 'row', alignItems: 'center', gap: 5, borderWidth: 1, borderRadius: radius.pill, paddingHorizontal: 10, height: 26 },
  composer: { flexDirection: 'row', alignItems: 'flex-end', gap: 8, borderRadius: radius.md, paddingLeft: 14, paddingRight: 6, paddingVertical: 6 },
  input: { flex: 1, ...type.body, maxHeight: 120, minHeight: 36, paddingTop: Platform.OS === 'ios' ? 8 : 6, paddingBottom: 6 },
  send: { width: 36, height: 36, borderRadius: 10, alignItems: 'center', justifyContent: 'center' },
});
