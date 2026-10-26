import { useEffect, useRef, useState, type ComponentRef } from 'react';
import { Keyboard, LayoutAnimation, Platform, View } from 'react-native';

/**
 * Klavyenin, verilen görünümün alt kenarını ne kadar örttüğünü döndürür.
 * Sistem pencereyi zaten küçülttüyse (Android adjustResize) 0 döner; kenardan kenara (edge-to-edge)
 * modda veya iOS'ta gereken boşluğu verir. Sekme çubuğu / başlık yüksekliğinden bağımsız çalışır.
 */
export function useKeyboardInset() {
  const ref = useRef<ComponentRef<typeof View>>(null);
  const [inset, setInset] = useState(0);

  useEffect(() => {
    if (Platform.OS === 'web') return;
    const showEvt = Platform.OS === 'ios' ? 'keyboardWillShow' : 'keyboardDidShow';
    const hideEvt = Platform.OS === 'ios' ? 'keyboardWillHide' : 'keyboardDidHide';
    const show = Keyboard.addListener(showEvt, (e) => {
      const kbTop = e.endCoordinates.screenY;
      ref.current?.measureInWindow((_x: number, y: number, _w: number, h: number) => {
        const overlap = Math.max(0, y + h - kbTop);
        if (Platform.OS === 'ios') LayoutAnimation.configureNext(LayoutAnimation.create(e.duration || 250, 'keyboard', 'opacity'));
        setInset(overlap);
      });
    });
    const hide = Keyboard.addListener(hideEvt, (e) => {
      if (Platform.OS === 'ios') LayoutAnimation.configureNext(LayoutAnimation.create(e?.duration || 250, 'keyboard', 'opacity'));
      setInset(0);
    });
    return () => {
      show.remove();
      hide.remove();
    };
  }, []);

  return { ref, inset };
}
