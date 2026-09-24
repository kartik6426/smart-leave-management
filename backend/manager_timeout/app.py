import json
import os
import boto3
from datetime import datetime, timezone, timedelta
from boto3.dynamodb.conditions import Attr

dynamodb = boto3.resource("dynamodb")

LEAVE_REQUESTS_TABLE = os.environ.get(
    "LEAVE_REQUESTS_TABLE",
    "leave_requests_dev"
)

SES_EMAIL = os.environ.get("SES_EMAIL", "")

leave_requests_table = dynamodb.Table(LEAVE_REQUESTS_TABLE)
ses = boto3.client("ses")


def lambda_handler(event, context):
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=48)

    response = leave_requests_table.scan(
        FilterExpression=Attr("status").eq("PENDING_MANAGER")
    )

    requests = response.get("Items", [])
    timed_out = []

    for leave in requests:
        created_at = leave.get("created_at")

        if not created_at:
            continue

        try:
            created_time = datetime.fromisoformat(
                created_at.replace("Z", "+00:00")
            )
        except Exception:
            continue

        if created_time <= cutoff:
            employee_id = leave.get("employee_id")
            request_id = leave.get("request_id")

            leave_requests_table.update_item(
                Key={
                    "employee_id": employee_id,
                    "request_id": request_id
                },
                UpdateExpression="""
                    SET #status = :status,
                        timeout_reason = :reason,
                        timed_out_at = :timed_out_at
                """,
                ExpressionAttributeNames={
                    "#status": "status"
                },
                ExpressionAttributeValues={
                    ":status": "MANAGER_TIMEOUT",
                    ":reason": "Manager did not respond within 48 hours",
                    ":timed_out_at": now.isoformat()
                }
            )

            employee_email = leave.get("employee_email") or SES_EMAIL

            if employee_email and SES_EMAIL:
                ses.send_email(
                    Source=SES_EMAIL,
                    Destination={
                        "ToAddresses": [employee_email]
                    },
                    Message={
                        "Subject": {
                            "Data": "Leave Request - Manager Response Timeout"
                        },
                        "Body": {
                            "Text": {
                                "Data": (
                                    f"Your leave request {request_id} "
                                    f"did not receive manager action within "
                                    f"48 hours and has been marked as "
                                    f"MANAGER_TIMEOUT."
                                )
                            }
                        }
                    }
                )

            timed_out.append(request_id)

    return {
        "statusCode": 200,
        "body": json.dumps({
            "message": "Manager timeout check completed",
            "timed_out_requests": timed_out,
            "count": len(timed_out)
        })
    }