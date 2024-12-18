---
title: "【Go】Markdownを変換して、画像まで埋め込んだ単一HTMLファイルを生成【goldmark】"
emoji: "🪆"
type: "tech" # tech: 技術記事 / idea: アイデア
topics: ["go", "goldmark", "markdown"]
published: true
---

## この記事は何
:::message
この記事は`goldmark`用の自作拡張機能の使い方説明記事です。
:::

日々、多くの方がドキュメントの作成にMarkdownを利用しているかと思います。Markdownはシンプルで読み書きしやすくGoodですね。**しかし、Markdownファイルは誰もが閲覧できるとは限りません**。せっかく書いたドキュメントも、それを届けたい相手に読んで貰えなければどうしようもありませんね？したがってMarkdownからPDFやHTMLを生成する多くの方法が生み出されているわけですが、本記事は**画像も含めて単一HTMLファイルで書き出したい！という熱意を胸に、Base64エンコードした画像を埋め込んだHTMLを生成する方法**をまとめます。
具体的には、Go製のMarkdownパーサーである`goldmark`と、その拡張機能の1つで画像をBase64でエンコードしてHTMLに埋め込む`goldmark-img64`を用いて、Markdownファイルを画像埋め込み済みのHTMLに変換する方法を示します。

:::message
yuinさんの`goldmark`は`Hugo`にも利用されているMarkdownパーサーです！かっこいい😎
:::

拡張機能`goldmark-img64`は、まさしく私自身がMarkdownから変換した単一HTMLファイルを配りたい！と思った時に作成したものです。一度完成してから特に手入れをしていなかったのですが、最近まさかのプルリクエストを頂いたことをきっかけに若干の機能拡張とリファクタリングを行いました。今年やったことは今年のうちに…というモチベーションで、この拡張機能の使い方や例をまとめました。

`goldmark`
https://github.com/yuin/goldmark

`goldmark-img64`
https://github.com/tenkoh/goldmark-img64

## この記事の対象読者
- Markdownファイルを変換し、画像まで埋め込んだHTMLを生成したい方
- `goldmark`ユーザー

### この記事で扱わないこと
- Go言語の環境構築や基本的な使い方

では、いよいよ本題に入ってまいります！

## Markdownから画像を埋め込んだHTMLを生成する
ローカルのディレクトリ内に次のようなMarkdownファイルと、参照されている画像が保存されているとします。
```markdown:target.md
![gopherのイラスト](./image/gopher.png)
```

ディレクトリ内で以下のGoのコードを実行するだけで、Base64エンコードした画像が埋め込まれたHTMLが生成されます。

```go:main.go
package main

import (
    "io"
    "os"

    "github.com/yuin/goldmark"
    img64 "github.com/tenkoh/goldmark-img64"
)

func main() {
    b, _ := os.ReadFile("target.md")
    goldmark.New(goldmark.WithExtensions(img64.Img64)).Convert(b, os.Stdout)
    // got: <p><img src="data:image/png;base64,{データ列...}" alt="gopherのイラスト"></p>
}
```

`goldmark`は機能拡張が容易なことをコンセプトとされており、上例のようにサクッと拡張機能を使った実装が可能です。

さて、`goldmark-img64`拡張機能はいくつかオプションを使うことでより実践的になります。オプションを使わないデフォルトの状態では、以下のような制約を設けたためです。

| 制約 | 制約の背景 |
| --- | --- |
| 変換実行ファイルとMarkdownファイル&参照される画像は同一ディレクトリ内にあるか、あるいは絶対パスだけが使われていること。 | Markdownファイル内の画像パスを一意に特定できないため。ユーザーに指定してもらうしかない。 |
| インターネット上のファイル等は読み込まない。 | セキュリティの確保。またどのような通信設定(例えばタイムアウト)をするかはユーザーに指定してもらうしかない。 |

これらの制約を緩和するにはオプションが必要です。アレンジレシピと称して2つのオプションを見てみましょう。

:::message
この記事を書いていて、「これ普通にリポジトリにexampleとして追加した方が良いな…。」と思ったので、後で追加します…。
:::

### アレンジレシピ1: 任意の場所のMarkdownファイルを処理する。
`goldmark-img64`には`WithPathResolver`というオプションを用意してあり、これは画像ファイルパスを加工する`func(string) string`というシンプルな関数を受け取るものです。このオプションにより、例えばディレクトリ`~/foo`にあるMarkdownファイルを読み込んだ時に、その中にある`./path/to/image.png`のようなファイルパスを`~/foo/path/to/image.png`に置き換えて処理することができます。

コードを交えてもう少し具体例を紹介します。次のような呼び出し方をするCLIを考えてみましょう。仮にCLIの実行ファイル名を`imgembed`としますね。

```sh
imgembed ~/foo/document.md
```

このCLIは以下のようなソースコードで実現可能です。(エラーハンドリングは記事の読みやすさを重視して割愛しています。ご了承ください。)

```go:main.go
package main

import (
	"fmt"
	"os"
	"path/filepath"

	img64 "github.com/tenkoh/goldmark-img64"
	"github.com/yuin/goldmark"
)

func main() {
	// 引数として処理対象のMarkdownファイルのパスを取得する。例: ./path/to/markdown.md
	if len(os.Args) != 2 {
		panic("markdown file path is required as an argument")
	}

	mdPath, _ := filepath.Abs(os.Args[1])
	parentPath := filepath.Dir(mdPath)

	b, _ := os.ReadFile(mdPath)

	md := goldmark.New(
		goldmark.WithExtensions(img64.Img64),
		goldmark.WithRendererOptions(
			// Markdownファイル内の画像パスを弄るオプション。PathResolver: func(string) string型の関数を受け取る。
			img64.WithPathResolver(
				// 単一の親ディレクトリのパスをプレフィックスとして付与するビルトインのResolver
				img64.ParentLocalPathResolver(parentPath),
			),
		),
	)

	md.Convert(b, os.Stdout)
}
```

この例では`WithPathResolver`に`ParentLocalPathResolver`というビルトインの関数を渡しています。これにより、Markdownファイルが保存されているディレクトリの絶対パスを各画像のファイルパスに付与し、画像を適切に参照できるようにしています。ビルトインの関数以外にもユーザーが作成した任意の関数を与えることができるため、ユースケースに応じて柔軟な設定が可能です。

### アレンジレシピ2: 外部の画像ファイルも読み込む
もう１つのオプションとして`WithFileReader`を用意しています。このオプションを使うことでMarkdownファイルも画像ファイルもインターネット上にあるようなユースケースに対応できるようになります。`WithFileReader`オプションは、`func(path string) ([]byte, error)`型の関数を受け取るもので、デフォルトではローカルファイルのパスを受け取ってファイル内容を読み出した`[]byte`を返しますが、これを拡張することでさまざまなファイルの読み込みに対応します。

例として、GitHubにあるMarkdownファイルを処理してみましょう。次のように呼び出して処理するイメージです。
```
imgembed https://raw.githubusercontent.com/tenkoh/zenn-content/refs/heads/main/articles/range-over-func-beginner.md
```

上記のMarkdownファイルが参照する画像ファイルは`/main/images`配下にあるため、先ほどの例と同じようにパスを解決する必要があります。この例だけでなく、インターネット上のファイルを扱う場合には同じような状況になることが多く、基本的には先ほどの`WithPathResolver`をセットで使うことになるでしょう。

:::message
ぶっちゃけ`WithFileReader`の中でもパスの解決もできるのですが、責務を分ける意味合いで2つのオプションを併用することをお勧めします。`WithPathResolver`でパスを修正した後に`WithFileReader`でファイルを読み込む流れとなります。
:::

以下が、サンプルケースに対応するコード例です。

```go:main.go
package main

import (
	"io"
	"net/http"
	"net/url"
	"os"
	"path"
	"time"

	img64 "github.com/tenkoh/goldmark-img64"
	"github.com/yuin/goldmark"
)

// Markdown中の画像ファイルパスに、{root}をつけて返す関数を生成
func remotePathResolver(root url.URL) img64.PathResolver {
	return func(s string) string {
		url.Path = path.Join(url.Path, s)
		return url.String()
	}
}

func main() {
	// 引数として処理対象のMarkdownファイルのパスを取得する。例: https://example.com/document.md
	if len(os.Args) != 2 {
		panic("remote markdown filepath must be specified")
	}

	mdPath := os.Args[1]
	root, err := url.Parse(mdPath)
	if err != nil {
		panic(err)
	}
    
	// https://example.com/root/articles/document.md のようなURLから、rootの部分までを抜き出す。
	// 何をルートとするかはケースバイケースなので、これは本当にただの例。
	root.Path = path.Dir(path.Dir(root.Path))

	// Markdownファイルを取得して読み込み
	client := &http.Client{
		Timeout: 5 * time.Second,
	}
	resp, _ := client.Get(mdPath)
	defer resp.Body.Close()

	b, _ := io.ReadAll(resp.Body)

    
	// HTMLファイルとして書き出す
	md := goldmark.New(
		goldmark.WithExtensions(img64.Img64),
		goldmark.WithRendererOptions(
			img64.WithPathResolver(remotePathResolver(*root)),
			img64.WithFileReader(
				// インターネットファイルを取得可能なビルトインのFileReaderを使う
				img64.AllowRemoteFileReader(client),
			),
		),
	)

	md.Convert(b, os.Stdout)
}
```

この例では`WithFileReader`に`AllowRemoteFileReader`というビルトインの関数を渡しています。インターネット上から画像をダウンロードするにも、タイムアウト等の設定はユーザーがケースバイケースで設定すべきですので、`*http.Client`をDIするような作りにしています。`FileReader`を様々に用意することで、例えばS3のバケット内のファイルを取得する、というような様々な拡張が可能です。

## おわりに
カスタム次第で意外となんでもできる拡張機能になりました。この記事のはじめに書いたように、画像まで埋め込んだ単一HTMLファイルを配布したい、という場面はちらほらあるかと思うので、ぜひ使ってみて頂けると嬉しいです。また、「こんなCLIを配布しておいてほしい」「こんな機能が欲しい」と言ったIssueやPullRequestも大歓迎ですので、どうぞよろしくお願いいたします。
