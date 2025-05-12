---
title: "LocalStackを本気で使いこなす：S3 URLを外部公開するための設定と仕組み理解"
emoji: "✨"
type: "tech" # tech: 技術記事 / idea: アイデア
topics: ["go", "localstack", "aws", "s3", "docker"]
published: false
---

## はじめに
### この記事は何
[LocalStack](https://www.localstack.cloud/)は、AWSの各種サービスをローカルで模倣できる便利なツールです。特にS3などの基本的なサービスは、AWS SDKのエンドポイントを切り替えるだけで簡単に扱えます。しかし、LocalStackをDockerコンテナ上で動かし、さらにアプリケーションも別のコンテナで動かす場合、**「ホストPCからアクセス可能なS3 URLを出力する」ことは、思いのほか難易度が高くなります。**

本記事では、LocalStackとアプリケーションコンテナを連携させる際の具体的な課題や設定（エンドポイントの指定、DNS解決の工夫）について、サンプルアプリケーションを通じて丁寧に解説します。最終的なサンプルアプリケーション構成は下図の通りです。下図構成は**WebアプリケーションがS3上のオブジェクトの署名付きURLを発行し、ブラウザがそのURLを使ってファイルをダウンロードする**仕組みを実現しています。この中では１点制約を設けており、**署名付きURLはS3の virtual-hosted style (以下、仮想ホスト形式)であること**とします。つまりバケット名をホスト名として含む`http://test-bucket.s3.localhost.localstack.cloud:4566/<object-key><署名情報>`のような署名付きURLを使うということです。S3のパス形式については本文で詳しく説明していきます。

![architecture.png](/images/localstack-hoststyle/architecture.drawio.png)

図中には既にキーポイントを明示していますが、本記事ではそれぞれのポイントをステップバイステップで説明していきます。**LocalStackの使いこなしという点に限らず、AWS(S3)の仕様や、ネットワークの面白い点についても触れていきます。** 図を見て不明な点がある方はぜひご一読頂ければと思います。

### 本記事の対象読者
- LocalStackが好きな人、使い始めたい人
- ローカル開発環境構築の手札を増やしたい人

### 本記事で扱わないこと
- AWS SDKやAWS CLIの基本的な使用方法は説明しません
- LocalStackのインストール方法や基本的な使用方法は説明しません

### 前提条件
- LocalStackはDockerコンテナとして実行する。
  - イメージは`localstack/localstack:3.7.2`。
  - S3サービスを実行する。(詳細はサンプルアプリケーションの章を参照)

### 結び
次からはいよいよ本題に入っていきます。以下の順番で説明を進めていきます。

1. LocalStackを使うためのAWS SDK設定
    1. AWS SDK設定の概要
    1. S3のURL形式
1. サンプルアプリケーション
    1. AppコンテナのAWS SDKのエンドポイントおよびネットワーク設定
    1. ホストからの名前解決の仕組み
1. おまけ: LocalStackのLambdaを使う場合のAWS SDKのエンドポイント

それでは始めましょう！

## LocalStackを使うためのAWS SDK設定
サンプルアプリケーションの説明の要点を理解するために、事前にLocalStackを使う際に必要なAWS SDKの設定をおさらいしましょう。本記事の肝の1つでもあるS3の2つのURL形式についても触れていきます。

### AWS SDK設定の概要
AWS SDKや`aws cli`はAWSサービスのエンドポイント設定をカスタマイズすることが可能です。エンドポイントにLocalStackを指定することで、他のアプリケーションコードは変更することなく、LocalStackを使って開発することができます。例えばLocalStackのドキュメントには以下のように記載されています。

```go
func main() {
  awsEndpoint := "http://localhost:4566"
  awsRegion := "us-east-1"
  
  awsCfg, _ := config.LoadDefaultConfig(context.TODO()) // 紙面都合上エラーハンドリング省略

  client := s3.NewFromConfig(awsCfg, func(o *s3.Options) {
    o.UsePathStyle = true
    o.BaseEndpoint = aws.String(awsEndpoint)
  })
  // ...
}
```

https://docs.localstack.cloud/user-guide/integrations/sdks/go/

この例では、エンドポイントとして`http://localhost:4566`を使っています。LocalStackコンテナのサービスポート(4566)は一般的にホストPCの4566番ポートにバインドして使用するため、この設定によりホストPCはLocalStackのサービスにアクセスするようになります。

ところで、先ほどの例にある`UsePathStyle`とは何でしょうか？これはS3のURLが**仮想ホスト形式(virtual-hosted style)**と**パス形式**のどちらの形式も扱うことから、SDKとしてどちらを使用するかを選択できるようにしているオプションです。仮想ホスト形式という言葉は、本記事冒頭で述べたサンプルアプリケーションの制約の中にも登場しましたね。2つのURL形式の違いを理解することは意外と重要です。

### S3のURL形式
仮想ホスト形式とパス形式は、それぞれ以下のようなURLです。**なお、パス形式については廃止予定となっています。**

| 形式 | URL |
| --- | --- |
| 仮想ホスト | `https://<bucket>.s3.<region>.amazonaws.com/<key>` |
| パス | `https://s3.<region>.amazonaws.com/<bucket>/<key>` |

https://docs.aws.amazon.com/AmazonS3/latest/userguide/VirtualHosting.html

`<region>`などが入り込んでいますが、もう少し汎用的にすると以下の形式とも読み取れます。(後ほど説明するLocalStackでのエンドポイント設定深掘りのため汎用的にしておきます。)

| 形式 | URL |
| --- | --- |
| 仮想ホスト | `<endpoint-schema>//<bucket>.<endpoint-host>/<key>` |
| パス | `<endpoint-schema>//<endpoint-host>/<bucket>/<key>` |

AWS SDKはデフォルトでは仮想ホスト形式を扱うようです。どちらのURL形式を使ってもSDKに隠蔽されている限りは大きな違いはありませんが、**S3の署名付きURLをSDKを使って発行するケースにおいては、設定した形式でURLが出力されます。**

つまり先ほどの例では、エンドポイントを`http://localhost:4566`、URL形式を`パス形式`としているため、`http://localhost:4566/<bucket>/<key>`のようなURLが得られることになりますね。

LocalStackのドキュメントには各プログラミング言語ごとのSDKの設定方法が記載されていますが、多くのケースで`パス形式`を扱う例が記載されています。これは推測ですが`パス形式`を扱う方が名前解決上はるかにシンプルでトラブルが少ないためと考えられます。仮想ホスト形式では`http://<bucket>.localhost:4566/<key>`のようなURLになってしまうため、何らかの設定をしていない限り名前解決ができません。パス形式を使えば、この「何らかの設定」を気にかけなくて良いメリットがあるでしょう。

ところで、LocalStackのドキュメントを読んでいくと、先ほどとは異なるエンドポイントの設定例も見つけられます。

```ruby
Aws.config.update(
  endpoint:  'http://s3.localhost.localstack.cloud:4566', # update with localstack endpoint
  # 他の項目は記載省略
)
```

https://docs.localstack.cloud/user-guide/integrations/sdks/ruby/

このパターンでは`UsePathStyle`[^1]を使ってURLをパス形式にする必要はありません。**突然現れた`s3.localhost.localstack.cloud`とは何者なのでしょうか？実はこれがS3の仮想ホスト形式URLに対応するためにLocalStackが用意した工夫です。**この点は次章のサンプルアプリケーションの説明を通じて紐解いていきましょう。

[^1]: オプションの名前は各言語ごとに異なります


## サンプルアプリケーション


ためしにLocalStackのS3に`your-bucket`バケットを作成し、その中の公開オブジェクトにホストPCのブラウザからアクセスしてみましょう。仮想ホスト形式のURLは`http://your-bucket.s3.localhost.localstack.cloud:4566/your-object-key`のはずです。すると期待した通りにオブジェクトにアクセスできます。これは2つの仕組みの組み合わせで実現されています。

1. `your-bucket.s3.localhost.localstack.cloud`は、LocalStackが登録したDNSレコードによって`127.0.0.1`、つまりホストPCのlocalhostに名前解決される。
2. LocalStackには名前解決の機能があり、 受信したリクエストの宛先が`s3.`を接頭辞とするホスト名であればS3の仮想ホスト形式として解釈し、ホスト名に含まれるバケット名も含めて適切に解決する。[^2]

簡単な図にすると以下のような流れです。

1に関して、以下は`dig`による問い合わせ結果の抜粋です。`<bucket>.<service>.localhost.localstack.cloud`というホスト名はいずれも`127.0.0.1`として名前解決されます。
```bash
your-bucket.s3.localhost.localstack.cloud. 60 IN CNAME localhost.localstack.cloud.
localhost.localstack.cloud. 600	IN	A	127.0.0.1
```

:::message
上記のようなDNSレコードが用意されているとは言え、万全を期すなら各自のホストPCで`/etc/hosts` or `C:\Windows\System32\drivers\etc\hosts`に同様の設定を書くのが良いとも思います。バケット名を変えたら設定を変えないといけなくなりはしますが。
:::


[^2]: 名前解決機能の詳細はドキュメントが見当たりませんでしたが、[このような](https://docs.localstack.cloud/user-guide/aws/s3/#path-style-and-virtual-hosted-style-requests)記述があります。

ただし、**本記事冒頭の図にあるような「LocalStackコンテナに他のコンテナからアクセスする」ケースではこの設定は有効に働きません。なぜなら他のコンテナ内の`127.0.0.1`にアクセスすることとなるためです。**これを解決するにはさらに設定が必要ですが、その説明はサンプルアプリケーションの章で行いたいと思います。

#### エンドポイントのURL形式の影響
基本的にはどちらのURL形式を使っても問題ありません。**ただしエンドポイントはS3等のリソースのURLの一部となるため、アプリケーションが特定のURL形式を想定したロジックを持ってしまっているような場合には、そのURL形式に設定する必要があります。**もし既存のプロジェクトでAWS SDKを使っていて、途中からLocalStackを使う場合には、これまでは**SDKのデフォルトのURL形式である仮想ホスト形式**を用いているケースが多いでしょう。（筆者もそのパターンでした）

次章のサンプルアプリケーションでは仮想ホスト形式のLocalStackのエンドポイントを使用します。ただ、いざ仮想ホスト形式のパスを使おうとするといろいろな疑問や躓きポイントが出てきます。サンプルアプリケーションを通じて一つ一つ解消していきましょう。
### S3のURL形式
パブリックアクセス可能なS3バケット内のオブジェクトへのアクセスや、署名付きURLを使用したS3バケット内のオブジェクトへのアクセスにおいて、そのURLは**仮想ホスト形式**と**パス形式**の両方が有効です。

https://docs.aws.amazon.com/ja_jp/AmazonS3/latest/userguide/VirtualHosting.html

:::message
ただし上記ドキュメントに記載されているように**パス形式**は将来的に廃止予定です。
:::

仮想ホスト形式は`https://your-bucket.s3.region-code.amazonaws.com/your-object-key`のようなバケット名をホスト名の一部として使用するものです。一方でパス形式は`https://s3.region-code.amazonaws.com/your-bucket/your-object-key`のようにバケット名をパスの一部として使用するものです。

ここで`https://s3.region-code.amazonaws.com`の部分が次に説明するAWSサービスのエンドポイントに該当します。


## サンプルアプリケーション
### AppコンテナのAWS SDKのエンドポイントおよびネットワーク設定
### ホストからの名前解決の仕組み

## おまけ: LocalStackのLambdaを使う場合のAWS SDKのエンドポイント

## おわりに
