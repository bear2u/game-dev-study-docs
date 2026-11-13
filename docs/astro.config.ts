import { defineConfig } from "astro/config";
import tailwindcss from "@tailwindcss/vite";
import nimbus, {
  defineConfig as defineNimbusConfig,
} from "@cloudflare/nimbus-docs";
import { tableScroll } from "@cloudflare/nimbus-docs/markdown";

const siteUrl = process.env.SITE_URL || "https://example.github.io";
const basePath = process.env.BASE_PATH || "/";

const nimbusConfig = defineNimbusConfig({
  site: siteUrl,
  title: "사쿠라이 마사히로의 게임 만드는 법",
  description:
    "桜井政博のゲーム作るには(사쿠라이 마사히로의 게임 만드는 법) 강의 한국어 번역, 핵심 요약 및 다이어그램 학습 노트",
  locale: "ko",
  github: "https://github.com/bear2u/game-dev-study-docs",
  socialImageAlt: "사쿠라이 마사히로의 게임 만드는 법 학습 문서",
  sidebar: {
    items: [
      "index",
      {
        label: "카테고리 핵심 정리",
        autogenerate: { directory: "guides" },
      },
      {
        label: "A. 일의 자세 (1~19강)",
        autogenerate: { directory: "lectures/a-work-attitude" },
      },
    ],
  },
});

export default defineConfig({
  site: siteUrl,
  base: basePath,
  output: "static",
  vite: {
    plugins: [tailwindcss()],
  },
  prefetch: {
    prefetchAll: true,
    defaultStrategy: "hover",
  },
  integrations: [
    nimbus(nimbusConfig, {
      rules: {
        "nimbus/frontmatter-shape": "error",
        "nimbus/internal-link": "error",
      },
      markdown: {
        hastPlugins: [tableScroll()],
        features: { headingAttributes: true },
      },
    }),
  ],
});
