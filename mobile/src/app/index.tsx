import { Redirect } from 'expo-router';

import { useAuth } from '../lib/auth';

/** Kök adres: oturuma göre giriş ekranına veya ana sohbete yönlendirir. */
export default function Index() {
  const { user } = useAuth();
  return <Redirect href={user ? '/home' : '/login'} />;
}
