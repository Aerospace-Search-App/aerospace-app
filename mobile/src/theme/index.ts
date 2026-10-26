import { createContext, createElement, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import { useColorScheme } from 'react-native';

import { storage } from '../lib/storage';

/**
 * AeroStandart Design System v1 (Figma "00 — Foundations")
 *  Primary #C8102E · Deep Crimson #870C2B · Canvas #F8FAFC · Surface #FFFFFF · Ink #0F172A · Dark Surface #0F172A
 */
export type Colors = {
  bg: string;
  surface: string;
  surfaceAlt: string;
  border: string;
  text: string;
  textMuted: string;
  textSubtle: string;
  primary: string;
  primaryPressed: string;
  primarySoft: string;
  primarySoftBorder: string;
  onPrimary: string;
  hero: string;
  disabled: string;
  onDisabled: string;
  info: string;
  infoSoft: string;
  success: string;
  successSoft: string;
  warning: string;
  warningSoft: string;
  onWarningSoft: string;
  danger: string;
  overlay: string;
  navy: string;
};

export const lightColors: Colors = {
  bg: '#F8FAFC',
  surface: '#FFFFFF',
  surfaceAlt: '#F1F5F9',
  border: '#E5E7EB',
  text: '#0F172A',
  textMuted: '#64748B',
  textSubtle: '#94A3B8',
  primary: '#C8102E',
  primaryPressed: '#870C2B',
  primarySoft: '#FDECEF',
  primarySoftBorder: '#F6C9D1',
  onPrimary: '#FFFFFF',
  hero: '#FDEEF1',
  disabled: '#E2E8F0',
  onDisabled: '#94A3B8',
  info: '#0C8CE9',
  infoSoft: '#EAF5FE',
  success: '#16A34A',
  successSoft: '#ECFDF3',
  warning: '#B45309',
  warningSoft: '#FFF7ED',
  onWarningSoft: '#9A3412',
  danger: '#C8102E',
  overlay: 'rgba(15, 23, 42, 0.45)',
  navy: '#0F172A',
};

export const darkColors: Colors = {
  bg: '#070B14',
  surface: '#0F172A',
  surfaceAlt: '#1E293B',
  border: '#1E293B',
  text: '#F1F5F9',
  textMuted: '#94A3B8',
  textSubtle: '#64748B',
  primary: '#E11D48',
  primaryPressed: '#C8102E',
  primarySoft: '#340612',
  primarySoftBorder: '#640E20',
  onPrimary: '#FFFFFF',
  hero: '#340612',
  disabled: '#1E293B',
  onDisabled: '#64748B',
  info: '#38A3F1',
  infoSoft: '#0B2236',
  success: '#22C55E',
  successSoft: '#0B2A19',
  warning: '#F59E0B',
  warningSoft: '#2A1A06',
  onWarningSoft: '#FCD34D',
  danger: '#F43F5E',
  overlay: 'rgba(0, 0, 0, 0.6)',
  navy: '#1E293B',
};

export const radius = { xs: 6, sm: 10, md: 12, lg: 16, xl: 22, pill: 999 };
export const space = { xs: 4, sm: 8, md: 12, lg: 16, xl: 20, xxl: 28 };

export const fonts = {
  regular: 'Inter_400Regular',
  medium: 'Inter_500Medium',
  semibold: 'Inter_600SemiBold',
  bold: 'Inter_700Bold',
};

export const type = {
  display: { fontFamily: fonts.bold, fontSize: 28, lineHeight: 34, letterSpacing: -0.5 },
  title: { fontFamily: fonts.bold, fontSize: 22, lineHeight: 28, letterSpacing: -0.3 },
  heading: { fontFamily: fonts.semibold, fontSize: 16, lineHeight: 22 },
  body: { fontFamily: fonts.regular, fontSize: 15, lineHeight: 22 },
  bodyMedium: { fontFamily: fonts.medium, fontSize: 15, lineHeight: 22 },
  label: { fontFamily: fonts.semibold, fontSize: 13, lineHeight: 18 },
  small: { fontFamily: fonts.regular, fontSize: 13, lineHeight: 18 },
  smallMedium: { fontFamily: fonts.medium, fontSize: 13, lineHeight: 18 },
  caption: { fontFamily: fonts.regular, fontSize: 12, lineHeight: 16 },
  eyebrow: { fontFamily: fonts.bold, fontSize: 11, lineHeight: 14, letterSpacing: 1.1 },
  mono: { fontFamily: fonts.semibold, fontSize: 12, lineHeight: 16, letterSpacing: 0.2 },
} as const;

export type ThemePref = 'system' | 'light' | 'dark';
const PREF_KEY = 'aerostd.theme';

interface ThemeCtx {
  colors: Colors;
  dark: boolean;
  pref: ThemePref;
  setPref: (p: ThemePref) => void;
}

const Ctx = createContext<ThemeCtx | null>(null);

export function ThemeProvider({ children }: { children: ReactNode }) {
  const system = useColorScheme();
  const [pref, setPrefState] = useState<ThemePref>('system');

  useEffect(() => {
    void storage.get(PREF_KEY).then((v) => {
      if (v === 'light' || v === 'dark' || v === 'system') setPrefState(v);
    });
  }, []);

  const value = useMemo<ThemeCtx>(() => {
    const dark = pref === 'system' ? system === 'dark' : pref === 'dark';
    return {
      colors: dark ? darkColors : lightColors,
      dark,
      pref,
      setPref: (p) => {
        setPrefState(p);
        void storage.set(PREF_KEY, p);
      },
    };
  }, [pref, system]);

  return createElement(Ctx.Provider, { value }, children);
}

export function useTheme(): ThemeCtx {
  const ctx = useContext(Ctx);
  if (ctx) return ctx;
  return { colors: lightColors, dark: false, pref: 'system', setPref: () => {} };
}
