import { Stack } from 'expo-router';

import { useTheme } from '../../theme';

export default function AppLayout() {
  const { colors } = useTheme();
  return (
    <Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: colors.bg } }}>
      <Stack.Screen name="home" />
      <Stack.Screen name="chat/[id]" />
      <Stack.Screen name="history" />
      <Stack.Screen name="saved" />
      <Stack.Screen name="profile" />
      <Stack.Screen name="library" />
      <Stack.Screen name="document/[id]" />
      <Stack.Screen name="source/[id]" />
      <Stack.Screen name="projects" />
      <Stack.Screen name="project/[id]" />
      <Stack.Screen name="project/edit" options={{ presentation: 'modal' }} />
    </Stack>
  );
}
