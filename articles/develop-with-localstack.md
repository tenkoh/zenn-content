---
title: "【Go】LocalStack活用メモ：ローカル開発環境からテストまで"
emoji: "💫"
type: "tech" # tech: 技術記事 / idea: アイデア
topics: [go, localstack, test]
published: false
---

## この記事は何
ローカル環境でAWSサービスをエミュレートできる[LocalStack](https://github.com/localstack/localstack)、便利ですよね。
本当のAWS環境を使わないようにすることで、セキュリティの担保(詳細は後述)やうっかりとした事故の防止を実現しつつ、アプリケーションのコード内で無用なモックを用意する必要もなくなります。

LocalStackの活用方法の様々な記事がありますが、Go言語での開発において、1:ローカル開発環境用途、2:テスト時の使い捨て用途の両方をまとめて整理した記事は見かけませんでした。本記事では両者を整理して、スッとLocalStackを活用できることを目的とします。

具体的に取り扱う内容は以下の通りです。

- ローカル開発環境：Go言語で書いたアプリケーションが動くアプリコンテナと、LocalStackコンテナ間で通信する環境を構築します。
- テスト：`testcontainers-go`を使ってLocalStackコンテナを立ち上げ・立ち下げます。

### この記事で扱わないこと
- Go言語の基本は説明しません。
- LocalStackの取り扱いを網羅的には説明しません。

## ローカル開発環境編
本章の題材として、次のようなアプリケーションと開発環境を想定します。

- `aws-sdk-go-v2`を使ってS3バケットからのReadを行うアプリケーション。
- ローカル開発でDockerを活用する。
- 本番環境ではアプリケーションはEC2やLambdaで稼働させるものとし、アクセス権はEC2/LambdaにアタッチするIAM Roleで管理する。したがってローカル開発時のみAWSへのアクセスには何かしらの認証が必要。

最後の要件を満たすには、IAM UserやSecurity Token Service(STS)の利用が考えられますが、セキュリティを担保するためIAM Userは使いたくはないですし、STSにしてもできれば簡素な運用をしたいところです。
**この悩みはローカル開発環境から本当のAWSにアクセスしようとすることに起因するため、AWSをローカルでエミュレートすることでバサっと解決を図ります。ここでLocalStackの出番となります**。

本章では、まずLocalStackを使わない場合のGoのコードとDocker等の設定を示し、その後にLocalStackを導入するための変更を加えます。

### LocalStackを使わない場合
まず、以下のような簡単なアプリケーションコードを用意しました。S3に保存したJSONファイルを読み込み、標準出力に表示するだけの機能を持ちます。

:::message
説明を簡単にするため、エラーハンドリングは割愛して掲載します。
:::

```go:main.go
package main

import (
	"context"
	"encoding/json"
	"fmt"
	"os"

	"github.com/aws/aws-sdk-go-v2/aws"
	"github.com/aws/aws-sdk-go-v2/config"
	"github.com/aws/aws-sdk-go-v2/service/s3"
)

type s3Config struct {
	region string
	bucket string
	key    string
}

func newS3Config() *s3Config {
	return &s3Config{
		region: os.Getenv("AWS_REGION"),
		bucket: os.Getenv("AWS_S3_BUCKET"),
		key:    os.Getenv("AWS_S3_KEY"),
	}
}

type User struct {
	ID int `json:"id"`
}

func main() {
	ctx := context.Background()
	s3Config := newS3Config()

	// S3を利用するためのクライアントの呼び出し
	config, _ := config.LoadDefaultConfig(ctx, config.WithRegion(s3Config.region))
	client := s3.NewFromConfig(config, func(o *s3.Options) {
		o.UsePathStyle = true
	})

	object, _ := client.GetObject(ctx, &s3.GetObjectInput{
		Bucket: aws.String(s3Config.bucket),
		Key:    aws.String(s3Config.key),
	})
	defer object.Body.Close()

	var users []User
	json.NewDecoder(object.Body).Decode(&users)

	fmt.Printf("%+v", users)
}
```

このアプリケーションを実行するための`Dockerfile`と`compose.yml`を用意しました。`Dockerfile`はアプリケーションをビルドして実行するだけなので掲載を割愛します。

```yml:compose.yml
services:
  app:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: go-localstack-sample-app
    environment:
      - AWS_REGION=${AWS_REGION}
      - AWS_S3_BUCKET=${AWS_S3_BUCKET}
      - AWS_S3_KEY=${AWS_S3_KEY}
      - AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID}
      - AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY}
```

:::message
別途`.env`ファイルを用意して読み込んでいます。
:::

:::message alert
説明を簡単にするため、IAM Userを使う想定にしています。またDocker Composeの`secrets`も使っていません。本番のアプリケーションにこのサンプルは適用しないでください。
:::

`compose.yml`では、S3にアクセス可能な権限を持ったIAM Userのアクセスキーとシークレットキーを環境変数に設定しています。

さて、これでアプリケーション自体は動きますが、IAM Userを使いたくない等の動機から、本物のAWS環境を剥がしていきます。

:::message
IAM Userを使いたくないと考える動機については、下記などをご覧ください。 https://engineer.retty.me/entry/2022/12/16/110000#なぜ-IAM-User-を減らしたいのか
:::

### LocalStackを取り入れる
Docker ComposeでLocalStackを使っていきます。詳細な説明は[公式リファレンス](https://docs.localstack.cloud/getting-started/installation/#docker-compose)をご覧ください。


```yml:compose.yml
services:
  localstack:
    image: localstack/localstack:3.7.2
    container_name: localstacks3
    ports:
      - "4566:4566"
    environment:
      - SERVICES=s3
      - DEBUG=1
    networks:
      - app-network
    volumes:
      - "./dev/init-aws.sh:/etc/localstack/init/ready.d/init-aws.sh" # 初期化スクリプト
      - "./dev/users.json:/docker-entrypoint-initaws.d/users.json" # 初期データ
      - "./volume:/var/lib/localstack"
      - "/var/run/docker.sock:/var/run/docker.sock"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:4566/_localstack/health"]
      interval: 10s
      retries: 5

  app:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: go-localstack-sample-app
    environment:
      - AWS_REGION=ap-northeast-1
      - AWS_S3_BUCKET=test-bucket
      - AWS_S3_KEY=users.json
      - AWS_ACCESS_KEY_ID=dummy
      - AWS_SECRET_ACCESS_KEY=dummy
      - AWS_ENDPOINT_URL=http://localstacks3:4566
    networks:
      - app-network
    depends_on:
      localstack:
        condition: service_healthy

networks:
  app-network:
    driver: bridge
```

ポイントは...
- アプリコンテナとLocalStackコンテナ間で通信を行うため、`network`の設定を加えています。
- アプリから実際のAWSではなくLocalStackにアクセスするように、`AWS_ENDPOINT_URL`環境変数を設定しています。エンドポイントは`http://{LocalStackのコンテナ}:{LocalStackのポート}`です。
- LocalStackを起動した時にS3のバケットを作り、バケット内にファイルを置いておきたいことがあると思います。初期化ファイル`init-aws.sh`を所定のディレクトリにマウントすることで実現可能です。

この時のローカル環境のディレクトリ構成および`init-aws.sh`の内容は次のとおりです。

```sh
.
├── Dockerfile
├── compose.yml
├── dev
│   ├── init-aws.sh
│   └── users.json
├── go.mod
├── go.sum
└── main.go
```

```sh:init-aws.sh
#!/bin/bash
export AWS_ACCESS_KEY_ID=dummy AWS_SECRET_ACCESS_KEY=dummy

awslocal s3 mb s3://test-bucket
awslocal s3 cp /docker-entrypoint-initaws.d/users.json s3://test-bucket/users.json
```

- 今回作成しているアプリはS3バケット内のファイルを読み込めないとエラーになります。そのためLocalStackのコンテナが立ち上がった後、ファイルのアップロード完了まではアプリコンテナは起動を待たなければなりません。LocalStackの`/_localstack/health`エンドポイントでヘルスチェックが行えるため、アプリコンテナは`depends_on`でLocalStackコンテナのヘルスチェック完了を待つようにします。

ここまで変更してみると、`compose.yml`の環境変数にはダミーの値しか登場しなくなることがわかります。安心感がありますね😊。そして**アプリケーションのコードにはなんの変更も加える必要はありません**。大変便利ですね！

:::message
環境変数によるエンドポイントの上書きは[AWS SDKsのドキュメント](https://docs.aws.amazon.com/ja_jp/sdkref/latest/guide/feature-ss-endpoints.html)に記載のあるとおりです。一方で[LocalStackのドキュメント](https://docs.localstack.cloud/user-guide/integrations/sdks/go/)には、環境変数ではなくコード中エンドポイントを明示的にLocalStackにするように記載されています。どちらが適切か、もしご知見があればコメントをください。
:::

ローカル開発環境におけるLocalStackの活用例は以上です！

## テスト編
ローカル開発環境の立ち上げは、Docker Composeの設定類が諸々あり、少し長くなってしまいましたね。ご安心ください、テスト編は`testcontainers-go`を使ってサクッと進めていきます。ありがとう、神...。

`testcontainers-go`は、Go言語のテスト時にコンテナの立ち上げ・立ち下げを行ってくれるモジュールですね。様々なところで使われているのを見かけます。任意のDockerイメージを指定してテストで利用できるため非常に便利です。
頻繁に使われるDockerイメージは`testcontainers-go`で利用しやすいようにモジュールが用意されています。LocalStack用のモジュールもあるため、積極的に使っておきたいと思います。

さて、現在のコードではテストを実施し辛いためいったんリファクタリングしておきましょう。`*s3.Client`というAWS SDKのクライアントをDIするようにし、テストでは`testcontainers-go`で立ち上げたコンテナを向けたクライアントを使えるようにします。

```go:main.go
type Repository struct {
	client *s3.Client
}

func NewRepository(client *s3.Client) *Repository {
	return &Repository{client}
}

func (r *Repository) GetUsers(ctx context.Context, bucket, key string) []User {
	object, _ := r.client.GetObject(ctx, &s3.GetObjectInput{
		Bucket: aws.String(bucket),
		Key:    aws.String(key),
	})
	defer object.Body.Close()

	var users []User
	json.NewDecoder(object.Body).Decode(&users)
	return users
}
```

:::message
あいからわずエラーハンドリングを割愛していたり、ところどころサボっているところがありますが、説明を短くするためなのでご容赦ください。
:::

この`*Repository.GetUsers`メソッドのテストを書いてみます。先に必要なモジュールを追加しましょう。

```sh
go get github.com/testcontainers/testcontainers-go
go get github.com/testcontainers/testcontainers-go/modules/localstack
```

テストを書いていきます。

```go:main_test.go
package main

import (
	"context"
	"os"
	"testing"

	"github.com/aws/aws-sdk-go-v2/aws"
	"github.com/aws/aws-sdk-go-v2/config"
	"github.com/aws/aws-sdk-go-v2/service/s3"
	"github.com/aws/aws-sdk-go-v2/service/s3/types"
	"github.com/docker/go-connections/nat"
	"github.com/google/go-cmp/cmp"
	"github.com/testcontainers/testcontainers-go"
	"github.com/testcontainers/testcontainers-go/modules/localstack"
)

const (
	region = "ap-northeast-1"
)


func TestRepository_GetUsers(t *testing.T) {
	// 説明のわかりやすさのためテーブルドリブンテストにはしません
	t.Setenv("AWS_ACCESS_KEY_ID", "dummy")     // 何かしらの値が必要
	t.Setenv("AWS_SECRET_ACCESS_KEY", "dummy") // 何かしらの値が必要
	ctx := context.Background()

	c, _ := localstack.Run(ctx, "localstack/localstack:3.7.2")
	defer func(c *localstack.LocalStackContainer) {
		testcontainers.TerminateContainer(c)
	}(c)

	provider, _ := testcontainers.NewDockerProvider()
	defer provider.Close()

	// 立ち上がったLocalStackコンテナのエンドポイントを割り出す
	host, _ := provider.DaemonHost(ctx)
	port, _ := c.MappedPort(ctx, nat.Port("4566/tcp"))
	awsEndpoint := "http://" + host + ":" + port.Port()

	awsCfg, _ := config.LoadDefaultConfig(ctx, config.WithRegion(region))
	client := s3.NewFromConfig(awsCfg, func(o *s3.Options) {
		o.UsePathStyle = true
		o.BaseEndpoint = aws.String(awsEndpoint)
	})
	initBucket(t, ctx, client, "test-bucket", "./dev/users.json", "users.json")

	// テスト用のクライアントをDIする
	repository := NewRepository(client)
	users := repository.GetUsers(ctx, "test-bucket", "users.json")

	want := []User{{ID: 1}}
	if diff := cmp.Diff(want, users); diff != "" {
		t.Error(diff)
	}
}

// バケットを作成し初期ファイルを配置する
func initBucket(
	t *testing.T,
	ctx context.Context,
	client *s3.Client,
	bucket, localPath, s3Key string,
) error {
	t.Helper()

	client.CreateBucket(ctx, &s3.CreateBucketInput{
		Bucket: aws.String(bucket),
		CreateBucketConfiguration: &types.CreateBucketConfiguration{
			LocationConstraint: types.BucketLocationConstraint(region),
		},
	})

	f, _ := os.Open(localPath)
	defer f.Close()

	client.PutObject(ctx, &s3.PutObjectInput{
		Bucket: aws.String(bucket),
		Key:    aws.String(s3Key),
		Body:   f,
	})
	return nil
}
```

`testcontainers-go`を使ったコンテナ立ち上げの基本は[公式リファレンス](https://golang.testcontainers.org/modules/localstack/#__tabbed_6_2)に倣っています。ポイントは...

- `host`と`port`を取得してエンドポイントURLを割り出します。
- 環境変数に`AWS_ACCESS_KEY_ID`と`AWS_SECRET_ACCESS_KEY`が必要です。(値は問わず)

:::message
アプリケーションコードと共通する処理が散見されるので、まだまだリファクタリングのしがいがありますが、いったんこのままにします。
:::

複数のテストでコンテナを使い回そうと思うと`TestMain`で立ち上げ処理を行うことも考えられますが、環境変数の設定には`t.Setenv`を使いたいところもあるので、何がベストプラクティスなのかなぁ？というのは私は理解できていません。ご存じの方はぜひご教示ください。

なお、本記事では深くは触れませんが、以前同一モジュール下の複数パッケージで`testcontainers-go`を使うテストを書いたところ、フレーキーなテストになってしまったことがありました。[このあたり](https://golang.testcontainers.org/features/configuration/#customizing-ryuk-the-resource-reaper)を参考にryukの設定を整えたところ解消しましたので、もし同じような課題にぶつかった方がいれば参照してみてください。

これで気軽にAWS環境(仮想)を使ったテストが出来ますね、やりました！🥂

## おわりに
本記事ではローカル開発環境とテストの両方でLocalStackを活用し、Go言語のアプリケーション開発を進める方法を整理しました。とても便利なツールなのでバンバン活用していきたいと思います。
今回は使いませんでしたが、LocalStackのリソースをTerraformで構築することもできるので、今後トライしてみようと思います。

## 参考
### ローカル環境開発編
- Docker Composeを使ったLocalStackの導入: https://docs.localstack.cloud/getting-started/installation/#docker-compose
- ヘルスチェック: https://docs.localstack.cloud/references/internal-endpoints/
- 初期化フック: https://docs.localstack.cloud/references/init-hooks/
- AWS SDKとの統合: https://docs.localstack.cloud/user-guide/integrations/sdks/go/

### テスト編
- `testcontainers-go`の導入: https://golang.testcontainers.org/quickstart/
- LocalStackモジュールを使う: https://golang.testcontainers.org/modules/localstack/#__tabbed_6_2