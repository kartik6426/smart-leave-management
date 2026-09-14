import os
import json
import boto3
from decimal import Decimal

dynamodb = boto3.resource("dynamodb")

leave_requests_table = dynamodb.Table(
    os.environ["LEAVE_REQUESTS_TABLE"]
)

leave_balances_table = dynamodb.Table(
    os.environ["LEAVE_BALANCES_TABLE"]
)

stepfunctions = boto3.client("stepfunctions")
ses = boto3.client("ses", region_name="ap-south-1")

STATE_MACHINE_ARN = os.environ.get("STATE_MACHINE_ARN")
SES_EMAIL = os.environ.get("SES_EMAIL")


def response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type",
            "Access-Control-Allow-Methods": "POST,OPTIONS"
        },
        "body": json.dumps(body)
    }

def send_email(subject, message):
    if not SES_EMAIL:
        print("SES_EMAIL is not configured")
        return False

    try:
        response = ses.send_email(
            Source=SES_EMAIL.strip(),
            Destination={
                "ToAddresses": [SES_EMAIL.strip()]
            },
            Message={
                "Subject": {
                    "Data": subject
                },
                "Body": {
                    "Text": {
                        "Data": message
                    }
                }
            }
        )

        print("SES email sent:", response.get("MessageId"))
        return True

    except Exception as email_error:
        print("SES email failed:", str(email_error))
        return False

def lambda_handler(event, context):

    try:
        # Read API Gateway request body
        body = event.get("body", event)

        if isinstance(body, str):
            body = json.loads(body)

        request_id = body.get("request_id")
        action = body.get("action")
        manager_id = body.get("manager_id", "MANAGER001")

        if not request_id or action not in ["approve", "reject", "hr_approve", "hr_reject"]:
            return response(
                400,
                {
                    "message": "request_id and valid action are required"
                }
            )

        # Find leave request
        scan_response = leave_requests_table.scan(
            FilterExpression="request_id = :rid",
            ExpressionAttributeValues={
                ":rid": request_id
            }
        )

        items = scan_response.get("Items", [])

        if not items:
            return response(
                404,
                {
                    "message": "Leave request not found"
                }
            )

        leave = items[0]

        employee_id = leave["employee_id"]
        leave_type = leave["leave_type"]
        days = int(leave["days"])

        current_status = leave.get("status")
        # -----------------------------
        # HR APPROVAL
        # -----------------------------

        if action in ["hr_approve", "hr_reject"]:

            if current_status != "PENDING_HR":
                return response(
                    400,
                    {
                        "message": f"Request is not pending HR approval. Current status: {current_status}"
                    }
                )

            if action == "hr_reject":

                leave_requests_table.update_item(
                    Key={
                        "employee_id": employee_id,
                        "request_id": request_id
                    },
                    UpdateExpression="SET #status = :status",
                    ExpressionAttributeNames={
                        "#status": "status"
                    },
                    ExpressionAttributeValues={
                        ":status": "REJECTED"
                    }
                )
            send_email(
                "Leave Request Rejected",
                f"Leave request {request_id} has been rejected by HR. "
                f"Employee: {employee_id}. "
                f"Leave type: {leave_type}. "
                f"Duration: {days} days."
            )

        if action == "hr_approve":
            # Deduct the approved leave balance
            balance_key = {
                "employee_id": employee_id,
                "leave_type_year": f"{leave_type}#2026"
            }

            balance_response = leave_balances_table.get_item(
                Key=balance_key
            )

            balance_item = balance_response.get("Item")

            if not balance_item:
                return response(
                    400,
                    {"message": "Leave balance record not found"}
                )

            remaining = int(balance_item.get("remaining", 0))
            used = int(balance_item.get("used", 0))

            if remaining < days:
                return response(
                    400,
                    {"message": "Insufficient leave balance"}
                )

            leave_balances_table.update_item(
                Key=balance_key,
                UpdateExpression="SET #remaining = :remaining, #used = :used",
                ExpressionAttributeNames={
                    "#remaining": "remaining",
                    "#used": "used"
                },
                ExpressionAttributeValues={
                    ":remaining": remaining - days,
                    ":used": used + days
                }
            )

            # Mark leave as finally approved
            leave_requests_table.update_item(
                Key={
                    "employee_id": employee_id,
                    "request_id": request_id
                },
                UpdateExpression="SET #status = :status, hr_id = :hr_id",
                ExpressionAttributeNames={
                    "#status": "status"
                },
                ExpressionAttributeValues={
                    ":status": "APPROVED",
                    ":hr_id": manager_id
                }
            )

            send_email(
                "Leave Request Approved",
                f"Your leave request {request_id} has been approved by HR."
            )

            return response(
                200,
                {"message": "HR approved the leave request"}
            )
        
            return response(
                    200,
                    {
                        "message": "HR rejected the leave request",
                        "request_id": request_id,
                        "status": "REJECTED"
                    }
                )

            # HR approved → deduct balance and finalize
            leave_type_year = f"{leave_type}#2026"

            balance_response = leave_balances_table.get_item(
                Key={
                    "employee_id": employee_id,
                    "leave_type_year": leave_type_year
                }
            )

            balance = balance_response.get("Item")

            if not balance:
                return response(
                    400,
                    {
                        "message": "Leave balance not found"
                    }
                )

            remaining = Decimal(
                str(balance.get("remaining", 0))
            )

            if Decimal(str(days)) > remaining:
                return response(
                    400,
                    {
                        "message": "Insufficient leave balance"
                    }
                )

            leave_balances_table.update_item(
                Key={
                    "employee_id": employee_id,
                    "leave_type_year": leave_type_year
                },
                UpdateExpression="""
                    SET used = :used,
                        remaining = :remaining
                """,
                ExpressionAttributeValues={
                    ":used": Decimal(str(balance.get("used", 0))) + Decimal(str(days)),
                    ":remaining": remaining - Decimal(str(days))
                }
            )

            leave_requests_table.update_item(
                Key={
                    "employee_id": employee_id,
                    "request_id": request_id
                },
                UpdateExpression="SET #status = :status",
                ExpressionAttributeNames={
                    "#status": "status"
                },
                ExpressionAttributeValues={
                    ":status": "APPROVED"
                }
            )

            return response(
                200,
                {
                    "message": "HR approved the leave request",
                    "request_id": request_id,
                    "status": "APPROVED",
                    "days": days
                }
            )

        if current_status != "PENDING_MANAGER":
            return response(
                400,
                {
                    "message": f"Request is not pending manager approval. Current status: {current_status}"
                }
            )

        # -----------------------------
        # MANAGER REJECTS
        # ------------------------------
        if action == "reject":

            leave_requests_table.update_item(
                Key={
                    "employee_id": employee_id,
                    "request_id": request_id
                },
                UpdateExpression="""
                    SET #status = :status,
                      manager_id = :manager_id
                """,
                ExpressionAttributeNames={
                    "#status": "status"
                },
                ExpressionAttributeValues={
                    ":status": "REJECTED",
                    ":manager_id": manager_id
                }
          )

            # Send rejection email to employee
            send_email(
              "Leave Request Rejected",
              f"Your leave request ({request_id}) has been rejected by your manager."
          )

            return response(
              200,
              {
                  
                  "message": "Leave request rejected",
                  "request_id": request_id,
                  "status": "REJECTED"
             }
           )

        # -----------------------------
        # MANAGER APPROVES
        # -----------------------------

        # If leave is more than 5 days,
        # HR approval is required.
        if days > 5:

            leave_requests_table.update_item(
                Key={
                    "employee_id": employee_id,
                    "request_id": request_id
                },
                UpdateExpression="""
                    SET #status = :status,
                        manager_id = :manager_id
                """,
                ExpressionAttributeNames={
                    "#status": "status"
                },
                ExpressionAttributeValues={
                    ":status": "PENDING_HR",
                    ":manager_id": manager_id
                }
            )

            # Start Step Functions workflow
            execution = stepfunctions.start_execution(
                stateMachineArn=STATE_MACHINE_ARN,
                input=json.dumps({
                    "request_id": request_id,
                    "employee_id": employee_id,
                    "leave_type": leave_type,
                    "days": days
                })
            )

            return response(
                200,
                {
                    "message": "Manager approved. HR approval is required.",
                    "request_id": request_id,
                    "status": "PENDING_HR",
                    "execution_arn": execution["executionArn"]
                }
            )

        # -----------------------------
        # FINAL APPROVAL FOR <= 5 DAYS
        # -----------------------------

        leave_type_year = f"{leave_type}#2026"

        balance_response = leave_balances_table.get_item(
            Key={
                "employee_id": employee_id,
                "leave_type_year": leave_type_year
            }
        )

        balance = balance_response.get("Item")

        if not balance:
            return response(
                400,
                {
                    "message": "Leave balance not found"
                }
            )

        remaining = Decimal(
            str(balance.get("remaining", 0))
        )

        if Decimal(str(days)) > remaining:
            return response(
                400,
                {
                    "message": "Insufficient leave balance"
                }
            )

        # Deduct balance
        leave_balances_table.update_item(
            Key={
                "employee_id": employee_id,
                "leave_type_year": leave_type_year
            },
            UpdateExpression="""
                SET used = :used,
                    remaining = :remaining
            """,
            ExpressionAttributeValues={
                ":used": Decimal(str(balance.get("used", 0))) + Decimal(str(days)),
                ":remaining": remaining - Decimal(str(days))
            }
        )

        # Mark request approved
        leave_requests_table.update_item(
            Key={
                "employee_id": employee_id,
                "request_id": request_id
            },
            UpdateExpression="""
                SET #status = :status,
                    manager_id = :manager_id
            """,
            ExpressionAttributeNames={
                "#status": "status"
            },
            ExpressionAttributeValues={
                ":status": "APPROVED",
                ":manager_id": manager_id
            }
        )
        send_email(
            "Leave Request Approved",
            f"Leave request {request_id} has been approved by the manager. "
            f"Employee: {employee_id}. "
            f"Leave type: {leave_type}. "
            f"Duration: {days} days."
        )
        return response(
            200,
            {
                "message": "Leave request approved",
                "request_id": request_id,
                "status": "APPROVED",
                "days": days
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