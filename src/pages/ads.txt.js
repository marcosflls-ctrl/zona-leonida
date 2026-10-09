import { SITE } from '../config';

// ads.txt para AdSense: se rellena solo con el código de cliente de src/config.ts (adsenseClient: 'ca-pub-...')
export function GET() {
  const pub = (SITE.adsenseClient || '').replace(/^ca-/, '');
  const body = pub ? `google.com, ${pub}, DIRECT, f08c47fec0942fa0\n` : '# Pendiente de AdSense\n';
  return new Response(body, { headers: { 'Content-Type': 'text/plain; charset=utf-8' } });
}
