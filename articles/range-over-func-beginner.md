---
title: "【Go】range over func入門ドリル"
emoji: "🔰"
type: "tech" # tech: 技術記事 / idea: アイデア
topics: ["go"]
published: false
---

## この記事は何
Go1.23から正式に導入される`range over func`、Go1.22で実験的に導入された頃から数えると、結構な時間が経ちましたね。既に慣れ親しんでいる方も多くいらっしゃると思いますが、**恥ずかしながら私はまだです…。**お作法を理解できていないのと、体に覚え込ませられていないのと、両方が原因かと思います。

これではいけない！と、最近、一念発起して`range over func`に向き合ってみたので、私と同じようになかなか慣れられない方向けに記事を書きたいと思います。

## この記事の対象読者
- Goの基本は履修済みだけど、`range over func`まだ全然慣れてない！というGopher。

## 前提
- GoのバージョンはGo1.23rc2であるとします。

## この記事の構成
「**まず覚えること**」と「**体が覚えるまで様々な例にトライすること**」の二本柱で進めたいと思います。

なお、ここからはストーリーテラーとして「ごふちゃん」を召喚してみます。

![gofu.png](/images/go-images/gofu.png)

:::message
このキャラクターはRenee Frenchが著作権を保持するGopherのコンテンツをベースに著者が作成したものであり、クリエイティブ・コモンズの表示3.0のライセンス(the Creative Commons 3.0 Attribution License)に記載の条件のもとで使用しています。http://creativecommons.org/licenses/by/3.0/ https://go.dev/doc/gopher/README
:::
