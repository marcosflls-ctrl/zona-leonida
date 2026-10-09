import { defineConfig } from 'astro/config';
import sitemap from '@astrojs/sitemap';

export default defineConfig({
  site: 'https://zonaleonida.com', // ← cambia por tu dominio
  trailingSlash: 'always',
  integrations: [sitemap()],
});
