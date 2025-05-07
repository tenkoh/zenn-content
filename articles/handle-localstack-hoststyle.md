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
    1. S3のパス形式
    1. AWS SDKのエンドポイントオプション
1. サンプルアプリケーション
    1. AppコンテナのAWS SDKのエンドポイントおよびネットワーク設定
    1. ホストからの名前解決の仕組み
1. おまけ: LocalStackのLambdaを使う場合のAWS SDKのエンドポイント

それでは始めましょう！

## 前提知識
冒頭に示した構成において制約として記載した「仮想ホスト形式」のパスとは何なのか、図中に示した「AWS SDK Endpoint」とは何なのか。今後の説明に必要なこの２点を説明します。

### S3のパス形式
パブリックアクセス可能なS3バケット内のオブジェクトへのアクセスや、署名付きURLを使用したS3バケット内のオブジェクトへのアクセスにおいて、そのURLは**仮想ホスト形式**と**パス形式**の両方が有効です。

https://docs.aws.amazon.com/ja_jp/AmazonS3/latest/userguide/VirtualHosting.html

:::message
ただし上記ドキュメントに記載されているように**パス形式**は将来的に廃止予定です。
:::

仮想ホスト形式は`https://your-bucket.s3.region-code.amazonaws.com/your-object-key`のようなバケット名をホスト名の一部として使用するものです。一方でパス形式は`https://s3.region-code.amazonaws.com/your-bucket/your-object-key`のようにバケット名をパスの一部として使用するものです。

ここで`s3.region-code.amazonaws.com`の

### AWS SDKのエンドポイントオプション

## サンプルアプリケーション
### AppコンテナのAWS SDKのエンドポイントおよびネットワーク設定
### ホストからの名前解決の仕組み

## おまけ: LocalStackのLambdaを使う場合のAWS SDKのエンドポイント

## おわりに
