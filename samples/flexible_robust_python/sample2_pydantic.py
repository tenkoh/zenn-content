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
        if self.drink_type == "coffee":
            if self.mode is None:
                raise ValueError("mode is required for coffee")
            if self.mode == "custom":
                if self.bean is None:
                    raise ValueError("bean is required for custom coffee")
                if self.density is None:
                    raise ValueError("density is required for custom coffee")
        elif self.drink_type == "green_tea":
            if self.region is None:
                raise ValueError("region is required for green tea")
        return self


def handler(event: dict) -> dict:
    try:
        request = ServeRequest.model_validate(event)
    except Exception as e:
        return {"statusCode": 400, "body": str(e)}

    match request.drink_type:
        case "coffee":
            match request.mode:
                case "auto":
                    print(f"Serving auto coffee in {request.cup_type}")
                    return {"statusCode": 200, "body": "served auto coffee"}
                case "custom":
                    print(f"Serving custom coffee with {request.bean} bean at {request.density} density in {request.cup_type}")
                    return {"statusCode": 200, "body": "served custom coffee"}
        case "green_tea":
            print(f"Serving green tea from {request.region} in {request.cup_type}")
            return {"statusCode": 200, "body": "served green tea"}

    return {"statusCode": 500, "body": "unexpected error"}


if __name__ == "__main__":
    # Test cases
    test_cases = [
        {
            "drink_type": "coffee",
            "mode": "auto",
            "cup_type": "paper_cup"
        },
        {
            "drink_type": "coffee",
            "mode": "custom",
            "bean": "famous_coffee",
            "density": "high",
            "cup_type": "my_cup"
        },
        {
            "drink_type": "green_tea",
            "region": "famous_region",
            "cup_type": "paper_cup"
        }
    ]
    
    for case in test_cases:
        print(f"\nTesting with input: {case}")
        result = handler(case)
        print(f"Result: {result}")
