import { defineConfig } from 'astro/config';
import sitemap from '@astrojs/sitemap';
import fs from 'node:fs';

// Fecha de última modificación de cada artículo (updated o date) para el mapa del sitio
const lastmod = {};
for (const f of fs.readdirSync('src/content/posts').filter((f) => f.endsWith('.md'))) {
  const head = fs.readFileSync(`src/content/posts/${f}`, 'utf8').split('\n---', 2)[0];
  const get = (k) => (head.match(new RegExp(`^${k}:\\s*["']?([^"'\\n]+)`, 'm')) || [])[1];
  if (/^draft:\s*true/m.test(head)) continue; // los borradores no se publican
  const fecha = get('updated') || get('date');
  const cat = get('category');
  if (fecha && cat && !Number.isNaN(Date.parse(fecha)) && Date.parse(fecha) <= Date.now()) lastmod[`/${cat}/${f.replace(/\.md$/, '')}/`] = new Date(fecha).toISOString();
}

// Caja de Telegram a mitad de los artículos largos (antes del segundo subtítulo), para no depender del robot
const telegram = (fs.readFileSync('src/config.ts', 'utf8').match(/telegram:\s*'([^']+)'/) || [])[1];
function cajaTelegram() {
  return (tree, file) => {
    if (!telegram) return;
    // Las guías en inglés no llevan la caja (está en español)
    const ruta = String((file && (file.path || (file.history && file.history[0]))) || '');
    if (ruta.includes('/content/en/')) return;
    const h2 = tree.children.map((n, i) => (n.type === 'element' && n.tagName === 'h2' ? i : -1)).filter((i) => i >= 0);
    if (h2.length < 3) return;
    const t = (value) => ({ type: 'text', value });
    tree.children.splice(h2[1], 0, {
      type: 'element', tagName: 'aside', properties: { className: ['tg-callout'], dataPagefindIgnore: true },
      children: [{ type: 'element', tagName: 'p', properties: {}, children: [
        { type: 'element', tagName: 'strong', properties: {}, children: [t('¿No quieres perderte nada de GTA 6?')] },
        t(' Te avisamos de cada novedad al momento en nuestro '),
        { type: 'element', tagName: 'a', properties: { href: `https://t.me/${telegram}`, target: '_blank', rel: ['noopener'] }, children: [t('canal de Telegram')] },
        t('.'),
      ] }],
    });
  };
}

export default defineConfig({
  markdown: { rehypePlugins: [cajaTelegram] },
  site: 'https://zonaleonida.com',
  trailingSlash: 'always',
  integrations: [sitemap({
    filter: (page) => !page.includes('/buscar/') && !page.includes('/imagenes-oficiales/'),
    serialize: (item) => {
      const m = lastmod[new URL(item.url).pathname];
      return m ? { ...item, lastmod: m } : item;
    },
  })],
});
