---
title: "[Tips]goqueryでクラス名などのアトリビュート部分一致をFind"
emoji: "🐥"
type: "tech" # tech: 技術記事 / idea: アイデア
topics: ["go", "golang"]
published: true
---

## この記事は何
Webサイトのスクレイピングをするときに、Go言語であれば`goquery`などのパッケージを使うことがありますね。そんな時、`<div class="wrapper_content__abcdef>`のような、`__`以降がビルドされるごとに変わるであろう要素を抽出するにはどうしたら？という記事です。

## 結論
CSSセレクタの前方一致でどうでしょう。ポイントは`div[class^="wrapper_content__"]`の部分です！

```go
package main

import (
	"fmt"
	"strings"

	"github.com/PuerkitoBio/goquery"
)

func main() {
	html := `<html>
  <body>
    <div class="whole_wrapper_content__xyz">
        <div>1</div>
        <div class="wrapper_content__abcdef">2</div>
        <div>3</div>
    </div>
  </body>
</html>
`
	doc, _ := goquery.NewDocumentFromReader(strings.NewReader(html))

    // 前方一致 ^= を使って、クラス名がwrapper_から始まるものを選ぶ
	sel := doc.Find(`div[class^="wrapper_content__"]`).First()
	fmt.Println(sel.Text())
}
```

playgroundはこちら。
https://go.dev/play/p/qBLHN6sJGc4

## もうあまり書くことはないけどメモ
`goquery`などのパッケージではCSSセレクタなどを使って要素を指定しますね。私自身は今まで`a#id`などの単純な指定しかしたことがなかったのですが、CSSセレクタをちゃんと理解すればもう少し高度な指定ができるんですね。

CSSセレクタ、不勉強なので詳しくないのですが、本記事に書いたような前方一致は以下に紹介されています。

MDN:属性セレクター
https://developer.mozilla.org/ja/docs/Web/CSS/Attribute_selectors

前方一致の他にも、大文字・小文字の扱いも指定できたりするんですね。

```css:MDNのサイトから引用
/* URL のどこかに "insensitive" が含まれるリンクで、
   大文字小文字は区別しない */
a[href*="insensitive" i] {
  color: cyan;
}
```

## おわりに
意外なところでCSSの勉強に繋がりました。奥が深い…！（浅い感想）