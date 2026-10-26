import Feather from '@expo/vector-icons/Feather';
import Ionicons from '@expo/vector-icons/Ionicons';
import { forwardRef, useEffect, useRef, useState, type ComponentProps, type ReactNode } from 'react';
import {
  ActivityIndicator,
  Animated,
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
  type PressableProps,
  type StyleProp,
  type TextInputInstance,
  type TextInputProps,
  type TextStyle,
  type ViewStyle,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { fonts, radius, space, type, useTheme } from '../theme';

export type IconName = ComponentProps<typeof Feather>['name'];
export const Icon = Feather;

// ---------------------------------------------------------------------------
export function AppText({
  variant = 'body',
  color,
  style,
  children,
  numberOfLines,
  selectable,
}: {
  variant?: keyof typeof type;
  color?: string;
  style?: StyleProp<TextStyle>;
  children: ReactNode;
  numberOfLines?: number;
  selectable?: boolean;
}) {
  const { colors } = useTheme();
  return (
    <Text numberOfLines={numberOfLines} selectable={selectable} style={[type[variant], { color: color ?? colors.text }, style]}>
      {children}
    </Text>
  );
}

export function Eyebrow({ children, color, style }: { children: ReactNode; color?: string; style?: StyleProp<TextStyle> }) {
  const { colors } = useTheme();
  return (
    <AppText variant="eyebrow" color={color ?? colors.primary} style={[{ textTransform: 'uppercase' }, style]}>
      {children}
    </AppText>
  );
}

// ---------------------------------------------------------------------------
type ButtonVariant = 'primary' | 'secondary' | 'soft' | 'ghost';

export function Button({
  title,
  onPress,
  variant = 'primary',
  icon,
  loading,
  disabled,
  style,
  size = 'lg',
}: {
  title: string;
  onPress?: () => void;
  variant?: ButtonVariant;
  icon?: IconName;
  loading?: boolean;
  disabled?: boolean;
  style?: StyleProp<ViewStyle>;
  size?: 'lg' | 'md' | 'sm';
}) {
  const { colors } = useTheme();
  const off = !!disabled && !loading;
  const palette = {
    primary: [colors.primary, colors.onPrimary, 'transparent'],
    secondary: [colors.surface, colors.text, colors.border],
    soft: [colors.primarySoft, colors.primary, 'transparent'],
    ghost: ['transparent', colors.primary, 'transparent'],
  }[variant];
  const [bg, fg, border] = off ? [colors.disabled, colors.onDisabled, 'transparent'] : palette;
  const height = { lg: 48, md: 42, sm: 34 }[size];
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityState={{ disabled: off, busy: !!loading }}
      onPress={off || loading ? undefined : onPress}
      style={({ pressed }) => [
        styles.button,
        {
          height,
          backgroundColor: pressed && variant === 'primary' && !off ? colors.primaryPressed : bg,
          borderColor: border,
          opacity: pressed && variant !== 'primary' ? 0.7 : 1,
          paddingHorizontal: size === 'sm' ? 12 : 18,
        },
        style,
      ]}
    >
      {loading ? (
        <ActivityIndicator color={fg} />
      ) : (
        <>
          {icon ? <Feather name={icon} size={size === 'sm' ? 14 : 17} color={fg} /> : null}
          <Text style={[size === 'sm' ? type.smallMedium : type.bodyMedium, { color: fg, fontFamily: fonts.semibold }]}>{title}</Text>
        </>
      )}
    </Pressable>
  );
}

/** Dolu/boş yıldız (Feather'da dolu yıldız olmadığı için Ionicons). */
export function Star({ filled, size = 16, color }: { filled?: boolean; size?: number; color?: string }) {
  const { colors } = useTheme();
  return <Ionicons name={filled ? 'star' : 'star-outline'} size={size} color={color ?? (filled ? colors.primary : colors.textMuted)} />;
}

/** Başlık çubuğundaki kare ikon düğmesi (Figma: "+", "←", "···"). */
export function IconSquare({
  icon,
  onPress,
  label,
  color,
  bg,
  size = 36,
  style,
  node,
}: {
  node?: ReactNode;
  icon: IconName;
  onPress?: () => void;
  label: string;
  color?: string;
  bg?: string;
  size?: number;
  style?: StyleProp<ViewStyle>;
}) {
  const { colors } = useTheme();
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={label}
      hitSlop={6}
      onPress={onPress}
      style={({ pressed }) => [
        { width: size, height: size, borderRadius: 10, alignItems: 'center', justifyContent: 'center', backgroundColor: bg ?? colors.surfaceAlt, opacity: pressed ? 0.6 : 1 },
        style,
      ]}
    >
      {node ?? <Feather name={icon} size={size * 0.5} color={color ?? colors.text} />}
    </Pressable>
  );
}

export function IconTile({ icon, size = 36, tone = 'primary', letter }: { icon?: IconName; size?: number; tone?: 'primary' | 'neutral'; letter?: string }) {
  const { colors } = useTheme();
  const bg = tone === 'primary' ? colors.primarySoft : colors.surfaceAlt;
  const fg = tone === 'primary' ? colors.primary : colors.text;
  return (
    <View style={{ width: size, height: size, borderRadius: 10, backgroundColor: bg, alignItems: 'center', justifyContent: 'center' }}>
      {letter ? (
        <Text style={{ fontFamily: fonts.bold, fontSize: size * 0.4, color: fg }}>{letter}</Text>
      ) : icon ? (
        <Feather name={icon} size={size * 0.46} color={fg} />
      ) : null}
    </View>
  );
}

export function Avatar({ name, size = 36, solid }: { name: string; size?: number; solid?: boolean }) {
  const { colors } = useTheme();
  const initials =
    name
      .split(/[\s._-]+/)
      .filter(Boolean)
      .slice(0, 2)
      .map((p) => p[0]?.toLocaleUpperCase('tr-TR'))
      .join('') || '?';
  return (
    <View
      style={{
        width: size,
        height: size,
        borderRadius: size / 2,
        backgroundColor: solid ? colors.primary : colors.primarySoft,
        alignItems: 'center',
        justifyContent: 'center',
      }}
    >
      <Text style={{ fontFamily: fonts.bold, fontSize: size * 0.34, color: solid ? '#fff' : colors.primary }}>{initials}</Text>
    </View>
  );
}

// ---------------------------------------------------------------------------
export const TextField = forwardRef<
  TextInputInstance,
  TextInputProps & { label?: string; icon?: IconName; error?: string | null; secureToggle?: boolean; hint?: string; containerStyle?: StyleProp<ViewStyle> }
>(function TextField({ label, icon, error, secureToggle, hint, style, secureTextEntry, containerStyle, ...rest }, ref) {
  const { colors } = useTheme();
  const [focused, setFocused] = useState(false);
  const [hidden, setHidden] = useState(!!secureTextEntry);
  const active = focused || (!!rest.value && !!error);
  return (
    <View style={[{ gap: 7 }, containerStyle]}>
      {label ? <AppText variant="label">{label}</AppText> : null}
      <View
        style={[
          styles.field,
          {
            backgroundColor: colors.surface,
            borderColor: error ? colors.danger : active ? colors.primary : colors.border,
            borderWidth: error || focused ? 1.5 : 1,
          },
        ]}
      >
        {icon ? <Feather name={icon} size={16} color={focused ? colors.primary : colors.textSubtle} /> : null}
        <TextInput
          ref={ref}
          placeholderTextColor={colors.textSubtle}
          secureTextEntry={hidden}
          onFocus={(e) => {
            setFocused(true);
            rest.onFocus?.(e);
          }}
          onBlur={(e) => {
            setFocused(false);
            rest.onBlur?.(e);
          }}
          style={[styles.fieldInput, { color: colors.text }, style]}
          {...rest}
        />
        {secureToggle ? (
          <Pressable hitSlop={8} onPress={() => setHidden((h) => !h)} accessibilityLabel={hidden ? 'Şifreyi göster' : 'Şifreyi gizle'}>
            <Feather name={hidden ? 'eye' : 'eye-off'} size={17} color={colors.textSubtle} />
          </Pressable>
        ) : null}
      </View>
      {error ? (
        <AppText variant="caption" color={colors.danger}>{error}</AppText>
      ) : hint ? (
        <AppText variant="caption" color={colors.textSubtle}>{hint}</AppText>
      ) : null}
    </View>
  );
});

export function SearchField(props: TextInputProps) {
  return <TextField icon="search" autoCapitalize="none" autoCorrect={false} returnKeyType="search" {...props} />;
}

export function Checkbox({ checked, onChange, children }: { checked: boolean; onChange: (v: boolean) => void; children: ReactNode }) {
  const { colors } = useTheme();
  return (
    <Pressable
      accessibilityRole="checkbox"
      accessibilityState={{ checked }}
      onPress={() => onChange(!checked)}
      style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}
    >
      <View
        style={{
          width: 22,
          height: 22,
          borderRadius: 6,
          borderWidth: checked ? 0 : 1.5,
          borderColor: colors.border,
          backgroundColor: checked ? colors.primary : colors.surface,
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        {checked ? <Feather name="check" size={15} color="#fff" /> : null}
      </View>
      <View style={{ flex: 1 }}>{children}</View>
    </Pressable>
  );
}

// ---------------------------------------------------------------------------
export function Card({
  children,
  style,
  onPress,
  onLongPress,
}: {
  children: ReactNode;
  style?: StyleProp<ViewStyle>;
  onPress?: PressableProps['onPress'];
  onLongPress?: PressableProps['onLongPress'];
}) {
  const { colors, dark } = useTheme();
  const base = [styles.card, { backgroundColor: colors.surface, borderColor: colors.border }, !dark && shadow(1), style];
  if (!onPress && !onLongPress) return <View style={base}>{children}</View>;
  return (
    <Pressable onPress={onPress} onLongPress={onLongPress} style={({ pressed }) => [...base, { opacity: pressed ? 0.85 : 1 }]}>
      {children}
    </Pressable>
  );
}

export function Chip({ label, selected, onPress, style }: { label: string; selected?: boolean; onPress?: () => void; style?: StyleProp<ViewStyle> }) {
  const { colors } = useTheme();
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityState={{ selected: !!selected }}
      onPress={onPress}
      style={({ pressed }) => [
        styles.chip,
        {
          backgroundColor: selected ? colors.primary : colors.surface,
          borderColor: selected ? colors.primary : colors.border,
          opacity: pressed ? 0.75 : 1,
        },
        style,
      ]}
    >
      <Text style={[type.smallMedium, { color: selected ? '#fff' : colors.text }]} numberOfLines={1}>
        {label}
      </Text>
    </Pressable>
  );
}

/** Pembe hap etiket — Figma'daki "EASA • CS-25", "CS-25 • 25.785" kaynak etiketleri. */
export function Tag({ label, onPress, tone = 'primary' }: { label: string; onPress?: () => void; tone?: 'primary' | 'neutral' | 'success' | 'info' | 'warning' }) {
  const { colors } = useTheme();
  const map = {
    primary: [colors.primarySoft, colors.primary],
    neutral: [colors.surfaceAlt, colors.textMuted],
    success: [colors.successSoft, colors.success],
    info: [colors.infoSoft, colors.info],
    warning: [colors.warningSoft, colors.warning],
  } as const;
  const [bg, fg] = map[tone];
  const content = (
    <Text style={[type.caption, { color: fg, fontFamily: fonts.semibold }]} numberOfLines={1}>
      {label}
    </Text>
  );
  const s = [styles.tag, { backgroundColor: bg }];
  if (!onPress) return <View style={s}>{content}</View>;
  return (
    <Pressable onPress={onPress} accessibilityRole="link" style={({ pressed }) => [...s, { opacity: pressed ? 0.7 : 1 }]}>
      {content}
    </Pressable>
  );
}

export function Segmented<T extends string>({ options, value, onChange }: { options: { value: T; label: string }[]; value: T; onChange: (v: T) => void }) {
  const { colors, dark } = useTheme();
  return (
    <View style={[styles.segment, { backgroundColor: dark ? colors.surfaceAlt : '#E8ECF1' }]}>
      {options.map((o) => {
        const active = o.value === value;
        return (
          <Pressable
            key={o.value}
            accessibilityRole="tab"
            accessibilityState={{ selected: active }}
            onPress={() => onChange(o.value)}
            style={[styles.segmentItem, active && { backgroundColor: colors.surface, ...shadow(1) }]}
          >
            <Text style={[type.smallMedium, { color: active ? colors.primary : colors.textMuted, fontFamily: active ? fonts.semibold : fonts.medium }]}>
              {o.label}
            </Text>
          </Pressable>
        );
      })}
    </View>
  );
}

/** Ayar/menü satırı: ikon karosu + etiket + sağda ok / değer / anahtar. */
export function ListRow({
  icon,
  label,
  value,
  onPress,
  right,
  chevron = true,
}: {
  icon: IconName;
  label: string;
  value?: string;
  onPress?: () => void;
  right?: ReactNode;
  chevron?: boolean;
}) {
  const { colors } = useTheme();
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      style={({ pressed }) => [styles.listRow, { backgroundColor: pressed ? colors.surfaceAlt : 'transparent' }]}
    >
      <IconTile icon={icon} size={34} />
      <AppText variant="bodyMedium" style={{ flex: 1 }}>{label}</AppText>
      {value ? <AppText variant="small" color={colors.textMuted}>{value}</AppText> : null}
      {right}
      {chevron && !right ? <Feather name="chevron-right" size={18} color={colors.textSubtle} /> : null}
    </Pressable>
  );
}

export function InfoNote({ children, tone = 'neutral', icon }: { children: ReactNode; tone?: 'neutral' | 'warning'; icon?: IconName }) {
  const { colors } = useTheme();
  const warn = tone === 'warning';
  return (
    <View style={[styles.note, { backgroundColor: warn ? colors.warningSoft : colors.surfaceAlt }]}>
      <Feather name={icon ?? (warn ? 'alert-triangle' : 'info')} size={14} color={warn ? colors.warning : colors.primary} />
      <AppText variant="caption" color={warn ? colors.onWarningSoft : colors.textMuted} style={{ flex: 1 }}>
        {children}
      </AppText>
    </View>
  );
}

export function SectionLabel({ title, style }: { title: string; style?: StyleProp<TextStyle> }) {
  const { colors } = useTheme();
  return (
    <AppText variant="eyebrow" color={colors.textMuted} style={[{ textTransform: 'uppercase', marginTop: 6 }, style]}>
      {title}
    </AppText>
  );
}

// ---------------------------------------------------------------------------
export function EmptyState({ icon, title, message, action }: { icon: IconName; title: string; message?: string; action?: ReactNode }) {
  const { colors } = useTheme();
  return (
    <View style={styles.empty}>
      <IconTile icon={icon} size={56} />
      <AppText variant="heading" style={{ textAlign: 'center' }}>{title}</AppText>
      {message ? (
        <AppText variant="small" color={colors.textMuted} style={{ textAlign: 'center', maxWidth: 300 }}>{message}</AppText>
      ) : null}
      {action}
    </View>
  );
}

export function ErrorBox({ message, onRetry }: { message: string; onRetry?: () => void }) {
  const { colors } = useTheme();
  return (
    <View style={[styles.errorBox, { backgroundColor: colors.primarySoft, borderColor: colors.primarySoftBorder }]}>
      <Feather name="alert-circle" size={18} color={colors.primary} />
      <AppText variant="small" style={{ flex: 1 }}>{message}</AppText>
      {onRetry ? <Button title="Tekrar dene" size="sm" variant="secondary" onPress={onRetry} /> : null}
    </View>
  );
}

export function Loading({ label }: { label?: string }) {
  const { colors } = useTheme();
  return (
    <View style={styles.loading}>
      <ActivityIndicator color={colors.primary} />
      {label ? <AppText variant="small" color={colors.textMuted}>{label}</AppText> : null}
    </View>
  );
}

export function TypingDots() {
  const { colors } = useTheme();
  const a = useRef(new Animated.Value(0.3)).current;
  const b = useRef(new Animated.Value(0.3)).current;
  const c = useRef(new Animated.Value(0.3)).current;
  useEffect(() => {
    const anims = [a, b, c].map((d, i) =>
      Animated.loop(
        Animated.sequence([
          Animated.delay(i * 160),
          Animated.timing(d, { toValue: 1, duration: 320, useNativeDriver: true }),
          Animated.timing(d, { toValue: 0.3, duration: 320, useNativeDriver: true }),
          Animated.delay((2 - i) * 160),
        ]),
      ),
    );
    anims.forEach((x) => x.start());
    return () => anims.forEach((x) => x.stop());
  }, [a, b, c]);
  return (
    <View style={{ flexDirection: 'row', gap: 5, paddingVertical: 4 }}>
      {[a, b, c].map((d, i) => (
        <Animated.View key={i} style={{ width: 7, height: 7, borderRadius: 4, backgroundColor: colors.primary, opacity: d }} />
      ))}
    </View>
  );
}

/** Alttan açılan panel (Figma "Tema", "Kaynak detayı"). */
export function Sheet({
  visible,
  onClose,
  title,
  subtitle,
  children,
  showClose,
}: {
  visible: boolean;
  onClose: () => void;
  title: string;
  subtitle?: string;
  children: ReactNode;
  showClose?: boolean;
}) {
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose} statusBarTranslucent>
      <View style={{ flex: 1, justifyContent: 'flex-end' }}>
        <Pressable style={[StyleSheet.absoluteFill, { backgroundColor: colors.overlay }]} onPress={onClose} accessibilityLabel="Kapat" />
        <View style={[styles.sheet, { backgroundColor: colors.surface, paddingBottom: insets.bottom + 18 }]}>
          <View style={[styles.grabber, { backgroundColor: colors.border }]} />
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12 }}>
            <AppText variant="title" style={{ flex: 1 }}>{title}</AppText>
            {showClose ? (
              <Pressable onPress={onClose} hitSlop={10} accessibilityLabel="Kapat">
                <Feather name="x" size={20} color={colors.textMuted} />
              </Pressable>
            ) : null}
          </View>
          {subtitle ? <AppText variant="small" color={colors.textMuted}>{subtitle}</AppText> : null}
          <ScrollView bounces={false} style={{ maxHeight: 560 }} contentContainerStyle={{ gap: 12, paddingTop: 4 }}>
            {children}
          </ScrollView>
        </View>
      </View>
    </Modal>
  );
}

export function shadow(level: 1 | 2 | 3 = 1): ViewStyle {
  return {
    shadowColor: '#0F172A',
    shadowOpacity: [0, 0.04, 0.08, 0.12][level],
    shadowRadius: [0, 6, 12, 20][level],
    shadowOffset: { width: 0, height: level },
    elevation: level,
  };
}

const styles = StyleSheet.create({
  button: { borderRadius: radius.sm, borderWidth: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8 },
  field: { flexDirection: 'row', alignItems: 'center', gap: 10, borderRadius: radius.sm, paddingHorizontal: 14, minHeight: 48 },
  fieldInput: { flex: 1, fontFamily: fonts.regular, fontSize: 15, paddingVertical: 11 },
  card: { borderRadius: radius.lg, borderWidth: 1, padding: space.lg },
  chip: { paddingHorizontal: 16, height: 34, borderRadius: radius.pill, borderWidth: 1, alignItems: 'center', justifyContent: 'center' },
  tag: { paddingHorizontal: 12, paddingVertical: 5, borderRadius: radius.pill, alignSelf: 'flex-start' },
  segment: { flexDirection: 'row', borderRadius: radius.md, padding: 4 },
  segmentItem: { flex: 1, height: 36, alignItems: 'center', justifyContent: 'center', borderRadius: radius.sm },
  listRow: { flexDirection: 'row', alignItems: 'center', gap: 14, paddingVertical: 10, paddingHorizontal: 6, borderRadius: radius.md },
  note: { flexDirection: 'row', alignItems: 'center', gap: 10, paddingHorizontal: 14, paddingVertical: 12, borderRadius: radius.md },
  empty: { alignItems: 'center', gap: 10, paddingVertical: 48, paddingHorizontal: 24 },
  errorBox: { flexDirection: 'row', alignItems: 'center', gap: 10, padding: 12, borderRadius: radius.md, borderWidth: 1 },
  loading: { padding: 32, alignItems: 'center', justifyContent: 'center', gap: 10 },
  sheet: { borderTopLeftRadius: 24, borderTopRightRadius: 24, paddingHorizontal: 20, paddingTop: 10, gap: 10 },
  grabber: { width: 40, height: 4, borderRadius: 2, alignSelf: 'flex-start', marginBottom: 8 },
});
