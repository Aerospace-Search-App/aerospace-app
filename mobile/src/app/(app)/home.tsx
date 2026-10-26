import { useQueryClient } from '@tanstack/react-query';
import { useLocalSearchParams } from 'expo-router';
import { useEffect, useState } from 'react';
import { View } from 'react-native';

import { AppHeader } from '../../components/brand';
import { ChatView } from '../../components/ChatView';
import { displayName, ProfileDrawer } from '../../components/overlays';
import { IconSquare, Star } from '../../components/ui';
import { endpoints } from '../../lib/api';
import { useAuth } from '../../lib/auth';
import { useTheme } from '../../theme';

/** M/03 — Sohbet (boş) ve M/04 — Sohbet (aktif) */
export default function HomeScreen() {
  const { colors } = useTheme();
  const { user } = useAuth();
  const qc = useQueryClient();
  const params = useLocalSearchParams<{ project?: string; t?: string }>();
  const [session, setSession] = useState(0);
  const [conv, setConv] = useState<{ id: number; title: string; starred?: boolean } | null>(null);
  const [drawer, setDrawer] = useState(false);
  const projectId = params.project ? Number(params.project) : null;

  useEffect(() => {
    if (params.t) newChat();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params.t]);

  function newChat() {
    setSession((s) => s + 1);
    setConv(null);
  }

  const toggleStar = async () => {
    if (!conv) return;
    const next = !conv.starred;
    setConv({ ...conv, starred: next });
    try {
      await endpoints.starConversation(conv.id, next);
      void qc.invalidateQueries({ queryKey: ['conversations'] });
    } catch {
      setConv((c) => (c ? { ...c, starred: !next } : c));
    }
  };

  return (
    <View style={{ flex: 1, backgroundColor: colors.bg }}>
      <AppHeader
        variant="home"
        title={conv?.title ?? 'AeroStandart'}
        avatarName={displayName(user)}
        onAvatar={() => setDrawer(true)}
        right={
          <View style={{ flexDirection: 'row', gap: 6 }}>
            {conv ? (
              <IconSquare
                icon="star"
              node={<Star filled={!!conv?.starred} size={18} color={conv?.starred ? colors.primary : colors.text} />}
                label={conv.starred ? 'Sohbet kaydını kaldır' : 'Sohbeti kaydet'}
                color={conv.starred ? colors.primary : colors.text}
                bg={conv.starred ? colors.primarySoft : undefined}
                onPress={toggleStar}
              />
            ) : null}
            <IconSquare icon="plus" label="Yeni sohbet" onPress={newChat} />
          </View>
        }
      />
      <ChatView key={session} initialProjectId={projectId} onConversation={(c) => setConv((p) => ({ ...c, starred: c.starred ?? p?.starred }))} />
      <ProfileDrawer visible={drawer} onClose={() => setDrawer(false)} />
    </View>
  );
}
