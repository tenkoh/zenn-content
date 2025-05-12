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

それでは始めましょう！

## LocalStackを使うためのAWS SDK設定
サンプルアプリケーションの説明の要点を理解するために、事前にLocalStackを使う際に必要なAWS SDKの設定をおさらいしましょう。本記事の肝の1つでもあるS3の2つのURL形式についても触れていきます。

### AWS SDK設定の概要
AWS SDKや`aws cli`はAWSサービスのエンドポイント設定をカスタマイズすることが可能です。エンドポイントにLocalStackを指定することで、他のアプリケーションコードは変更することなく、LocalStackを使って開発することができます。例えばLocalStackのドキュメントには以下のように記載されています。

```go
func main() {
  awsEndpoint := "http://localhost:4566"
  
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

このパターンでは`UsePathStyle`[^1]を使ってURLをパス形式にする必要はありません。**突然現れた`s3.localhost.localstack.cloud`とは何者なのでしょうか？実はこれがS3の仮想ホスト形式URLに対応するためにLocalStackが用意した工夫です。** この点は次章のサンプルアプリケーションの説明を通じて紐解いていきましょう。

[^1]: オプションの名前は各言語ごとに異なります


## サンプルアプリケーション
それでは、いよいよサンプルアプリケーションに取りかかりましょう。おさらいになりますが、期待する動作を次のように定めます。
1. ユーザーはホストPCのブラウザで`http://localhost:8080`にアクセスする。
1. ユーザーはページに表示された署名付きURLを用いてS3バケット内のオブジェクトをダウンロードする。

本記事冒頭の完成図から、いくつかの設定を省略した図は以下の通りです。LocalStackコンテナ、Appコンテナを動作させ、`http://localhost:8080`にユーザーがアクセスするとAppコンテナの8080番ポートで待ち受けているWebアプリケーションが表示されます。

![architecture-plain.png](/images/localstack-hoststyle/architecture.plain.drawio.png)

現在の図中には、AppコンテナがLocalStackコンテナのS3 オブジェクトの署名付きURLを発行するための設定が欠けています。LocalStackのドキュメント等を見ながらいろいろと設定を変えてみて、どうすれば期待する動作を実現できるか考えてみましょう。

S3のURL形式については、まず**パス形式**で説明を進めます。一通りの説明の後、**仮想ホスト形式**を扱う場合を説明します。

:::message
これから先、「いやそりゃ明らかにダメでしょう」という設定も省略せずに、順序立てて説明していきます。冗長に感じられる方は適宜飛ばし読みしてください。
:::

### URL形式がパス形式の場合
#### Step1. 最初に見つけられるドキュメントを真似る
WebアプリケーションのAWS SDKに、先ほど説明した設定を加えてみましょう。これで動くでしょうか？

```go
func main() {
  awsEndpoint := "http://localhost:4566"
  
  awsCfg, _ := config.LoadDefaultConfig(context.TODO()) // 紙面都合上エラーハンドリング省略

  client := s3.NewFromConfig(awsCfg, func(o *s3.Options) {
    o.UsePathStyle = true
    o.BaseEndpoint = aws.String(awsEndpoint)
  })
  // ...
}
```

**いいえ、動きません。署名付きURLを発行できません。** Appコンテナの`localhost:4566`では何のサービスも動いていませんので、ただただエラーとなります。この例はあくまでホストPC上で動作させるソフト向けの設定であると理解することが必要ですね。

#### Step2. Dockerネットワークを加味してホスト名を変える
次の実験です。同じDockerネットワークに繋がるコンテナは互いのサービス名をホスト名として通信することができます。そこでエンドポイントを`http://localstack:4566`にしてみます。これで動くでしょうか？

![architecture-plain.png](/images/localstack-hoststyle/architecture.step2.drawio.png)

**署名付きURLの発行には成功しますが、ホストPCのブラウザからオブジェクトにアクセスできません。[^2]** AWS SDKのエンドポイントに設定するURLは、AWS SDKが発行する署名付きURL等にそのまま使用されるため、Webアプリケーションは`http://localstack:4566/test-bucket/key-name`というURLをブラウザに表示します。ホストPCからすると`http://localstack`を名前解決できないため、LocalStackコンテナにアクセスできないですね。

[^2]: ただしホストPCに`localstack 127.0.0.1`のようなホスト設定をしてあればアクセスできます。

#### Step3. `s3.localhost.localstack.cloud`形式を使う
LocalStackドキュメントの中で見かけた`http://s3.localhost.localstack.cloud:4566`というエンドポイント設定を試してみましょう。いよいよこれで動くでしょう！

![architecture-plain.png](/images/localstack-hoststyle/architecture.step3.drawio.png)

**いいえ、動きません。署名付きURLを発行できません。**

おまじないのように使用した`s3.localhost.localstack.cloud`というホストが何なのかを確認してみると、この設定がうまく働かない理由がわかります。`s3.localhost.localstack.cloud`は`localhost.localstack.cloud`のCNAMEで、`localhost.localstack.cloud`は`127.0.0.1`に名前解決されます。(お手元で`dig`等でご確認頂けます。)

これはホストPCのブラウザであれば`http://s3.localhost.localstack.cloud:4566/test-bucket/key-name`というURLが`http://127.0.0.1:4566/test-bucket/key-name`として名前解決され、LocalStackコンテナの4566番ポートに辿りつくためうまく働きます。一方でAppコンテナの中でもエンドポイントを`http://127.0.0.1:4566`としてしまうため、Step1.と同じ結果になります。

![architecture-plain.png](/images/localstack-hoststyle/architecture.step3-2.drawio.png)

Step1.と同じくホストPCを意識した仕組みであると理解することが必要ですね。

#### Step4. AppコンテナのDNSサーバーを指定する
LocalStackのドキュメントを彷徨うと、いよいよ求めていた答えに辿り着けます。

https://docs.localstack.cloud/references/network-troubleshooting/endpoint-url/#from-your-container

**LocalStackコンテナが持つDNS機能を使って`localhost.localstack.cloud`を名前解決してね！** ということです。

```docker-compose
services:
  localstack:
    image: localstack/localstack
    # 省略
    networks:
      ls:
        # Set the container IP address in the 10.0.2.0/24 subnet
        ipv4_address: 10.0.2.20

  application:
    image: ghcr.io/localstack/localstack-docker-debug:main
    # 省略
    dns:
      # Set the DNS server to be the LocalStack container
      - 10.0.2.20
    networks:
      - ls

networks:
  ls:
    ipam:
      config:
        # Specify the subnet range for IP address allocation
        - subnet: 10.0.2.0/24
```

LocalStackコンテナをDNSサーバーとして使用するため、LocalStackコンテナのIPアドレスを固定し、AppコンテナのDNS設定にそのIPアドレスを指定します。これにより`localhost.localstack.cloud`というホストは、ホストPCからは`127.0.0.1`として、Appコンテナからは`10.0.2.20`として扱われ、それぞれ適切に動作するようになるという絡繰りです。おもしろいですね！

![architecture-plain.png](/images/localstack-hoststyle/architecture.step4.drawio.png)

**ついに動きました！**

## URL形式が仮想ホスト形式の場合
パス形式の場合とほとんど同じ議論です。Step.4の構成が必要です。

もしかしたら「エンドポイントのホストにバケット名を含めるべきかどうか」で迷われるかもしれませんが、**バケット名はエンドポイントに含めません。バケット名はAWS SDKが適宜付与します。** Step.4の構成において、次のように処理が進められます。

1. WebアプリケーションのAWS SDK設定で`http://s3.localhost.localstack.cloud:4566`をエンドポイントに、`UsePathStyle`を`false`に設定する。
1. AWS SDKは`http://test-bucket.s3.localhost.localstack.cloud:4566`という仮想ホスト形式のURLを使用してサービス(LocalStack)へのリクエストを行う。
1. LocalStackコンテナのDNS機能は、`test-bucket.s3.localhost.localstack.cloud`をLocalStackコンテナのIPアドレスに名前解決する。
1. LocalStackコンテナは`s3.`というプレフィックスを含むリクエストをS3 仮想ホスト形式のURLとして解釈し適切に処置する。
1. Webアプリケーションは`http://test-bucket.s3.localhost.localstack.cloud:4566/key-name`という仮想ホスト形式の署名付きURLを発行する。
1. ブラウザがDNSサーバーに`test-bucket.s3.localhost.localstack.cloud`を問い合わせると`127.0.0.1`と名前解決される。
1. ブラウザはLocalStackコンテナからオブジェクトを取得する。

LocalStackコンテナのDNS機能が仮想ホスト形式のURLの名前解決をする点と、ホスト名に`s3.`を含めておくことでLocalStackコンテナが仮想ホスト形式のURLを適切に処置する点がポイントですね。

これにて本記事の冒頭で宣言したサンプルアプリケーションが完成しました！

:::message
なお、ホストPCが利用しているDNSレコードはLocalStackが登録してくれているものですが、筆者としては、万全を機すのであればホストPCで`test-bucket.s3.localhost.localstack.cloud 127.0.0.1`というホスト設定をしておいた方が良いのかな？とも思っています。LocalStackがドメインを手放した時にどうなるか…？を考えると…。
:::

## おわりに
本記事では、LocalStackを用いたS3の仮想ホスト形式URLの外部公開について、ネットワーク構成やDNS解決の仕組みを交えながら解説しました。特に、Dockerコンテナ環境下で「ホストPCからアクセス可能な署名付きURLを発行する」ためのポイントや、LocalStack独自のDNS機能を活用した実践的な設定方法に焦点を当てました。

LocalStackはローカル開発を強力にサポートしてくれる一方、S3の仮想ホスト形式やネットワーク越しの名前解決など、実運用に近い構成を再現しようとすると意外な落とし穴もあります。本記事の内容が、そうした課題に直面した際のヒントや、より深い理解の一助となれば幸いです。

今後もLocalStackやAWSの仕様は進化していくため、公式ドキュメントやリリースノートも適宜チェックしつつ、柔軟に開発環境をアップデートしていきましょう。

最後までお読みいただき、ありがとうございました！
