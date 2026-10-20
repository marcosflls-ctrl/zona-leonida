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
    rumor: z.boolean().default(false),
    pilar: z.boolean().default(false),
    cuentaAtras: z.boolean().default(false),
    comparadorPrecio: z.boolean().default(false), // tabla «¿dónde sale más barato al cambio de hoy?» (guía de precios) // muestra la cuenta atrás por país (guía de la hora de salida) // página de referencia que se mantiene actualizada
    orden: z.number().default(99),
    // Productos recomendados (enlaces de afiliado). busqueda = texto que se busca en Amazon.
    compras: z.array(z.object({ nombre: z.string(), busqueda: z.string(), nota: z.string().optional() })).default([]),       // orden en el bloque "Lo esencial"  // filtración o rumor sin confirmar → etiqueta visible
    sources: z.array(z.object({ name: z.string(), url: z.string().url() })).default([]),
    draft: z.boolean().default(false),
  }),
});

// Guías en inglés (/en/). `es` es la dirección de la guía equivalente en español, para las etiquetas hreflang.
const en = defineCollection({
  loader: glob({ pattern: '**/*.md', base: './src/content/en' }),
  schema: z.object({
    title: z.string().max(110),
    description: z.string().max(170),
    date: z.coerce.date(),
    updated: z.coerce.date().optional(),
    es: z.string().optional(),
    orden: z.number().default(99),
    image: z.string().optional(),
    imageAlt: z.string().optional(),
    imageCredit: z.string().optional(),
    sources: z.array(z.object({ name: z.string(), url: z.string().url() })).default([]),
    draft: z.boolean().default(false),
  }),
});

export const collections = { posts, en };
