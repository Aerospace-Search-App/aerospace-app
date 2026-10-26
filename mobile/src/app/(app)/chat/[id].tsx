import { useQueryClient } from '@tanstack/react-query';
import { router, useLocalSearchParams } from 'expo-router';
import { useState } from 'react';
import { View } from 'react-native';

import { AppHeader } from '../../../components/brand';
import { ChatView } from '../../../components/ChatView';
import { IconSquare, Star } from '../../../components/ui';
import { endpoints } from '../../../lib/api';
import { useTheme } from '../../../theme';

export default function ConversationScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { colors } = useTheme();
  const qc = useQueryClient();
  const [conv, setConv] = useState<{ id: number; title: string; starred?: boolean } | null>(null);

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
        title={conv?.title ?? 'Sohbet'}
        right={
          <>
            <IconSquare
              icon="star"
              node={<Star filled={!!conv?.starred} size={18} color={conv?.starred ? colors.primary : colors.text} />}
              label={conv?.starred ? 'Sohbet kaydını kaldır' : 'Sohbeti kaydet'}
              color={conv?.starred ? colors.primary : colors.text}
              bg={conv?.starred ? colors.primarySoft : undefined}
              onPress={toggleStar}
            />
            <IconSquare icon="plus" label="Yeni sohbet" onPress={() => router.dismissTo('/home')} />
          </>
        }
      />
      <ChatView conversationId={Number(id)} onConversation={(c) => setConv((p) => ({ ...c, starred: c.starred ?? p?.starred }))} />
    </View>
  );
}
