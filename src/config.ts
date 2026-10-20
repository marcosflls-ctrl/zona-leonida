// ⚙️ CONFIGURACIÓN GENERAL — cambia aquí el nombre, dominio y AdSense
export const SITE = {
  name: 'Zona Leonida',
  tagline: 'Noticias, guías y trucos de GTA 6 (GTA VI) en español',
  url: 'https://zonaleonida.com', // ← tu dominio definitivo (también en astro.config.mjs)
  lang: 'es',
  locale: 'es_LA',
  author: 'Redacción Zona Leonida',
  email: 'contacto@zonaleonida.com',
  // Datos legales del titular (aviso legal y privacidad)
  ownerName: 'Marcos Fernández León',
  ownerNif: '48158108H', // si lo dejas vacío, no se muestra
  // Fecha de lanzamiento usada por la cuenta atrás (hora peninsular)
  launchDate: '2026-11-19T00:00:00+01:00',
  // AdSense: pega tu ID de editor cuando te aprueben (ej. 'ca-pub-1234567890123456').
  // Mientras esté vacío, no se carga ningún anuncio.
  adsenseClient: 'ca-pub-2093028838178784',
  // Cloudflare Web Analytics (sin cookies): pega aquí el token cuando lo crees en Cloudflare.
  cfAnalyticsToken: '',
  // Redes sociales
  social: { x: 'ZonaLeonida', telegram: 'zonaleonida', instagram: 'zonaleonidavi', tiktok: '' },
  // Afiliados: pega tu ID de Amazon Afiliados (termina en -21). Mientras esté vacío no se muestran enlaces.
  amazonTag: 'zonaleonida-21',
};

export const CATEGORIES = {
  noticias: { label: 'Noticias', desc: 'Últimas noticias de GTA 6: fechas, tráilers, filtraciones confirmadas y anuncios oficiales.' },
  guias: { label: 'Guías', desc: 'Guías completas de GTA 6: misiones, coleccionables, mapa, personajes y mucho más.' },
  trucos: { label: 'Trucos', desc: 'Todos los trucos y códigos de GTA 6 para PS5 y Xbox Series, y consejos para jugar mejor.' },
  descubrimientos: { label: 'Descubrimientos', desc: 'Secretos, easter eggs, detalles ocultos y lugares reales de Florida descubiertos en GTA 6.' },
} as const;

export type CategoryKey = keyof typeof CATEGORIES;
