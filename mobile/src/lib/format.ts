export const CATEGORY_LABEL: Record<string, string> = { civil: 'Sivil', defense: 'Savunma', both: 'Sivil + Savunma' };

function sameDay(a: Date, b: Date) {
  return a.toDateString() === b.toDateString();
}

/** "14:32", "Dün", "Pazartesi", "12 Eki" */
export function shortTime(iso: string): string {
  const d = new Date(iso);
  const now = new Date();
  if (sameDay(d, now)) return d.toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit' });
  const y = new Date();
  y.setDate(now.getDate() - 1);
  if (sameDay(d, y)) return 'Dün';
  const days = (now.getTime() - d.getTime()) / 86400000;
  if (days < 7) return d.toLocaleDateString('tr-TR', { weekday: 'long' });
  return d.toLocaleDateString('tr-TR', { day: 'numeric', month: 'short' });
}

/** "Bugün 14:25", "Dün", "17 Eki" */
export function savedTime(iso: string): string {
  const d = new Date(iso);
  if (sameDay(d, new Date())) return `Bugün ${d.toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit' })}`;
  return shortTime(iso);
}

export function dayBucket(iso: string): 'BUGÜN' | 'SON 7 GÜN' | 'DAHA ÖNCE' {
  const d = new Date(iso);
  const now = new Date();
  if (sameDay(d, now)) return 'BUGÜN';
  return (now.getTime() - d.getTime()) / 86400000 < 7 ? 'SON 7 GÜN' : 'DAHA ÖNCE';
}

export function stripMarkdown(s: string): string {
  return s.replace(/\*\*/g, '').replace(/\[\d{1,2}\]/g, '').replace(/^\s*[-*•]\s+/gm, '').replace(/\s+/g, ' ').trim();
}
