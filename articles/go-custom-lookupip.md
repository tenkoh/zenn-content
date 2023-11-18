---
title: "【Go】http.Clientの名前解決差し替え紀行"
emoji: "📞"
type: "tech" # tech: 技術記事 / idea: アイデア
topics: ["go","golang","dns"]
published: true
---

## この記事は何
- Goの`http.Client`の名前解決方法をカスタムしたかった。
- `http.Transport`の`DialContext`を差し替えればできそうだが、名前解決部分をカスタムしたいだけなのに変更必要箇所が大きくなりすぎる。
- 本当に名前解決の部分だけ差し替える方法はないかしら、と調べたが`net.Resolver`で躓いた。
- 今の所は`http.Transport`の`DialContext`フィールドをカスタムするのが良いのかな？

## この記事の対象読者
- Goの`http.Client`の名前解決方法をカスタマイズしたい人。ただしこの記事中の内容は実用性は気にしていません。悪しからず。
- Goのソースコードリーディングが好きな人

## 以下、本文です。

## 背景
最近、DNS over HTTPS(DoH)について簡単に調べる機会がありました。調べてみたら、もちろん使ってみたくなりますね。DoHを利用する方法としては例えばCloudflareさんが提供しているAPIがありました。

https://developers.cloudflare.com/1.1.1.1/encryption/dns-over-https/

以下のようなリクエストで手軽に名前解決が実現できるとのことです。

```bash
curl --http2 -H "accept: application/dns-json" "https://1.1.1.1/dns-query?name=cloudflare.com" 

# Response:
# {"Status":0,"TC":false,"RD":true,"RA":true,"AD":true,"CD":false,"Question":[{"name":"cloudflare.com","type":1}],"Answer":[{"name":"cloudflare.com","type":1,"TTL":155,"data":"104.16.133.229"},{"name":"cloudflare.com","type":1,"TTL":155,"data":"104.16.132.229"}]} 
```

実用的にはどうなんだろう？と思いますが、ここまで簡単にトライできると、**当然Goで活用してみたくなります。(強引)**

名前解決にDoHを使うためのクライアントの実装はあるのでしょうか？"golang dns over https"で検索すると、はい、何件かヒットしますね。

こちらは一例ですが、サーバーとクライアント両方を含んでいます。活発に開発もされていそうです。

https://github.com/m13253/dns-over-https

他にもいくつかの例を見ましたが、`http.Client`の名前解決の方法だけをピンポイントで差し替える方法は見受けられません。極力標準パッケージを活用したいな、と個人的には思うので、どうしたら実現できるのか一度確認してみよう！と思いました。

## http.Clientが名前解決をするまで
まず簡単に`http.Client`が名前解決をするまでの手順を確認してみます。特にことわりを入れない限り、`http.DefaultClient`が行う手順について記載します。

`http.Client`は次のような構造体ですね。リクエスト処理を行うのは`http.RoundTripper`インタフェースです。

```go
type Client struct {
    Transport RoundTripper
    CheckRedirect func(req *Request, via []*Request) error
    Jar CookieJar
    Timeout time.Duration
}

type RoundTripper interface {
    RoundTrip(*Request) (*Response, error)
}
```

`http.RoundTripper`の実装として`*http.Transport`があります。その中でコネクションを確立するのが`DialContext`関数です。

```go
type Transport struct{
    DialContext func(ctx context.Context, network, addr string) (net.Conn, error)
}
```

コネクション確立の過程で名前解決を行うため、`DialContext`フィールドをカスタムした関数で上書きすればやりたいことはやれそうです。ただ、名前解決方法だけを差し替えたいのに、変更する範囲が広くなってしまいそうです。そこでもう一歩踏み込んでみたいと思います。

`http.DefaultTransport`では、`DialContxt`フィールドを次のように設定します。

```go
var DefaultTransport RoundTripper = &Transport{
    DialContext: defaultTransportDialContext(&net.Dialer{
        Timeout:   30 * time.Second,
        KeepAlive: 30 * time.Second,
    }),
}
```

`defaultTransportDialContext`の実装はwasmかそれ以外かで分けられていますが、wasm以外では初期化した`net.Dialer`の`DialContext`関数をそのまま返します。どうやら`net.Dialer`が鍵を握っていそうです。

`net.Dialer`は次のような構造体です。

```go
type Dialer struct {
    // Resolver optionally specifies an alternate resolver to use.
    Resolver *Resolver
}

func (d *Dialer) DialContext(ctx context.Context, network, address string) (Conn, error) {
    // 省略
}
```

`Resolver`フィールドにカスタムした`*net.Resolver`を設定すればコネクション確立のやり方(名前解決含む)を上書きできそうに見えますが、`*Dialer.DialContext`関数の中身を見ると、`Resolver`の`resolveAddrList`関数を呼び出しています。このプライベートメソッドの挙動を変更するにはどうしたら良いのでしょうか？

https://cs.opensource.google/go/go/+/master:src/net/dial.go;l=490;drc=1fde99cd6eff725f5cc13748a43b4aef3de557c8

:::message
`Resolver`が構造体ではなくインタフェースであれば、この辺りを柔軟に変更しやすそうですが…。
:::

`net.Resolver`を見てみると`Dial`関数なるフィールドがありますが、この関数は`resolveAddrList`の中からは呼ばれないので、挙動の変更には使え無さそうです。

```go
type Resolver struct {
    PreferGo bool
    StrictErrors bool
    Dial func(ctx context.Context, network, address string) (Conn, error)
}
```

`resolveAddrList`関数をもう少し見てみます。

https://cs.opensource.google/go/go/+/master:src/net/dial.go;l=264;drc=1fde99cd6eff725f5cc13748a43b4aef3de557c8

この関数の中では、指示されたアドレスを`*Resolver.internetAddrList`、さらにそこから`*Resolver.lookupIPAddr`を使ってIPアドレスに変換しています。**ついに名前解決きた！**

https://cs.opensource.google/go/go/+/master:src/net/lookup.go;l=304;drc=b9a08f159d3074ad5921a9d8625b267b64d957bc

そしてついにピンポイントで名前解決だけを差し替える部位を発見しました。

```go:src/net/lookup.go
// The underlying resolver func is lookupIP by default but it
// can be overridden by tests. This is needed by net/http, so it
// uses a context key instead of unexported variables.
resolverFunc := r.lookupIP
if alt, _ := ctx.Value(nettrace.LookupIPAltResolverKey{}).(func(context.Context, string, string) ([]IPAddr, error)); alt != nil {
    resolverFunc = alt
}
```

**なるほど、`context`の中に`lookupIP(ctx context.Context, network, host string) (addrs []IPAddr, err error)`と同じ型の関数を入れておけば差し替えられるんですね！**

## いざカスタム
ということで喜び勇んで次のようなコードを書きました。

```go:main.go
// 適当に省略
func CustomDialContext(ctx context.Context, /*省略*/) {
    ctx := context.WithValue(
        ctx,
        nettrace.LookupIPAltResolverKey{},
        myCustomLookupIPFunc,
    )
    d := &net.Dialer{}
    return d.DialContext(ctx, /*省略*/)
}
```

これを`http.Transport`に差し込めばいける…！と確信した刹那

```bash
[gopls] go list:Error:use of internal package internal/nettrace not allowed
```

**え、君、`internal`パッケージの人なの…？**

なんと言うことでしょう、この差し替えはテスト向けにしか使われていないのです。ここを変えれば変更ミニマムで既存コードの恩恵に預かれると思ったのですが…。悲しい。

## 代案
さあ、ではどうしようとなりますが、先ほどのコードリーディングの最中に１つ発見をしました。`*Resolver.lookupIpAddr`の処理の中で、指示されたアドレスがホスト名ではなくIPアドレスの際はそのままリターンする処理がありました。

https://cs.opensource.google/go/go/+/master:src/net/lookup.go;l=309;drc=15fa7a84b88165092d3a05fb0af11f11d967065d

ということで、当初モチベーションにこだわってDoHしたい！のであれば、デフォルトの処理が実行される前に自力で名前解決してあげるのが良さそうです。ということで`http.Transport`の`DialContext`フィールドに、次のようなカスタム品を設定してみます。

```go
func customDialContext(ctx context.Context, network, addr string) (net.Conn, error) {
    // addr = host:port format
    addrs := strings.Split(addr, ":")
    if len(addrs) != 2 {
        return nil, errors.New("invalid address")
    }
    host := addrs[0]
    port := addrs[1]

    // dohLookupIPはcloudflareのdoh APIを使って名前解決をする
    ip, err := dohLookupIP(host)
    if err != nil {
        return nil, fmt.Errorf("can not resolve host %s: %w", host, err)
    }

    d := &net.Dialer{}
    return d.DialContext(ctx, network, ip+":"+port)
}
```

DNSキャッシュをクリアして、上の関数を差し込んだ`http.Transport`を使うと、確かにDNSへの問い合わせがスキップできています。遠回りしましたが、当初狙いは達成できましたね。

:::message
ちなみに、`http.Transport`を合成した次のような構造体を作ることもできそうですが、`http.Transport`がHTTPS通信における署名中のホスト名の検証を行う際に、IPアドレスとホスト名を比較してしまうので検証に失敗しますね。

```go
type customTransport struct {
    t *http.Transport
}

func (t *customTransport) RoundTrip(req *http.Request) (*http.Response, error) {
    // req.URLのSchemeやHostの情報から、DoHして名前解決する。
    // reqの中身を適当に上書きする。
    return t.t.RoundTrip(req)
}
```
:::

## おわりに
途中までは`net.Resolver`の内部で行う名前解決部分だけを差し替える方法を模索しましたが、最終的には`http.Transport`にカスタムした`DialContext`を渡すことで狙いを達成しました。

`net.Resolver`をカスタムしたい要望はありそうで、以下のようなIssueもあります。`net.Resolver`をインタフェースにしてはどうかという議論もされていますが、現在の`net.Resolver`構造体は意外とメソッドも多く、やるにしても責務ごとにインタフェースを分割する必要がありそうなど、ある程度の変更が必要そうですね。

https://github.com/golang/go/issues/12503

個人的には、今回のソースコードリーディングで発見した`context`で名前解決の関数を差し込む部分を、テスト用に限らなければ、多少やりたいことはやれそうだけどな、と思いました。（トリッキーな感じは拭えませんが）