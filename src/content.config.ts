import { defineCollection, z } from 'astro:content';
import { glob } from 'astro/loaders';

const posts = defineCollection({
  loader: glob({ pattern: '**/*.md', base: './src/content/posts' }),
  schema: z.object({
    title: z.string().max(110),
    description: z.string().max(170), // meta description para Google
    date: z.coerce.date(),
    updated: z.coerce.date().optional(),
    category: z.enum(['noticias', 'guias', 'trucos', 'descubrimientos']),
    tags: z.array(z.string()).default([]),
    image: z.string().optional(),
    imageAlt: z.string().optional(),
    imageCredit: z.string().optional(), // ej. "Rockstar Games"
    rumor: z.boolean().default(false),  // filtración o rumor sin confirmar → etiqueta visible
    sources: z.array(z.object({ name: z.string(), url: z.string().url() })).default([]),
    draft: z.boolean().default(false),
  }),
});

export const collections = { posts };
