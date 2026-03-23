---
title: "[小ネタ] Claude Code の新しい対話型 `/init` は何をして何をしないのか"
emoji: "🐥"
type: "idea" # tech: 技術記事 / idea: アイデア
topics: ["claude", "claudecode"]
published: true
---

## はじめに
`CLAUDE_CODE_NEW_INIT=1` と環境変数を設定することで、Claude Code が対話的に`CLAUDE.md`を作成してくれるという情報をXで拝見しました。

@[tweet](https://x.com/oikon48/status/2035866646267740655?s=20)

たしかに公式ドキュメントの環境変数一覧にもデビューしています。
https://code.claude.com/docs/en/env-vars#:~:text=CLAUDE_CODE_NEW_INIT

> Set to true to make /init run an interactive setup flow. The flow asks which files to generate, including CLAUDE.md, skills, and hooks, before exploring the codebase and writing them. Without this variable, /init generates a CLAUDE.md automatically without prompting.

今までの初期化と何が異なるのか、また対話内容がプロジェクトの状態でどのように変わるのか実験しておきたいと思います。

## 想定読者
- Claude Code の機能追加に追いつきたいけど追いつけない忙しい人で、手っ取り早く`CLAUDE_CODE_NEW_INIT`を有効かすべきかどうか知りたい人。

## 前提条件
- Claude Code 2.1.81
  - Model: Opus 4.6 (1M)

## 実験内容
以下の3パターンを比較します。

| No. | CLAUDE_CODE_NEW_INIT | プロジェクトの状態 |
| --- | --- | --- |
| 1 | (未設定) | Next.js 16.1 初期化済み |
| 2 | 1 | 何も無し |
| 3 | 1 | Next.js 16.1 初期化済み |

:::message
Next.js は 16.2 から CLAUDE.md が同梱されるようになったので、16.1までを使用しておきます。
:::

## 実験結果の要約
`CLAUDE_CODE_NEW_INIT=1`を設定していると...

- 公式ドキュメント記載通り、`CLAUDE.md`以外にhooks, skillsをセットアップするかも質問される。
  - skillsの設定を頼むと、`/verify`という名前でlint, format等を設定するskillを提案される。
  - hooksの設定を頼むと、編集完了時にlint, format等を設定するhookを提案される。
    - 狙い通りにhooksを設定完了したか動作確認してくれようとするけど高確率で不発になるお茶目さあり。
- 対話形式でGitコミットの流儀なども聞かれる。
- プロジェクトにてlint, format設定をしていない場合には何を使うかも聞かれる。
  - ただし実際にパッケージを導入するようなこと(`ex) npm install`)は行われない。
- プロジェクトが初期化済みだと、その内容に沿って追加の質問をされる。(Next.jsだとServer Componentsを優先するか等)
- 設定完了後におすすめのplugin, skillsなどが紹介される。

総じて、`CLAUDE_CODE_NEW_INIT=1`にしてもデメリットはなく、特に初心者にとっては最低限のskills, hooksが作成される = 今後のお手本ができるのはメリットだと感じました。

## 実験結果詳細
### No.1: CLAUDE_CODE_NEW_INIT未設定かつプロジェクト初期化済み
- いままで通りの `/init` なので特筆する点はなし。

生成されたCLAUDE.md

```markdown
# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

- `npm run dev` - Start dev server (Next.js)
- `npm run build` - Production build
- `npm run start` - Start production server
- `npm run lint` - Run ESLint (flat config, `eslint.config.mjs`)

## Architecture

- **Framework**: Next.js 16 (App Router) with React 19, TypeScript (strict mode)
- **Styling**: Tailwind CSS v4 via `@tailwindcss/postcss` plugin
- **Path alias**: `@/*` maps to project root (configured in `tsconfig.json`)
- **App Router structure**: All routes live under `app/` directory
  - `app/layout.tsx` - Root layout (Geist font family)
  - `app/page.tsx` - Home page
  - `app/globals.css` - Global styles (Tailwind imports)
- **ESLint**: Flat config with `eslint-config-next` (core-web-vitals + typescript presets)

```
### No.2: CLAUDE_CODE_NEW_INIT=1かつプロジェクト何も無し
- 本当に何もファイルを置いていないリポジトリにて `/init` を実行。
- 以下のような質問が対話形式で実施された。
  - どのCLAUDE.mdファイルをセットアップしますか？ (プロジェクト / Personal / 両方)
  - スキルやフックも設定しますか？ (両方 / Skills only / Hooks only / CLAUDE.md only)
  - このプロジェクトの用途 (TypeScript / Webアプリケーション / ...)
  - パッケージマネージャー
  - test, lint, format ツールの好みはありますか？
  - コーディングスタイルやワークフローで特に守りたいルールはありますか？（例:コミットメッセージ規約、ブランチ戦略など）

質問に沿って答えれば、開発環境セットアップの初動が済むのは良いですね…！と思いきや、**これらの質問は本当にCLAUDE.mdの編集やhooks, skillsの設定のためだけなので、必要なパッケージのインストールなどはしてくれませんでした…！涙** これは勘違いしないでおきたいですね。。。

生成されたCLAUDE.md
```markdown
# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Web frontend sandbox project for experimentation and prototyping.

## Commands

- Package manager: `npm`
- Install: `npm install`
- Dev server: `npm run dev`
- Build: `npm run build`
- Lint: `npm run lint`
- Typecheck: `npm run typecheck`
- Test: `npm test`
- Format: `npx prettier --write .`

## Conventions

- Use Conventional Commits: `feat:`, `fix:`, `chore:`, `docs:`, `refactor:`, `test:`, `style:`, `perf:`
- Use TypeScript with strict mode
- Prefer `type` over `interface` for type definitions
- Use 2-space indentation
```

hooks, skills についても指示通りに作成が完了しています。（コードは割愛します）

一通りの作業が完了した段階で、おもむろにおすすめのplugins, skillsの紹介がありました。これは予想外。

```markdown
(1~3はプロジェクト初期設定が完了していないことに起因するアドバイスがありました、掲載割愛)
4. /plugin install skill-creator@claude-plugins-official — スキルの作成・改善を evals を使って効率化できます
5. /plugin install frontend-design@claude-plugins-official — Webフロントエンド開発で、洗練された UI をClaude が生成するためのデザイン原則を追加します
6. /plugin install playwright@claude-plugins-official — Claude が実際のブラウザを起動してスクリーンショットを撮り、ビジュアルバグを自分で修正できるようになります
7. /plugin で公式プラグインを一覧 — スキル、エージェント、フック、MCPサーバーがバンドルされたプラグインを探せます。カスタムプラグインの作成・共有も可能です
```

### No.3: CLAUDE_CODE_NEW_INIT=1かつプロジェクト初期化済み
- `npx create-next-app@16.1` を行ったリポジトリにて `/init` を実行。
  - この段階でlint, formatは設定済み。
- 以下のような質問が対話形式で実施された。
  - どのCLAUDE.mdファイルをセットアップしますか？ (プロジェクト / Personal / 両方)
  - スキルやフックも設定しますか？ (両方 / Skills only / Hooks only / CLAUDE.md only)
  - コミットメッセージやブランチ命名に決まったルールはありますか？
  - このプロジェクトで特に気をつけてほしいことや、Claudeに知っておいてほしいことはありますか？ (Server Components優先 / ...)

設定のスコープ、skills/hooksも含めるか、開発上のルール(コミットメッセージなど)については共通の質問でした。
また、初期セットアップが済んでいるからこそ、の質問も追加されています。

生成されたCLAUDE.md

```markdown
# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build & Lint Commands

- `npm run dev` — start dev server
- `npm run build` — production build
- `npm run lint` — run ESLint (Next.js config with core-web-vitals + TypeScript)

## Code Style

- Use Conventional Commits (feat:, fix:, chore:, refactor:, docs:, test:, etc.)
- TypeScript strict mode is enabled — do not use `any` or disable strict checks
- Path alias: `@/*` maps to the project root

## Architecture

- Next.js App Router only — do not use Pages Router
- Prefer React Server Components by default; only use `"use client"` when client-side interactivity is required
- Minimize client components — keep data fetching and rendering on the server where possible
- Tailwind CSS v4 for styling (PostCSS plugin, no tailwind.config file)

## Project Structure

- `app/` — Next.js App Router pages and layouts
- `public/` — static assets

Subdirectory CLAUDE.md files can be added for module-specific instructions as the project grows.
```

hooks, skills についても指示通りに作成が完了しています。（コードは割愛します）

この場合でも、先程のケースと同じようにおすすめのplugins, skillsの紹介がありました。

```markdown
1. /plugin install frontend-design@claude-plugins-official — フロントエンドコードの UIデザイン品質を向上させるプラグイン。React + Tailwind のプロジェクトに最適です
2. /plugin install playwright@claude-plugins-official — ブラウザを起動してスクリーンショットを撮り、視覚的なバグを自分で修正できるようになります
(3~4はプロジェクト固有の初期セットアップ未完了項目でした、掲載割愛)
5. /plugin install skill-creator@claude-plugins-official — スキルの作成・改善を eval 付きで行えるプラグイン。/skill-creator <skill-name> で使えます
6. /plugin — 公式プラグイン一覧を閲覧できます。Skills、Agents、Hooks、MCP サーバーをまとめて導入可能です
```

おすすめされるplugins, skillsは同じ顔ぶれですね。私以外の環境でも同じなのでしょうか。

## おわりに
`CLAUDE_CODE_NEW_INIT`の挙動を知りたかっただけなのですが、実験してみると意外に面白いですね。
所属会社内でClaude Codeの導入支援をしたりすることもあるのですが、その際はしれっと`CLAUDE_CODE_NEW_INIT=1`を設定しておこうと思います。

ただしプロジェクトの初期セットアップ(linterなどの導入)をしてから実施しないと、「質問に答えたから一通りセットアップ済みじゃないの？」という罠を踏みそうなことも分かったので、実施順序に留意する必要はありそうだと気づけました。みなさんもお気をつけて。