---
title: "LocalStackのS3を意地でも仮想ホスト形式で扱うための全て"
emoji: "✨"
type: "tech" # tech: 技術記事 / idea: アイデア
topics: ["go", "localstack", "aws", "s3", "docker"]
published: false
---

## はじめに
### この記事は何
AWSを使用するアプリケーションのローカル開発環境構築において、本物のAWSを使用しないで済む[LocalStack](https://www.localstack.cloud)はありがたい存在です。環境を壊しても問題ないという安心感は心強いものです。

筆者は最近、本物のAWSに依存したローカル開発環境を再構築する機会に恵まれたのですが、**S3のパス形式、SDK仕様、LocalStack仕様の三者が織りなす沼にハマって数日を溶かしました**。なんとか解決することができましたが、なかなか必要な情報に辿り着けず苦労しました。本記事は同じ沼にはまる人を減らしたい…！という思いで記しています。

本記事では、最終的に下図の構成にたどり着きます。下図構成は**WebアプリケーションがS3上のオブジェクトの署名付きURLを発行し、ブラウザがそのURLを使ってファイルをダウンロードする**仕組みを実現しています。この中では１点制約を設けており、**署名付きURLはS3の virtual-hosted style (以下、仮想ホスト形式)であること**とします。つまりバケット名をホスト名として含む`http://test-bucket.s3.localhost.localstack.cloud:4566/<object-key><署名情報>`のような署名付きURLを使うということです。S3のパス形式については本文で詳しく説明していきます。

図中には既にキーポイントを明示していますが、本記事ではそれぞれのポイントをステップバイステップで説明していきます。**LocalStackの使いこなしという点に限らず、AWS(S3)の仕様や、ネットワークの面白い点についても触れていきます。** 図を見て不明な点がある方はぜひご一読頂ければと思います。

![architecture.png](/images/localstack-hoststyle/architecture.drawio.png)

また記事の最後にはおまけとして、他の要素(LocalStackのLambda)を追加する実験も行いますので、そちらもよろしければどうぞ。

### 本記事の対象読者
- LocalStackが好きな人
- LocalStackを使い始めたい人
- ローカル開発環境構築の手札を増やしたい人

### 本記事で扱わないこと
- AWS SDKやAWS CLIの基本的な使用方法は説明しません
- LocalStackのインストール方法や基本的な使用方法は説明しません

### 前提条件
- LocalStackはDockerコンテナとして実行する。
  - イメージは`localstack/localstack:3.7.2`。
  - S3サービスを実行する。(詳細はサンプルアプリケーションの章を参照)

### 結び
前置きが長くなりましたが、次からはいよいよ本題に入っていきます。以下の順番で説明を進めていきます。

1. 前提知識
    1. S3のURL形式
    1. AWS SDKのエンドポイントオプション
1. サンプルアプリケーション
    1. AppコンテナのAWS SDKのエンドポイントおよびネットワーク設定
    1. ホストからの名前解決の仕組み
1. おまけ: LocalStackのLambdaを使う場合のAWS SDKのエンドポイント

それでは始めましょう！

## 前提知識
冒頭に示した構成において制約として記載した「仮想ホスト形式」のパスとは何なのか、図中に示した「AWS SDK Endpoint」とは何なのか。今後の説明に必要なこの２点を説明します。

### S3のURL形式
パブリックアクセス可能なS3バケット内のオブジェクトへのアクセスや、署名付きURLを使用したS3バケット内のオブジェクトへのアクセスにおいて、そのURLは**仮想ホスト形式**と**パス形式**の両方が有効です。

https://docs.aws.amazon.com/ja_jp/AmazonS3/latest/userguide/VirtualHosting.html

:::message
ただし上記ドキュメントに記載されているように**パス形式**は将来的に廃止予定です。
:::

仮想ホスト形式は`https://your-bucket.s3.region-code.amazonaws.com/your-object-key`のようなバケット名をホスト名の一部として使用するものです。一方でパス形式は`https://s3.region-code.amazonaws.com/your-bucket/your-object-key`のようにバケット名をパスの一部として使用するものです。

ここで`https://s3.region-code.amazonaws.com`の部分が次に説明するAWSサービスのエンドポイントに該当します。

### AWS SDKのエンドポイントオプション
AWS SDKや`aws cli`はAWSサービスのエンドポイント設定をカスタマイズすることが可能です。エンドポイントにLocalStackを指定することで、他のアプリケーションコードは変更することなく、LocalStackを使って開発することができます。例えばLocalStackのドキュメントには以下のように記載されています。

```go
func main() {
  awsEndpoint := "http://localhost:4566"
  awsRegion := "us-east-1"
  
  awsCfg, err := config.LoadDefaultConfig(context.TODO(),
    config.WithRegion(awsRegion),
  )
  if err != nil {
    log.Fatalf("Cannot load the AWS configs: %s", err)
  }

  // Create the resource client
  client := s3.NewFromConfig(awsCfg, func(o *s3.Options) {
    o.UsePathStyle = true
    o.BaseEndpoint = aws.String(awsEndpoint)
  })
  // ...
}
```

https://docs.localstack.cloud/user-guide/integrations/sdks/go/

この例では、エンドポイントとして`http://localhost:4566`を使い、`UsePathStyle = true`にしてパス形式のURLを指定しています。

ところで、LocalStackのドキュメントを複数見てみると、いくつか異なる記述が見受けられます。**このエンドポイントの設定が本記事のポイントの1つです**。それぞれを以下で確認してみましょう。

#### パターン①: パス形式を使用
先ほどの例のように、エンドポイントとして`http://localhost:4566`を使い、`UsePathStyle = true`にするものです。

#### パターン②: 仮想ホスト形式を使用
他方、以下のような設定も紹介されています。

```ruby
Aws.config.update(
  endpoint:  'http://s3.localhost.localstack.cloud:4566', # update with localstack endpoint
  # 他の項目は記載省略
)
```

https://docs.localstack.cloud/user-guide/integrations/sdks/ruby/

このパターンでは`UsePathStyle`[^1]を使ってURLをパス形式にする必要はありません。**突然現れた`s3.localhost.localstack.cloud`とは何者なのでしょうか？実はこれがS3の仮想ホスト形式URLに対応するためにLocalStackが用意した工夫です。**

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

[^1]: オプションの名前は各言語ごとに異なります

[^2]: 名前解決機能の詳細はドキュメントが見当たりませんでしたが、[このような](https://docs.localstack.cloud/user-guide/aws/s3/#path-style-and-virtual-hosted-style-requests)記述があります。

ただし、**本記事冒頭の図にあるような「LocalStackコンテナに他のコンテナからアクセスする」ケースではこの設定は有効に働きません。なぜなら他のコンテナ内の`127.0.0.1`にアクセスすることとなるためです。**これを解決するにはさらに設定が必要ですが、その説明はサンプルアプリケーションの章で行いたいと思います。

#### エンドポイントのパス形式の影響
基本的にはどちらのパス形式を使っても問題ありません。**ただしエンドポイントはS3等のリソースのパスの一部となるため、アプリケーションが特定のパス形式を想定したロジックを持ってしまっているような場合には、そのパス形式に設定する必要があります。**もし既存のプロジェクトでAWS SDKを使っていて、途中からLocalStackを使う場合には、これまでは**SDKのデフォルトのパス形式である仮想ホスト形式**を用いているケースが多いでしょう。（筆者もそのパターンでした）

次章のサンプルアプリケーションでは仮想ホスト形式のLocalStackのエンドポイントを使用します。ただ、いざ仮想ホスト形式のパスを使おうとするといろいろな疑問や躓きポイントが出てきます。サンプルアプリケーションを通じて一つ一つ解消していきましょう。

## サンプルアプリケーション
### AppコンテナのAWS SDKのエンドポイントおよびネットワーク設定
### ホストからの名前解決の仕組み

## おまけ: LocalStackのLambdaを使う場合のAWS SDKのエンドポイント

## おわりに
