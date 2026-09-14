import os
import json
import boto3
from boto3.dynamodb.conditions import Key

dynamodb = boto3.resource("dynamodb")

leave_balances_table = dynamodb.Table(
    os.environ["LEAVE_BALANCES_TABLE"]
)


def response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type",
            "Access-Control-Allow-Methods": "GET,OPTIONS"
        },
        "body": json.dumps(body)
    }


def lambda_handler(event, context):

    if event.get("httpMethod") == "OPTIONS":
        return response(200, {"message": "CORS OK"})

    employee_id = (
        event.get("queryStringParameters") or {}
    ).get("employee_id")

    if not employee_id:
        return response(
            400,
            {"message": "employee_id is required"}
        )

    try:
        result = leave_balances_table.query(
            KeyConditionExpression=Key("employee_id").eq(employee_id)
        )

        balances = []

        for item in result.get("Items", []):
            balances.append({
                "leave_type_year": item.get("leave_type_year"),
                "allocated": int(item.get("allocated", 0)),
                "used": int(item.get("used", 0)),
                "remaining": int(item.get("remaining", 0)),
                "carry_forward": int(item.get("carry_forward", 0))
            })

        return response(
            200,
            {
                "employee_id": employee_id,
                "balances": balances
            }
        )

    except Exception as e:
        print("Error:", str(e))

        return response(
            500,
            {
                "message": "Unable to fetch leave balance",
                "error": str(e)
            }
        )