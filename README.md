# Zona Leonida — web de GTA VI

Web estática (Astro) + robot que busca noticias y redacta borradores con IA cada 3 horas.

## Cómo funciona

```
Cada 3 h  →  GitHub Actions ejecuta scripts/radar.py
          →  lee los feeds (scripts/feeds.json) y filtra lo que habla de GTA VI
          →  descarta lo repetido y lo que ya está publicado
          →  Claude redacta un artículo ORIGINAL con fuente enlazada
          →  te llega una "pull request" con los borradores
Tú        →  la revisas en la app de GitHub y pulsas "Merge"
Cloudflare→  detecta el cambio y publica la web en ~1 minuto
```

## Imágenes, vídeos y filtraciones

- **Imagen principal**: el robot solo descarga la imagen cuando la fuente es la propia Rockstar
  (`OFFICIAL_IMAGE_DOMAINS` en `radar.py`) y añade el crédito "Imagen: Rockstar Games".
  Nunca copia fotos de otros medios. Si no hay imagen oficial, se usa la portada de la categoría (`public/img/portadas/`).
- **Vídeos y tuits**: incrusta como mucho 2, y solo de cuentas oficiales (canal de YouTube "Rockstar Games", @RockstarGames).
- **Filtraciones**: la IA las cuenta con sus palabras citando al medio, sin describir el material como si lo viera ni compararlo con imágenes oficiales. Si viene de un hackeo, solo lo general. En estos artículos no se incrustan vídeos y la imagen oficial se marca como "no forma parte de la filtración". Llevan la etiqueta **Rumor**
  y un aviso de "Información sin confirmar". Nunca enlaza ni muestra el material filtrado.
- **Tus capturas** (desde el lanzamiento): guárdalas en `public/img/` y ponlas en el campo `image:` del artículo,
  con `imageCredit: "Zona Leonida"`.

## Dónde se cambia cada cosa

| Qué | Archivo |
|---|---|
| Nombre, dominio, AdSense, fecha de la cuenta atrás | `src/config.ts` (y el dominio también en `astro.config.mjs`) |
| Artículos | `src/content/posts/*.md` (uno por archivo) |
| Fuentes que vigila el robot | `scripts/feeds.json` |
| Instrucciones de redacción de la IA | `SYSTEM` en `scripts/radar.py` |
| Cada cuánto se ejecuta | `cron` en `.github/workflows/radar.yml` |
| Correo de contacto y datos legales | `src/pages/contacto.astro`, `aviso-legal.astro`, `privacidad.astro` |

### Formato de un artículo

```markdown
---
title: "Titular (50-70 caracteres)"
description: "Entradilla que sale en Google (130-160 caracteres)"
date: 2026-10-09T10:00:00+02:00     # si pones una fecha futura, se publica ese día
category: noticias                  # noticias | guias | trucos | descubrimientos
tags: [mapa, vice-city]
image: /img/mi-imagen.webp          # opcional, guárdala en public/img/
sources:
  - name: "Medio: titular original"
    url: "https://..."
---

Texto en Markdown con subtítulos ## ...
```

## Puesta en marcha (una sola vez)

1. **GitHub**: crea una cuenta y un repositorio privado, y sube esta carpeta (lo más fácil: GitHub Desktop).
2. **Cloudflare Pages** (gratis): *Workers & Pages → Create → Pages → Connect to Git*, elige el repositorio.
   Preset: **Astro** · Build command: `npm run build` · Output: `dist`.
3. **Dominio**: cómpralo (Cloudflare o Hostinger, ~10 €/año), añádelo en *Custom domains* y cámbialo en `src/config.ts` y `astro.config.mjs`.
4. **Clave de IA**: crea una API key en console.anthropic.com y guárdala en GitHub:
   *Settings → Secrets and variables → Actions → New repository secret* → nombre `ANTHROPIC_API_KEY`.
5. **Permiso del robot**: *Settings → Actions → General → Workflow permissions* → marca
   **Read and write** y **Allow GitHub Actions to create and approve pull requests**.
6. **Probar**: pestaña *Actions → Radar de noticias GTA VI → Run workflow*. En el registro verás cuántas entradas ha leído de cada feed (si alguna da 0, esa URL no vale y hay que cambiarla).
7. **Reconstrucción diaria** (opcional, para artículos programados): en Cloudflare *Settings → Builds → Deploy hooks* crea un hook y guárdalo en GitHub como secreto `CF_DEPLOY_HOOK`.

## SEO

- Ya incluido: sitemap (`/sitemap-index.xml`), RSS, `robots.txt`, URLs limpias, etiquetas canónicas, Open Graph, datos estructurados (NewsArticle, Breadcrumb), enlaces internos y artículos relacionados.
- Al publicar: da de alta la web en **Google Search Console** y **Bing Webmaster Tools** y envía el sitemap.
- Cuando tengas unas semanas de noticias propias y regulares, solicita la entrada en **Google News** (Publisher Center).

## AdSense

1. Rellena antes los datos de `aviso-legal`, `privacidad` y `contacto` (AdSense los revisa).
2. Solicítalo con 20-30 artículos de calidad publicados.
3. Al aprobarte: pon tu `ca-pub-...` en `src/config.ts` y crea `public/ads.txt` con la línea que te da AdSense.
4. **Obligatorio en España/UE**: en AdSense → *Privacidad y mensajes* activa el mensaje de consentimiento (RGPD). Es la plataforma certificada de Google y gratuita.

## Modo automático (sin revisión)

Crea una variable (no secreto) `AUTO_PUBLISH` = `true` en *Settings → Secrets and variables → Actions → Variables*.
⚠️ No recomendado al principio: Google penaliza el contenido de IA publicado en masa sin revisión y AdSense puede rechazar la web.

## Probar en tu ordenador

```bash
npm install
npm run dev          # http://localhost:4321
python scripts/radar.py --dry-run   # ver qué noticias encontraría, sin gastar IA
```
