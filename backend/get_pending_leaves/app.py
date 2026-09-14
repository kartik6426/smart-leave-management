import os
import json
import boto3

dynamodb = boto3.resource("dynamodb")

LEAVE_REQUESTS_TABLE = os.environ.get(
    "LEAVE_REQUESTS_TABLE",
    "leave_requests_dev"
)

leave_requests_table = dynamodb.Table(LEAVE_REQUESTS_TABLE)


def response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type",
            "Access-Control-Allow-Methods": "GET,OPTIONS"
        },
        "body": json.dumps(body, default=str)
        
    }


def lambda_handler(event, context):
    try:
        scan_response = leave_requests_table.scan()

        items = scan_response.get("Items", [])

        pending_requests = [
            item for item in items
            if item.get("status") == "PENDING_MANAGER"
        ]

        pending_requests.sort(
            key=lambda x: x.get("created_at", ""),
            reverse=True
        )

        return response(
            200,
            {
                "message": "Pending manager requests retrieved successfully",
                "count": len(pending_requests),
                "requests": pending_requests
            }
        )

    except Exception as e:
        print("ERROR:", str(e))

        return response(
            500,
            {
                "message": "Internal server error",
                "error": str(e)
            }
        )