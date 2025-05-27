---
title: "Python再訪:柔軟かつ複雑さを抑えた実装を考える"
emoji: "🐍"
type: "tech" # tech: 技術記事 / idea: アイデア
topics: ["python", "pydantic", "taggedunion", "型"]
published: false
---

## はじめに
筆者は普段、趣味でGoを書き仕事で諸々のWebフレームワークを触っています。昔データ解析のために書き捨てのPythonを書いたことはありますが、ある程度の規模のPythonプログラムは書いたことがありません。この度仕事でPythonに再会する機会があり、「あ、こういうことが出来るんだ！」との気づきがあったため記事にまとめることにしました。

### 本記事の着地点
- リクエストに応じて振る舞いを多様に変えるAPIを設計。
- `Tagged Union`により複雑さを抑えたAPIリクエストを実現。
- ソフトウェア内部では`ダックタイピング`で振る舞いを変える。
- 上記を実現するために`Pydantic`と組み込みの`Protocol`を使用する。

この着地点に向かって、段階的にコードを改善していく過程を説明します。

### 本記事の対象読者
- Pythonを使って柔軟かつ複雑さを抑えた実装をしてみたい人。
- (軽くしか触れませんが)型の活用が好きな人。

### お願い事項
はじめに記載したように筆者はPythonの熟練者ではありません。他言語の考え方を持ち込んでいる部分も多々あり、Pythonとしてのベストプラクティスではない設計・実装をしている可能性があります。もしお気づきのことやアドバイスがございましたら、コメントで優しくご教示頂ければ幸いです。

### 前提条件
- Python3.10以降

### 結び
次章では、サンプルアプリケーションを通じて「柔軟かつ複雑さを抑えた」実装を考えてみます。ワクワクしますね。

それでは始めましょう！

## サンプルアプリケーションの作成
### サンプルアプリケーションの仕様
**注文を受けてドリンクを提供するサービスのAPI**を公開するアプリケーションを作るものとします。
- 提供するドリンクはコーヒーか緑茶。
- コーヒーの場合は全てお任せ設定にするか、コーヒー豆の銘柄と濃さをカスタマイズ設定するかを選べる。
- 緑茶の場合はお茶の産地を選ぶことができる。
- 紙コップか持ち込みのマグカップのどちらにも注ぐことができる。

このAPIのシグネチャを以下のように定義します。注文を表すリクエスト`event`を受け取るものとして、`event`はPythonの辞書型で表現されるものとします。(これはAWS LambdaのPythonランタイムにおけるハンドラーをイメージしています。)

```python
def handler(event: dict) -> dict:
    # do something
```

HTTPのPOSTリクエストで送信されたJSONがミドルウェアで`event`に変換されるものとします。`handler`が担うのはそこから先ということですね。

愚直にアプリケーションの仕様を`handler`の中に書いていくとこうなります。

```python
def handler(event: dict) -> dict:
    drink_type = event.get('drink_type')
    if drink_type is None:
        return {'statusCode': 400, 'body': 'drink_type is required'}
    
    cup_type = event.get('cup_type')
    # エラーハンドリング省略
    
    match drink_type:
        case 'coffee':
            mode = event.get('mode')
            if mode is None:
                return {'statusCode': 400, 'body': 'coffee serving mode is required'}
            match mode:
                case 'auto':
                    # ドリンクをカップに注ぐ処理
                case 'custom':
                    # コーヒー豆の銘柄を表すキーと、濃さを表すキーがあるかを確認し、処理を進めていきます。
                    # さすがに記載を省略します。
                case _:
                    # 想定していない例外ケースです。
        case 'green_tea':
            # 同じように処置していきます。
```

対応するHTTPリクエストのボディは、例えばこのようなものが考えられます。(いろいろな設計が考えられると思います。あくまで一例。)

```json:コーヒーの場合
{
    "drink_type": "coffee",
    "mode": "custom",
    "bean": "famous_coffee",
    "density": "high"
}
```
```json:緑茶の場合
{
    "drink_type": "green_tea",
    "region": "famous_region"
}
```

条件分岐を繰り返してリクエストを捌いていくため、本質的ではない処理が嵩んでしまいますね。また想定しないリクエストに対する処理も必要で複雑度が高いです。

このコードの複雑度を下げていきましょう。次節からコードを段階的に改善していきます。

### Pydanticでリクエストを検証する
普段Pythonを触らない筆者でも名前を知っている**Pydantic**を使っていきます。Pydanticの概要については[公式ドキュメントのGetting Started](https://docs.pydantic.dev/latest/)を参照ください。

先ほどのコードをPydanticの`BaseModel`を使ってざっくり書き直していきます。**まずは、いまいち複雑度を下げられないパターンです。**

それぞれのパラメータを`Literal`で定め、「コーヒーの場合は」のようなオプショナルなパラメータは`Literal[] | None`のように定めて、カスタムバリデーションで必要なパラメータをチェックします。

```python
from typing import Literal

from pydantic import BaseModel, model_validator


class ServeRequest(BaseModel):
    drink_type: Literal["coffee", "green_tea"]
    cup_type: Literal["paper_cup", "my_cup"]
    mode: Literal["auto", "custom"] | None = None
    bean: Literal["famous_coffee", "other_coffee"] | None = None
    density: Literal["high", "mid", "low"] | None = None
    region: Literal["famous_region", "other_region"] | None = None

    @model_validator(mode='after')
    def validate_coffee_fields(self) -> 'ServeRequest':
        if self.drink_type != "coffee":
            return self
        if self.mode is None:
            raise ValueError("mode is required")
```

この変更により、先ほどの`handler`のコードは次のように修正できます。

```python
def handler(event: dict) -> dict:
    # バリデーションはここで一撃で完了
    # エラーハンドリングは割愛しています
    request = ServeRequest.model_validate(event)

    match request.drink_type:
        case "coffee":
            match request.mode:
                case "auto":
                    # いろいろ
                case "custom":
                    # いろいろ
        case "green_tea":
            # いろいろ
```

リクエストのバリデーションをPydanticに移譲できるため、処理の中にバリデーションが都度都度混ざることが無くなり見通しが良くなりました。

ただし**パラメータの組み合わせはカスタムバリデーションで確認しており、複雑さを他に押し付けただけ**とも言えます。

なぜ複雑さを下げられないのか。Naoya Itoさんのスライド(p.55)を引用しますが、ありえないパターンも含めた**直積**の組み合わせから、有効な組み合わせを検証するためなんですね。そこで**直和**型のアプローチへと考え方を変えてみます。

@[speakerdeck](ed40eb21f5be431395028ee3777ca727)


```python
from typing import Literal

from pydantic import BaseModel, Field

class CoffeeAutoMode(BaseModel):
    mode: Literal["auto"] = "auto"

class CoffeeCustomMode(BaseModel):
    mode: Literal["custom"] = "custom"
    bean: Literal["famous_coffee", "other_coffee"]
    density: Literal["high", "mid", "low"]

class Coffee(BaseModel):
    drink_type: Literal["coffee"] = "coffee"
    serve_mode: CoffeeAutoMode | CoffeeCustomMode = Field(discriminator="mode")

class GreenTea(BaseModel):
    drink_type: Literal["green_tea"] = "green_tea"
    region: Literal["famous_region", "other_region"]

class ServeRequest(BaseModel):
    drink: Coffee | GreenTea = Field(discriminator="drink_type")
    cup_type: Literal["paper_cup", "my_cup"]
```

お気づきでしょうか、**すべての`| None`が消えました。**
上記のコードでは`CoffeeServer | GreenTeaServer`のようにユニオン(直和)を使い、クラスを判別するために`discriminator`で判別用の**タグ**を指定しています。**Tagged Union(タグ付きユニオン)** と呼ばれるパターンですね。

https://pydantic.com.cn/ja/concepts/unions/#str

コーヒーを提供する場合の`auto`と`custom`についても同様に処理しています。これにより、複雑なカスタムバリデーションが全て消え、入力を受けて直接的に`ServeRequest`が得られるようになりました。**これは便利だ。**

`handler`のコードはあまり変わりません。

```python
def handler(event: dict) -> dict:
    request = ServeRequest.model_validate(event)

    match request.drink:
        case Coffee():
            match request.drink.serve_mode:
                case CoffeeAutoMode():
                    # いろいろ
                case CoffeeCustomMode():
                    # いろいろ
        case GreenTea():
            # いろいろ
```

ここまででグッと複雑度は下がりましたが、まだ気になるところがあります。**変化に対する柔軟性を高めたいですね。** 例えば提供するドリンクの種類が増えるようなケースは十分に考えられます。

こんな時こそ**抽象化**ですね。筆者はPythonにおける抽象化の実現方法は`abc`(AbstractClassの意)だけだと思っていたのですが、`typing.Protocol`という仕組みがあることを知りました。今回は`Protocol`を活用して変化に対する柔軟性を高め、より良いアプリケーションコードに至りたいと思います。

### `Protocol`を使ったダックタイピング
`abc`と`Protocol`が提供するのは、それぞれ`抽象基底クラス`と`構造的サブタイプ`と捉えられます。

https://docs.python.org/ja/3.13/library/abc.html
https://typing.python.org/en/latest/spec/protocol.html

構造的サブタイプでは、振る舞いを満足するものは全て代入可能となります。例えば以下のようなものです。
```python
from abc import abstractmethod
from typing import Protocol


class Animal(Protocol):
    @abstractmethod
    def run(self) -> None:
        pass

class Dog():
    def run(self) -> None:
        # do something

def run_animal(animal: Animal) -> None:
    animal.run()

d = Dog()
run_animal(d) # 実行可能
```

「ガァ」と鳴くものは全てアヒル、つまりダックタイピングが可能になるんですね。

`abc`と`Protocol`の使い分けですが、公式ドキュメントを参照して以下のように解釈しました。

- `abc`: クラス継承による明示的な抽象化が必要な場合
- `Protocol`: 振る舞いの一致のみを重視する場合

筆者自身がGo言語の`interface`になじみがあることもあり、似た性質の`Protocol`を採用してみます。`Protocol`の仕組みを活かして先ほどのコードを改善していきましょう。

まず、少し後出しになってしまいますが、先ほどTagged Unionを使用した修正結果を一部変更します。`Coffee`のような「物」ではなく`CoffeeServer`のような「ふるまいの主体」であるとして、`cup_type`を受け取って飲み物を注ぐ`serve`というふるまいを持つことにします(簡単のため、戻り値はNoneにします)。併せて、`cup_type`のリテラルも個別に定義しておきます。


```python
from typing import Literal

from pydantic import BaseModel, Field


CupType = Literal["paper_cup", "my_cup"]

# 変化なし
class CoffeeAutoMode(BaseModel):
    mode: Literal["auto"] = "auto"

# 変化なし
class CoffeeCustomMode(BaseModel):
    mode: Literal["custom"] = "custom"
    bean: Literal["famous_coffee", "other_coffee"]
    density: Literal["high", "mid", "low"]

class CoffeeServer(BaseModel):
    drink_type: Literal["coffee"] = "coffee"
    serve_mode: CoffeeAutoMode | CoffeeCustomMode = Field(discriminator="mode")

    def serve(self, cup_type: CupType) -> None:
        # do something
        # 処理の詳細は`serve_mode`に応じて内部的に変更する

class GreenTeaServer(BaseModel):
    drink_type: Literal["green_tea"] = "green_tea"
    region: Literal["famous_region", "other_region"]

    def serve(self, cup_type: CupType) -> None:
        # do something

class ServeRequest(BaseModel):
    drink_server: CoffeeServer | GreenTeaServer = Field(discriminator="drink_type")
    cup_type: CupType
```

このように変更しても先ほど導入したTagged Unionは同様に働きます。リクエストを検証することで、`serve`というふるまいを持つクラスのインスタンスが生成できるんですね。

`handler`を変更してみます。

```python
from abc import abstractmethod
from typing import Protocol

class DrinkServer(Protocol):
    @abstractmethod
    def serve(self, cup_type: CupType) -> None:
        pass

def serve_drink(server: DrinkServer, cup_type: CupType) -> None:
    server.serve(cup_type)

def handler(event: dict) -> dict:
    request = ServeRequest.model_validate(event)
    serve_drink(request.drink_server, request.cup_type)
    return {"statusCode": 200}
```

**`handler`の中身が激減しました。**
説明の都合上、中身のほとんどない`serve_drink`という関数を作成しています。`Protocol`を使用することで、`serve`メソッドを持つ任意のクラスを`DrinkServer`型として扱うことができます。これにより、新しい飲み物の種類を追加する際も、`serve`メソッドを持つクラスを実装するだけで既存のコードを変更することなく対応できます。

:::message
`ServeRequest`クラスは`CoffeeServer | GreenTeaServer`のように使用可能な`DrinkServer`の実装クラスをUnionで指定しているため、飲み物の種類が増えたらクラスを追加していく必要があります。これは、このアプリケーションが提供可能なサービスを明示する必要があるため、抽象ではなく具象で記述するべき内容であるからです。
:::

:::message
型のことを考えなければ`request.drink_server.serve(request.cup_type)`とするだけで実質問題はありません。
:::

:::message
Visual Studio Code などのIDEを使用している方は、`DrinkServer`の「実装を表示」などを試してみると、たしかに`CoffeeServer`や`GreenTeaServer`が`DrinkServer`を実装していることが確認できると思います。お試しください。
:::

**`Protocol`を使用することで、複雑さは抑えたまま変化に対する柔軟性を獲得することができました！**

## おわりに

本記事では、Pythonを使って柔軟かつ複雑さを抑えた実装について考えてきました。特に以下の点に注目して解説を進めました：

- Pydanticを使用してリクエスト検証の複雑さを低減
  - 特にTagged Unionによる直和型での複雑さ低減
- Protocolを活用したダックタイピングによる柔軟な設計

筆者自身、他言語からPythonに再会して「へぇ、こんな良い仕組みがあったのか」と新鮮な驚きがありました。型の活用やインターフェースの考え方など、言語を渡り歩いて実践できるテクニックを見出せたことが興味深かったです。

本記事で紹介した実装パターンが、みなさんのPythonプログラミングの一助となれば幸いです。
