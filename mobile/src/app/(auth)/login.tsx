import { Link } from 'expo-router';
import { useRef, useState } from 'react';
import { KeyboardAvoidingView, Platform, Pressable, ScrollView, StyleSheet, View, type TextInputInstance } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { BrandBlock, ServerStatus } from '../../components/brand';
import { AppText, Button, ErrorBox, InfoNote, Sheet, TextField } from '../../components/ui';
import { useAuth } from '../../lib/auth';
import { space, useTheme } from '../../theme';

export default function LoginScreen() {
  const { colors } = useTheme();
  const { signIn } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [forgot, setForgot] = useState(false);
  const passRef = useRef<TextInputInstance>(null);

  const looksEmail = email.includes('@');
  const emailError = email && looksEmail && !/^\S+@\S+\.\S+$/.test(email.trim()) ? 'Geçerli bir e-posta adresi girin.' : null;
  const canSubmit = email.trim().length >= 3 && !!password && !emailError;

  const submit = async () => {
    if (!canSubmit || loading) return;
    setLoading(true);
    setError(null);
    try {
      await signIn(email, password);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.surface }}>
      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
        <ScrollView contentContainerStyle={styles.scroll} keyboardShouldPersistTaps="handled">
          <View style={{ marginTop: space.xxl }}>
            <BrandBlock />
          </View>
          <View style={{ gap: 6, marginTop: space.lg }}>
            <AppText variant="display">Tekrar hoş geldiniz</AppText>
            <AppText color={colors.textMuted}>Havacılık standartlarında kaynaklı arama yapmak için giriş yapın.</AppText>
          </View>
          <TextField
            label="E-posta"
            value={email}
            onChangeText={setEmail}
            placeholder="ornek@havacilik.com"
            autoCapitalize="none"
            autoComplete="email"
            keyboardType="email-address"
            returnKeyType="next"
            onSubmitEditing={() => passRef.current?.focus()}
            error={emailError}
          />
          <TextField
            ref={passRef}
            label="Şifre"
            value={password}
            onChangeText={setPassword}
            placeholder="••••••••••"
            secureTextEntry
            secureToggle
            autoComplete="password"
            returnKeyType="go"
            onSubmitEditing={submit}
          />
          <Pressable onPress={() => setForgot(true)} style={{ alignSelf: 'flex-end' }} hitSlop={8}>
            <AppText variant="label" color={colors.primary}>Şifremi unuttum</AppText>
          </Pressable>
          {error ? <ErrorBox message={error} /> : null}
          <Button title="Giriş yap" onPress={submit} loading={loading} disabled={!canSubmit} />
          <View style={styles.divider}>
            <View style={[styles.line, { backgroundColor: colors.border }]} />
            <AppText variant="caption" color={colors.textSubtle}>veya</AppText>
            <View style={[styles.line, { backgroundColor: colors.border }]} />
          </View>
          <View style={{ flexDirection: 'row', justifyContent: 'center', gap: 6 }}>
            <AppText variant="small" color={colors.textMuted}>Hesabınız yok mu?</AppText>
            <Link href="/register">
              <AppText variant="label" color={colors.text}>Kayıt olun</AppText>
            </Link>
          </View>
          <View style={{ marginTop: 'auto', paddingTop: space.lg }}>
            <ServerStatus />
          </View>
        </ScrollView>
      </KeyboardAvoidingView>
      <Sheet visible={forgot} onClose={() => setForgot(false)} title="Şifre sıfırlama" showClose>
        <AppText color={colors.textMuted}>
          Bu sürümde e-posta ile şifre sıfırlama yok. Kurumunuzdaki sistem yöneticisi, yönetim panelinden hesabınızı yeniden oluşturabilir.
        </AppText>
        <InfoNote>Kullanıcı adınızla da giriş yapabilirsiniz.</InfoNote>
        <Button title="Tamam" onPress={() => setForgot(false)} />
      </Sheet>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  scroll: { flexGrow: 1, padding: space.xl, gap: space.lg, maxWidth: 480, width: '100%', alignSelf: 'center' },
  divider: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  line: { flex: 1, height: 1 },
});
