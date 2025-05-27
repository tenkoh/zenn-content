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


def main():
    # コーヒー（auto mode）のリクエスト例
    coffee_auto_request = {
        "drink": {
            "drink_type": "coffee",
            "serve_mode": {
                "mode": "auto"
            }
        },
        "cup_type": "paper_cup"
    }
    
    # コーヒー（custom mode）のリクエスト例
    coffee_custom_request = {
        "drink": {
            "drink_type": "coffee",
            "serve_mode": {
                "mode": "custom",
                "bean": "famous_coffee",
                "density": "high"
            }
        },
        "cup_type": "my_cup"
    }
    
    # 緑茶のリクエスト例
    green_tea_request = {
        "drink": {
            "drink_type": "green_tea",
            "region": "famous_region"
        },
        "cup_type": "paper_cup"
    }
    
    # リクエストの検証
    requests = [coffee_auto_request, coffee_custom_request, green_tea_request]
    
    for req in requests:
        request = ServeRequest.model_validate(req)
        print(f"Validated request: {request.model_dump_json(indent=2)}")
        
        # パターンマッチングの例
        match request.drink:
            case Coffee():
                match request.drink.serve_mode:
                    case CoffeeAutoMode():
                        print("Serving coffee in auto mode")
                    case CoffeeCustomMode():
                        print(f"Serving coffee with {request.drink.serve_mode.bean} beans at {request.drink.serve_mode.density} density")
            case GreenTea():
                print(f"Serving green tea from {request.drink.region}")
        print("-" * 50)


if __name__ == "__main__":
    main()
