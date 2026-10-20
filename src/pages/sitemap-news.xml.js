import { SITE } from '../config';
import { getPublishedPosts } from '../lib/posts';

// Mapa del sitio de noticias para Google News: solo noticias y descubrimientos de los últimos 2 días
// (Google solo admite artículos recientes; las guías van en el mapa del sitio normal).
const esc = (s) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');

export async function GET() {
  const limite = Date.now() - 2 * 24 * 3600 * 1000;
  const todas = await getPublishedPosts();
  const esNoticia = (p) => ['noticias', 'descubrimientos'].includes(p.data.category);
  const recientes = todas.filter((p) => p.data.date.getTime() >= limite && esNoticia(p));
  // Google da error si el mapa no tiene ninguna página: si no hay noticias de los últimos 2 días,
  // se deja la más reciente (o, si no hay ninguna, el último artículo). Google ignora las antiguas sin dar error.
  const posts = recientes.length ? recientes : (todas.filter(esNoticia).slice(0, 1).length ? todas.filter(esNoticia).slice(0, 1) : todas.slice(0, 1));
  const urls = posts.map((p) => `  <url>
    <loc>${SITE.url}/${p.data.category}/${p.id}/</loc>
    <news:news>
      <news:publication><news:name>${esc(SITE.name)}</news:name><news:language>es</news:language></news:publication>
      <news:publication_date>${p.data.date.toISOString()}</news:publication_date>
      <news:title>${esc(p.data.title)}</news:title>
    </news:news>
  </url>`).join('\n');
  const xml = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:news="http://www.google.com/schemas/sitemap-news/0.9">
${urls}
</urlset>
`;
  return new Response(xml, { headers: { 'Content-Type': 'application/xml; charset=utf-8' } });
}
