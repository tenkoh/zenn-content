def handler(event: dict) -> dict:
    drink_type = event.get('drink_type')
    if drink_type is None:
        return {"statusCode": 400, "body": 'drink_type is required'}
    
    cup_type = event.get('cup_type')
    if cup_type is None:
        return {"statusCode": 400, "body": 'cup_type is required'}
    if cup_type not in ["paper_cup", "my_cup"]:
        return {"statusCode": 400, "body": 'invalid cup_type'}
    
    match drink_type:
        case 'coffee':
            mode = event.get('mode')
            if mode is None:
                return {"statusCode": 400, "body": 'coffee serving mode is required'}
            match mode:
                case 'auto':
                    print(f"Serving auto coffee in {cup_type}")
                    return {"statusCode": 200, "body": "served auto coffee"}
                case 'custom':
                    bean = event.get('bean')
                    if bean is None:
                        return {"statusCode": 400, "body": 'bean is required for custom mode'}
                    if bean not in ["famous_coffee", "other_coffee"]:
                        return {"statusCode": 400, "body": 'invalid bean type'}
                    
                    density = event.get('density')
                    if density is None:
                        return {"statusCode": 400, "body": 'density is required for custom mode'}
                    if density not in ["high", "mid", "low"]:
                        return {"statusCode": 400, "body": 'invalid density'}
                    
                    print(f"Serving custom coffee with {bean} bean at {density} density in {cup_type}")
                    return {"statusCode": 200, "body": "served custom coffee"}
                case _:
                    return {"statusCode": 400, "body": 'invalid coffee mode'}
        case 'green_tea':
            region = event.get('region')
            if region is None:
                return {"statusCode": 400, "body": 'region is required for green tea'}
            if region not in ["famous_region", "other_region"]:
                return {"statusCode": 400, "body": 'invalid region'}
            
            print(f"Serving green tea from {region} in {cup_type}")
            return {"statusCode": 200, "body": "served green tea"}
        case _:
            return {"statusCode": 400, "body": 'invalid drink type'}

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
