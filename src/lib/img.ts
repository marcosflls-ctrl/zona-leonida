import fs from 'node:fs';
import path from 'node:path';

/** srcset con las versiones -400/-800 que existan en /public, más la original (1600 px). */
export function srcset(src?: string): string | undefined {
  if (!src || !src.startsWith('/img/') || !src.endsWith('.webp')) return undefined;
  const base = src.slice(0, -5);
  const parts: string[] = [];
  for (const w of [400, 800]) {
    if (fs.existsSync(path.join(process.cwd(), 'public', `${base}-${w}.webp`))) parts.push(`${base}-${w}.webp ${w}w`);
  }
  if (!parts.length) return undefined;
  parts.push(`${src} 1600w`);
  return parts.join(', ');
}
