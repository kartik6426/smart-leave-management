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

        query_params = event.get("queryStringParameters") or {}
        view = query_params.get("view", "pending")

        if view == "all":
            requests = items
            message = "All leave requests retrieved successfully"
        else:
            requests = [
                item for item in items
                if item.get("status") == "PENDING_MANAGER"
            ]
            message = "Pending manager requests retrieved successfully"

        requests.sort(
            key=lambda x: x.get("created_at", ""),
            reverse=True
        )

        return response(
            200,
            {
                "message": message,
                "count": len(requests),
                "requests": requests
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