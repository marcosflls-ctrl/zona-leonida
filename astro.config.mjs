import { defineConfig } from 'astro/config';
import sitemap from '@astrojs/sitemap';
import fs from 'node:fs';

// Fecha de última modificación de cada artículo (updated o date) para el mapa del sitio
const lastmod = {};
for (const f of fs.readdirSync('src/content/posts').filter((f) => f.endsWith('.md'))) {
  const head = fs.readFileSync(`src/content/posts/${f}`, 'utf8').split('\n---', 2)[0];
  const get = (k) => (head.match(new RegExp(`^${k}:\\s*["']?([^"'\\n]+)`, 'm')) || [])[1];
  const fecha = get('updated') || get('date');
  const cat = get('category');
  if (fecha && cat && !Number.isNaN(Date.parse(fecha))) lastmod[`/${cat}/${f.replace(/\.md$/, '')}/`] = new Date(fecha).toISOString();
}

export default defineConfig({
  site: 'https://zonaleonida.com',
  trailingSlash: 'always',
  integrations: [sitemap({
    filter: (page) => !page.includes('/buscar/'),
    serialize: (item) => {
      const m = lastmod[new URL(item.url).pathname];
      return m ? { ...item, lastmod: m } : item;
    },
  })],
});
