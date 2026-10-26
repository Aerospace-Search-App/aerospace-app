import { useQueryClient } from '@tanstack/react-query';
import * as Haptics from 'expo-haptics';
import { useEffect, useState } from 'react';

import { endpoints } from './api';

/** Standart (chunkId=null) veya madde kaydetme anahtarı; iyimser günceller. */
export function useSaveToggle(documentId: number, chunkId: number | null, initial: boolean) {
  const qc = useQueryClient();
  const [saved, setSaved] = useState(initial);
  const [busy, setBusy] = useState(false);
  useEffect(() => setSaved(initial), [initial]);

  const toggle = async () => {
    const next = !saved;
    setSaved(next);
    setBusy(true);
    void Haptics.selectionAsync().catch(() => {});
    try {
      if (next) await endpoints.save(documentId, chunkId);
      else await endpoints.unsave(documentId, chunkId);
      void qc.invalidateQueries({ queryKey: ['saved'] });
      void qc.invalidateQueries({ queryKey: ['documents'] });
      void qc.invalidateQueries({ queryKey: ['document', documentId] });
      if (chunkId) void qc.invalidateQueries({ queryKey: ['source', chunkId] });
    } catch {
      setSaved(!next);
    } finally {
      setBusy(false);
    }
  };
  return { saved, toggle, busy };
}
