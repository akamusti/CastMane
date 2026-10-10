// @ts-check
import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';

// https://starlight.astro.build/reference/configuration/
export default defineConfig({
  site: 'https://akamusti.github.io',
  base: '/CastMane/',
  integrations: [
    starlight({
      title: 'CastMane',
      logo: {
        src: './src/assets/logo.png',
        alt: 'CastMane logo',
      },
      social: [
        {
          icon: 'github',
          label: 'GitHub',
          href: 'https://github.com/akamusti/CastMane',
        },
        {
          icon: 'x.com',
          label: 'X (Twitter)',
          href: 'https://x.com/CastManeRecord',
        },
      ],
      defaultLocale: 'root',
      locales: {
        root: {
          label: 'English',
          lang: 'en',
        },
        tr: {
          label: 'Türkçe',
          lang: 'tr',
        },
      },
      sidebar: [
        {
          label: 'Start Here',
          translations: { tr: 'Başlangıç' },
          items: [
            { slug: 'getting-started/installation' },
            { slug: 'getting-started/usage' },
          ],
        },
        {
          label: 'Guides',
          translations: { tr: 'Rehberler' },
          items: [
            { slug: 'guides/crash-safety' },
            { slug: 'guides/configuration' },
            { slug: 'guides/audio' },
            { slug: 'guides/troubleshooting' },
          ],
        },
        {
          label: 'Reference',
          translations: { tr: 'Referans' },
          items: [{ slug: 'reference/architecture' }],
        },
        {
          label: 'Legal',
          translations: { tr: 'Yasal' },
          items: [{ slug: 'legal/privacy' }],
        },
      ],
    }),
  ],
});
