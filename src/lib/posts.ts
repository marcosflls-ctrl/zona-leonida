import { getCollection } from 'astro:content';

/** Artículos publicados (sin borradores, sin fechas futuras), más recientes primero. */
export async function getPublishedPosts() {
  const now = Date.now();
  const posts = await getCollection('posts', ({ data }) => !data.draft && data.date.getTime() <= now);
  return posts.sort((a, b) => b.data.date.getTime() - a.data.date.getTime());
}

export function formatDate(d: Date) {
  return d.toLocaleDateString('es-ES', { day: 'numeric', month: 'long', year: 'numeric', timeZone: 'Europe/Madrid' });
}

export function formatDateTime(d: Date) {
  const day = formatDate(d);
  const time = d.toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit', timeZone: 'Europe/Madrid' });
  return `${day}, ${time} (hora de España)`;
}

export function readingTime(text: string) {
  return Math.max(1, Math.round(text.split(/\s+/).length / 220));
}
