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

// Etiquetas tan comunes que no indican que dos artículos traten de lo mismo
const ETIQUETAS_GENERICAS = new Set(['gta-6', 'gta-vi', 'gta6', 'ps5', 'xbox', 'rockstar-games', 'rockstar', 'guia', 'noticias', 'take-two']);
const VACIAS = new Set(['para', 'como', 'cómo', 'todo', 'todos', 'sobre', 'según', 'segun', 'tendrá', 'será', 'están', 'esta', 'este', 'desde', 'hasta', 'entre', 'antes', 'después', 'nuevo', 'nueva', 'dice', 'sabemos', 'puede', 'podrás', 'tiene', 'cuál', 'cuando', 'cuándo', 'qué', 'quién', 'donde', 'dónde', 'lista', 'guía', 'rockstar']);
const palabras = (s: string) => new Set(
  s.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/gta\s*(6|vi)\b/g, ' ')
    .split(/[^a-z0-9ñ]+/).filter((w) => w.length > 3 && !VACIAS.has(w)),
);

/** Elige los artículos más relacionados con `post` por temática (etiquetas y palabras del título),
 * dando un pequeño empujón a las guías de referencia y a lo reciente, y evitando los que ya enlaza el texto. */
export function relacionados(post: any, todos: any[], n = 3) {
  const d = post.data;
  const tags = new Set((d.tags as string[]).filter((t) => !ETIQUETAS_GENERICAS.has(t)));
  const tit = palabras(`${d.title} ${d.description}`);
  const cuerpo: string = post.body ?? '';
  const ahora = Date.now();
  const puntuados = todos
    .filter((p) => p.id !== post.id)
    .map((p) => {
      const e = p.data;
      let s = 0;
      for (const t of e.tags as string[]) if (tags.has(t)) s += 3;
      for (const w of palabras(`${e.title} ${e.description}`)) if (tit.has(w)) s += 1.5;
      if (e.category === d.category) s += 1;
      if (e.pilar) s += 1;
      const dias = (ahora - e.date.getTime()) / 864e5;
      if (dias < 14) s += 0.5;
      if (cuerpo.includes(`/${e.category}/${p.id}/`)) s -= 2; // ya enlazado en el texto: mejor descubrir otro
      return { p, s };
    })
    .sort((a, b) => b.s - a.s || b.p.data.date.getTime() - a.p.data.date.getTime());
  const elegidos = puntuados.filter((x) => x.s >= 3).slice(0, n).map((x) => x.p);
  // En las noticias, que al menos uno sea una guía (suelen ser las páginas que más se buscan)
  if (d.category === 'noticias' && elegidos.length === n && !elegidos.some((p) => p.data.category !== 'noticias')) {
    const guia = puntuados.find((x) => x.p.data.category !== 'noticias' && x.s >= 1.5);
    if (guia) elegidos[n - 1] = guia.p;
  }
  // Si no hay suficientes afines, se completa con los mejor puntuados restantes
  for (const x of puntuados) { if (elegidos.length >= n) break; if (!elegidos.includes(x.p)) elegidos.push(x.p); }
  return elegidos;
}
