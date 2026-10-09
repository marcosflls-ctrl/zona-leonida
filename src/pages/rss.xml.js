import rss from '@astrojs/rss';
import { SITE } from '../config';
import { getPublishedPosts } from '../lib/posts';

export async function GET(context) {
  const posts = await getPublishedPosts();
  return rss({
    title: SITE.name,
    description: SITE.tagline,
    site: context.site,
    items: posts.slice(0, 50).map((p) => ({
      title: p.data.title,
      description: p.data.description,
      pubDate: p.data.date,
      link: `/${p.data.category}/${p.id}/`,
    })),
    customData: '<language>es</language>',
  });
}
