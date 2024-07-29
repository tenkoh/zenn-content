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

## この記事で扱うこと、扱わないこと
- `range over func`の導入に至る背景や解決したい課題に関する説明は行いません。
- `range over func`を使ってみよう！と意気込めるように、最低限押さえておきたいポイントを筆者の主観ベースでまとめた内容を紹介します。本機能の設計意図などを完璧に汲んだ説明は目指しておらず、**あくまで「使い始める」を目標にした入門ドリルの位置付け**です。

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

## まず覚えること
ごふちゃん「今日勉強する`range over func`だけど、まずは『**これはこういうものだ！**』と覚えないと始まらないことがいくつかあるよ。いっしょに確認してみよう。」

### rangeにfunc??
ごふちゃん「これまでの`range`の使い方といえばこういう感じだよね。」

```go
for i, v := range []int{100, 200, 300} {
    fmt.Printf("iteration:%d, value:%d\n", v)
}
// example
// iteration:0, value:100
// iteration:1, value:200
// iteration:2, value:300
```

ごふちゃん「なんでこの構文でこういうことができるんだろう？っていうのは、正直『そういうものだよね』って覚えちゃうしかないよね。`range over func`も同じ位置付けで、まずそういうもんだ！と覚えちゃうしかないよ！私のおすすめはGo Specの表をまずじーっと眺めてみることかなぁ。」

https://github.com/golang/go/blob/c9940fe2a9f2eb77327efca860abfbae8d94bf28/doc/go_spec.html#L6664-L6673

- `range func(func() bool)`は値を何も返さない。`for range ...`みたいな感じで使うんだね。
- `range func(func(V) bool)`はVを返す。`for x := range ...`みたいな感じで使うんだね。
- `range func(func(K, V) bool)`はK, Vを返す。`for i, x := range ...`みたいな感じで使うんだね。

「いままで馴染みがあるスライスやマップと横並びで見ると、ちょっと挙動を理解しやすくないかな？」

### `func(V) bool`みたいなのは結局どこで何をするの??
ごふちゃん「さっきのGo Specで出てきた`range`の使い方で、どんな値を引き出せるのかはわかったけど、具体的にどうやって使うのかな？ここでは例を挙げて考えてみるよ。1つ値を返す関数を例にしてみるね。」

https://goplay.tools/snippet/_FCT9JFXBJ4

```go
package main

import (
	"fmt"
)

func main() {
	for s := range f {
		fmt.Println("=== In loop, times=1 ===")
		fmt.Println(s)
	}
}

func f(yield func(string) bool) {
	fmt.Println("*** In function, times=1 ***")
	yield("hello")
	fmt.Println("*** In function, times=2 ***")
	yield("gopher")
}
```

ごふちゃん「ここで覚えておくポイントは次のことかな。」

- 慣例的に`yield`という名前の関数を使うことが多くなりそうだよ。別に予約語とかではないので深読みしなくて良いよ。yieldは他の言語を使ったことがある人は見覚えがあるかもしれないね。
- `yield`の型は`func(string)bool`だから、`f(yield)`がGo Spedで言うところの`function, 1 value`にあたるね。ということは`range`に渡せて、`yield("foo")`ってすると`"foo"`が渡せる/飛び出してくるはずだね。

「さっきの例には処理の順番を確認するための出力も差し込んであるよ。試しに実行してみるね。」

```txt:実行結果
*** In function, times=1 ***
=== In loop, times=1 ===
hello
*** In function, times=2 ***
=== In loop, times=1 ===
gopher
```

「まだ分かりづらいかもしれないから、図を使って呼び出しの順序について確認してみるね。」

:::message
まず処理の順序を直感的に理解したいための説明になります。正確な言語仕様にそぐわない点があるかもしれません。気になる方はそっとタブを閉じてください。
:::

<div style="display: grid; place-items: center; width: 100%;">
    <img src="/images/range-over-func-first/range_over_func_first_example_loop1.png" alt="first-example-loop1" style="width: 100%, max-width: 100%; height: auto;">
</div>