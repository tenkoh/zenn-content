from typing import Literal, Protocol
from pydantic import BaseModel, Field


CupType = Literal["paper_cup", "my_cup"]


class CoffeeAutoMode(BaseModel):
    mode: Literal["auto"] = "auto"


class CoffeeCustomMode(BaseModel):
    mode: Literal["custom"] = "custom"
    bean: Literal["famous_coffee", "other_coffee"]
    density: Literal["high", "mid", "low"]


class CoffeeServer(BaseModel):
    drink_type: Literal["coffee"] = "coffee"
    serve_mode: CoffeeAutoMode | CoffeeCustomMode = Field(discriminator="mode")

    def serve(self, cup_type: CupType) -> None:
        # do something
        print(f"Serving coffee in {cup_type}")
        match self.serve_mode:
            case CoffeeAutoMode():
                print("Using auto mode settings")
            case CoffeeCustomMode():
                print(f"Using custom settings - bean: {self.serve_mode.bean}, density: {self.serve_mode.density}")


class GreenTeaServer(BaseModel):
    drink_type: Literal["green_tea"] = "green_tea"
    region: Literal["famous_region", "other_region"]

    def serve(self, cup_type: CupType) -> None:
        # do something
        print(f"Serving green tea from {self.region} in {cup_type}")


class ServeRequest(BaseModel):
    drink_server: CoffeeServer | GreenTeaServer = Field(discriminator="drink_type")
    cup_type: CupType


class DrinkServer(Protocol):
    def serve(self, cup_type: CupType) -> None:
        pass


def serve_drink(server: DrinkServer, cup_type: CupType) -> None:
    server.serve(cup_type)


def handler(event: dict) -> dict:
    request = ServeRequest.model_validate(event)
    serve_drink(request.drink_server, request.cup_type)
    return {"statusCode": 200}


if __name__ == "__main__":
    # Test with coffee auto mode
    coffee_auto_event = {
        "drink_server": {
            "drink_type": "coffee",
            "serve_mode": {"mode": "auto"}
        },
        "cup_type": "paper_cup"
    }
    print("Testing coffee auto mode:")
    result = handler(coffee_auto_event)
    print(f"Result: {result}\n")

    # Test with coffee custom mode
    coffee_custom_event = {
        "drink_server": {
            "drink_type": "coffee",
            "serve_mode": {
                "mode": "custom",
                "bean": "famous_coffee",
                "density": "high"
            }
        },
        "cup_type": "my_cup"
    }
    print("Testing coffee custom mode:")
    result = handler(coffee_custom_event)
    print(f"Result: {result}\n")

    # Test with green tea
    green_tea_event = {
        "drink_server": {
            "drink_type": "green_tea",
            "region": "famous_region"
        },
        "cup_type": "paper_cup"
    }
    print("Testing green tea:")
    result = handler(green_tea_event)
    print(f"Result: {result}")