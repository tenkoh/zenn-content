---
title: "Pydantic TypeAdapterでサクサク型付けデシリアライズ"
emoji: "🔌"
type: "tech" # tech: 技術記事 / idea: アイデア
topics: ["python", "pydantic", "型"]
published: false
---

## はじめに
最近、仕事の中でPythonを触る機会が増え続けています。そんな中、以下のようなJSONをデシリアライズするシーンに出会いました。

```json
{
    "model_name": "compact",
    "weight": 1.5
}
```

```json
{
    "model_name": "powerful",
    "turbo": "true"
}
```

このように、「**識別に使えそうな共通のキーはあるが、それ以外のキーが全く異なるようなJSON**」を読み込んでデシリアライズし、後続で異なる処理を行っていくというものです。

愚直に辞書として読み込んだ後に`model_name`を参照して条件分岐を書くこともできますが、せっかくであれば型やクラスを活用していきたいですね？（押し付け）

そこで本記事では以下のようなゴールを設定します。
```python
# これは CompactMachine クラスになる
machine = 何かの処理({"model_type": "compact", "weight": 1.5})

# これは PowerfulMachine クラスになる
machine = 何かの処理({"model_type": "poerful", "turbo": "true"})
```

さあ、これを実現する「何かの処理」はいったい何があるのでしょうか？

## 前提条件
- Python3.10以上
- Pydantic v2以上

## 本記事の対象読者
- PythonでJSONをデシリアライズした結果を適切なクラスに動的にキャストしたい人
- Pydanticが好きな人

## Pydanticのdiscriminator
筆者の以前の記事では、次のような **データの一部が異なるJSON** をPydanticを使って型安全に扱うことをトライしました。

```jsonp
// drink_typeによって、drinkが持つフィールドが異なる。
{
    "drink": {
        "drink_type": "coffee",
        "serve_mode": {
            // 省略
        }
    },
    "cup_type": "paper_cup"
}

{
    "drink": {
        "drink_type": "green_tea",
        "region": "famous_region"
    },
    "cup_type": "my_cup"
}
```

このケースではPydanticのFieldで **discriminator** を活用することができました。

```python
class Coffee(BaseModel):
    drink_type: Literal["coffee"] = "coffee"
    serve_mode: # 省略

class GreenTea(BaseModel):
    drink_type: Literal["green_tea"] = "green_tea"
    region: Literal["famous_region", "other_region"]

class ServeRequest(BaseModel):
    drink: Coffee | GreenTea = Field(discriminator="drink_type")
    cup_type: Literal["paper_cup", "my_cup"]

# ServeRequest.drink は Coffee クラス
req = ServeRequest.model_validate({
    "drink_type": "coffee",
    "serve_mode": # 省略
})

# ServeRequest.drink は GreenTea クラス
req = ServeRequest.model_validate({
    "drink_type": "green_tea",
    "region": # 省略
})
```

こちらの詳細を知りたい場合は、ぜひ下記の記事もご覧ください。
https://zenn.dev/foxtail88/articles/flexible_robust_python

しかし今回のケースは **クラスのプロパティの一部を異なるクラスとしてデシリアライズしたいのではなく、丸ごと異なるクラスとして扱いたい** ため異なるケースです。他の手段を探す必要があると分かりました。

## PydanticのTypeAdapter
理想の手段を求め、筆者はPydanticの森を彷徨いました。。。

そしてついに見つけたのです、**TypeAdapter**を…！

https://docs.pydantic.dev/latest/api/type_adapter/#pydantic.type_adapter.TypeAdapter.json_schemas

TypeAdapterを使うことで、下記のような処理が実現できます。

```python
from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field, TypeAdapter


class CompactMachine(BaseModel):
    model_name: Literal["compact"]
    weight: float


class PowerfulMachine(BaseModel):
    model_name: Literal["powerful"]
    turbo: Literal["true", "false"]

MachineAdapter = TypeAdapter(CompactMachine | PowerfulMachine)

compact_json = {
    "model_name": "compact",
    "weight": 1.5,
}

powerful_json = {
    "model_name": "powerful",
    "turbo": "true",
}

compact = MachineAdapter.validate_python(compact_json)
powerful = MachineAdapter.validate_python(powerful_json)

print(compact)
print(type(compact))
print(powerful)
print(type(powerful))
```
**簡潔だ…!!**

playground: https://pydantic.run/store/ba10a1ade69d2c98



ちなみに、先ほどのように何を識別に使うか明示しなくても上手くいく例もありますが、明示しておくにこしたことはありません。
その場合は`typing.Annotated`と`pydantic.Field`を併用して以下のように書けます。

```python
# model_name で判別する Union 型
Machine = Annotated[
    CompactMachine | PowerfulMachine,
    Field(discriminator="model_name"),
]

MachineAdapter = TypeAdapter(Machine)
```

つまり、冒頭の`何かの処理`は`TypeAdapter.validate_python`だったんですね！ありがとうPydantic…！

## おわりに
Pydanticを使うことで、デシリアライズした結果を異なるクラスとして扱うことが非常にシンプルに実現できました。
今後もこうしたテクニックを身につけて、型安全で楽しいPythonライフを送りたいと思います。