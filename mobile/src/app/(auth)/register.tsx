import { Link, router } from 'expo-router';
import { useRef, useState } from 'react';
import { KeyboardAvoidingView, Platform, ScrollView, StyleSheet, View, type TextInputInstance } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { AppText, Button, Checkbox, ErrorBox, IconSquare, TextField } from '../../components/ui';
import { useAuth } from '../../lib/auth';
import { space, useTheme } from '../../theme';

const USERNAME_RE = /^[a-zA-Z0-9._-]{3,30}$/;

function passwordProblem(p: string) {
  if (!p) return null;
  if (p.length < 8) return 'En az 8 karakter olmalı.';
  if (!/\d/.test(p) || !/[A-Za-zÇĞİÖŞÜçğıöşü]/.test(p)) return 'En az bir harf ve bir rakam içermeli.';
  return null;
}

export default function RegisterScreen() {
  const { colors } = useTheme();
  const { signUp } = useAuth();
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [terms, setTerms] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const emailRef = useRef<TextInputInstance>(null);
  const passRef = useRef<TextInputInstance>(null);
  const confirmRef = useRef<TextInputInstance>(null);

  const userError = username && !USERNAME_RE.test(username.trim()) ? '3-30 karakter; harf, rakam, nokta, alt çizgi.' : null;
  const emailError = email && !/^\S+@\S+\.\S+$/.test(email.trim()) ? 'Geçerli bir e-posta adresi girin.' : null;
  const passError = passwordProblem(password);
  const confirmError = confirm && confirm !== password ? 'Şifreler eşleşmiyor.' : null;
  const canSubmit = !!username && !userError && !!email && !emailError && !!password && !passError && confirm === password && terms;

  const submit = async () => {
    if (!canSubmit || loading) return;
    setLoading(true);
    setError(null);
    try {
      await signUp(username, email, password, terms);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.surface }}>
      <View style={styles.header}>
        <IconSquare icon="arrow-left" label="Geri" onPress={() => (router.canGoBack() ? router.back() : router.replace('/login'))} />
        <AppText variant="heading">Kayıt ol</AppText>
      </View>
      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
        <ScrollView contentContainerStyle={styles.scroll} keyboardShouldPersistTaps="handled">
          <View style={{ gap: 6 }}>
            <AppText variant="display">Hesabınızı oluşturun</AppText>
            <AppText color={colors.textMuted}>Kaynaklı yanıtlar ve sohbet geçmişiniz tek hesapta saklanır.</AppText>
          </View>
          <TextField label="Kullanıcı adı" value={username} onChangeText={setUsername} placeholder="ayse.kaya" autoCapitalize="none"
            autoCorrect={false} autoComplete="username" returnKeyType="next" onSubmitEditing={() => emailRef.current?.focus()} error={userError} />
          <TextField ref={emailRef} label="E-posta" value={email} onChangeText={setEmail} placeholder="ayse@kurum.com" autoCapitalize="none"
            keyboardType="email-address" autoComplete="email" returnKeyType="next" onSubmitEditing={() => passRef.current?.focus()} error={emailError} />
          <TextField ref={passRef} label="Şifre" value={password} onChangeText={setPassword} placeholder="En az 8 karakter" secureTextEntry
            secureToggle autoComplete="new-password" returnKeyType="next" onSubmitEditing={() => confirmRef.current?.focus()} error={passError} />
          <TextField ref={confirmRef} label="Şifre tekrar" value={confirm} onChangeText={setConfirm} placeholder="••••••••••" secureTextEntry
            autoComplete="new-password" returnKeyType="go" onSubmitEditing={submit} error={confirmError} />
          <Checkbox checked={terms} onChange={setTerms}>
            <AppText variant="small" color={colors.textMuted}>KVKK ve kullanım koşullarını kabul ediyorum.</AppText>
          </Checkbox>
          {error ? <ErrorBox message={error} /> : null}
          <Button title="Hesap oluştur" onPress={submit} loading={loading} disabled={!canSubmit} />
          <View style={{ flexDirection: 'row', justifyContent: 'center', gap: 6 }}>
            <AppText variant="small" color={colors.textMuted}>Zaten hesabınız var mı?</AppText>
            <Link href="/login" replace>
              <AppText variant="label" color={colors.text}>Giriş yapın</AppText>
            </Link>
          </View>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  header: { flexDirection: 'row', alignItems: 'center', gap: 12, paddingHorizontal: 16, paddingVertical: 8 },
  scroll: { flexGrow: 1, padding: space.xl, paddingTop: space.md, gap: space.lg, maxWidth: 480, width: '100%', alignSelf: 'center' },
});
