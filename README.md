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
  Nunca copia fotos de otros medios. Si no hay imagen oficial, elige una **ilustración propia del banco** (`public/img/banco/`) según el tema de la noticia, rotando para no repetir. Los temas y sus imágenes están en `scripts/banco.json`; para añadir más, guarda `tema-N.webp` en esa carpeta y añádela a la lista. En rumores siempre usa una de "misterio".
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
4. **Conexión con Claude (sin clave)**: el robot usa la *federación de identidades*. En la Claude Console
   (*Settings → Identidad de carga de trabajo*) está la regla `robot-zona-leonida`, que solo acepta ejecuciones
   de este repositorio en la rama `main`. Los identificadores están en `.github/workflows/radar.yml`.
   No hay que guardar ninguna clave en GitHub.
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

## Galería oficial de Rockstar

- `scripts/galeria.json` lista las imágenes del kit de prensa oficial (rockstargames.com/VI/media), etiquetadas por personaje o zona (`refs`).
- La tarea **Galería oficial de Rockstar** (Actions) las descarga a `public/img/oficial/`. Se ejecuta sola al cambiar `galeria.json`; también a mano.
- El robot añade a cada noticia (salvo rumores) la imagen oficial del personaje o lugar del que trata, con el crédito "Imagen: Rockstar Games". Si no encaja ninguna, usa las ilustraciones propias.
- Las noticias de Rockstar se leen de la API del Newswire (la web ya no tiene RSS), en español y con su imagen oficial; solo las de la última semana con la etiqueta de GTA VI.

## Día del lanzamiento (19 de noviembre)

Hay 8 plantillas en borrador (`draft: true`) que no aparecen en la web: trucos, cómo ganar dinero, misiones, cuánto dura, mejores coches, secretos, controles y trofeos. Para publicar cada una:

1. Rellenar los comentarios `<!-- RELLENAR -->` con datos comprobados y borrarlos.
2. Añadir las fuentes en `sources`, cambiar `draft: true` por `draft: false` y poner la fecha real en `date` y `updated`.
3. Al ser un archivo que ya existía, Telegram no lo publica solo: lanzar la tarea **Telegram** a mano con el nombre del archivo.

## Imágenes rápidas, buscador y test

- `python scripts/miniaturas.py` crea las versiones de 400 y 800 px de las imágenes (el robot y la galería ya lo hacen solos). Si añades imágenes a mano a `public/img/banco/`, ejecútalo.
- El buscador (`/buscar/`) usa Pagefind: se genera solo al publicar (`npm run build`). Indexa artículos y fichas de personajes; la configuración está en `pagefind.yml`.
- El test de personajes está en `src/pages/test-que-personaje-eres.astro` (preguntas y puntuación arriba del archivo).

## Galería oficial automática

La tarea **Galería oficial (revisión diaria)** mira dos veces al día el kit de prensa de Rockstar. Si hay capturas nuevas, las clasifica (las de un personaje o lugar nuevo van a un grupo nuevo), las descarga, las publica en `/imagenes-oficiales/` y en las fichas de personajes, y avisa en el canal de Telegram. Si de golpe apareciesen más de 60, no toca nada (sería un cambio en la web de Rockstar, no imágenes nuevas).

## Imágenes en las guías del lanzamiento

Por orden de preferencia: vídeo de YouTube insertado en el minuto exacto, gráfico propio, captura de la comunidad con permiso, imagen oficial. Nunca fotogramas recortados de vídeos de otros.

Para insertar un vídeo en cualquier artículo (empieza en el segundo indicado y cita al canal):

```html
<figure class="yt-guia" data-id="ID_DEL_VIDEO" data-inicio="2:05" data-autor="Nombre del canal"></figure>
```

Las capturas de lectores llegan por `/envia-tu-captura/` (correo o X), con autorización expresa para publicarlas con su nombre.

## Noticia urgente: redactar ya un enlace concreto

En GitHub → Actions → «Radar de noticias GTA VI» → «Run workflow»: pega el enlace de la noticia en el campo y pulsa el botón verde. El robot la redacta al momento (aunque no sea de sus fuentes) y abre la propuesta para revisar como siempre. Si el campo se deja vacío, revisa todas las fuentes sin esperar a las 3 horas. También se puede hacer desde la app de GitHub en el móvil.

## Modo lanzamiento (desde el 18 de noviembre)

Además de noticias, el robot busca descubrimientos de la comunidad (Reddit r/GTA6 y r/GTA, y canales de YouTube de GTA) y **amplía las guías** (secretos, trucos, coches, dinero, misiones, trofeos, controles, mapa) en una sección «Últimos descubrimientos», con crédito a quien lo encontró, su vídeo en el minuto exacto y la marca «⚠️ Sin comprobar» hasta que se confirme. Llega en la misma propuesta para revisar. Fuentes y fecha de activación en `scripts/feeds.json` → `comunidad`. Para probarlo antes sin escribir nada: «Run workflow» con la casilla «Probar el modo lanzamiento».

## Avisos privados por Telegram

- Si el radar, la galería o la publicación en el canal fallan, el bot te escribe en privado con el enlace al error.
- Cada noche (21:47 en verano) te manda un resumen: cuántas veces ha funcionado el radar, fallos y propuestas pendientes.
- Para activarlo: escribe /start a tu bot en Telegram, consigue tu número de chat (por ejemplo con @userinfobot) y guárdalo en GitHub → Settings → Secrets and variables → Actions como `TELEGRAM_AVISOS_CHAT_ID`.

## Google Discover y Google News

- Google ya no admite solicitudes: incluye las webs automáticamente si cumplen sus requisitos.
- La web ya tiene lo técnico: imágenes de 1600 px con vista previa grande, datos estructurados con logo y fechas, `sitemap-news.xml` (noticias de los últimos 2 días) y página de transparencia (Sobre nosotros).
- En Search Console, envía también `sitemap-news.xml` en Sitemaps.

## Carruseles para Instagram y TikTok

- Al publicarse un artículo nuevo, la IA escribe titular, 3 puntos clave, texto, hashtags y un tuit sugerido (con su respuesta y el enlace); se genera un carrusel de 5 imágenes (1080×1350) con el diseño de la marca y llega por Telegram en privado, junto con el texto para copiar.
- Variedad: etiqueta según el tipo (OFICIAL, ÚLTIMA HORA, RUMOR, FILTRACIÓN, DESMENTIDO, ANÁLISIS, GUÍA, TRUCO, DESCUBRIMIENTO), paleta neón por sección (rosa noticias, turquesa guías, verde trucos, dorado descubrimientos) y 3 composiciones de portada que se alternan (`--diseno 0|1|2` para forzar una).
- Cada mañana (10:37) comprueba si toca portada de cuenta atrás: 60, 50, 45, 40, 35, 30, 25, 21, 20, 15, 14, 12 y 10 días, y todos los días de la última semana.
- A mano: Actions → «Carruseles para Instagram y TikTok» → Run workflow (modo `noticia` con el archivo, o `cuenta-atras`).
- Probar en local sin IA: `python scripts/redes.py noticia src/content/posts/<archivo>.md --sin-ia --no-enviar` (salen en `redes-salida/`).
