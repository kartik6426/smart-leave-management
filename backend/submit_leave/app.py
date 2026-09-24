import json
import os
import uuid
import base64
import hashlib
import hmac
import time
from urllib.parse import quote
from datetime import datetime, date

import boto3
sns = boto3.client("sns")
SNS_TOPIC_ARN = os.environ.get("SNS_TOPIC_ARN")
APPROVAL_SECRET = os.environ.get("APPROVAL_SECRET", "")
APPROVAL_BASE_URL = os.environ.get("APPROVAL_BASE_URL", "")
from boto3.dynamodb.conditions import Key


# ============================================================
# AWS RESOURCES
# ============================================================

dynamodb = boto3.resource("dynamodb")

LEAVE_REQUESTS_TABLE = os.environ.get(
    "LEAVE_REQUESTS_TABLE",
    "leave_requests"
)

LEAVE_BALANCES_TABLE = os.environ.get(
    "LEAVE_BALANCES_TABLE",
    "leave_balances"
)

LEAVE_CONFIG_TABLE = os.environ.get(
    "LEAVE_CONFIG_TABLE",
    "leave_config"
)

leave_requests_table = dynamodb.Table(LEAVE_REQUESTS_TABLE)
leave_balances_table = dynamodb.Table(LEAVE_BALANCES_TABLE)
leave_config_table = dynamodb.Table(LEAVE_CONFIG_TABLE)


# ============================================================
# RESPONSE HELPER
# ============================================================

def response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type",
            "Access-Control-Allow-Methods": "OPTIONS,POST"
        },
        "body": json.dumps(body)
    }

def create_approval_token(employee_id, request_id, action, expires_in=172800):
    payload = {
        "employee_id": employee_id,
        "request_id": request_id,
        "action": action,
        "exp": int(time.time()) + expires_in
    }

    payload_json = json.dumps(
        payload,
        separators=(",", ":")
    ).encode()

    payload_encoded = base64.urlsafe_b64encode(
        payload_json
    ).decode().rstrip("=")

    signature = hmac.new(
        APPROVAL_SECRET.encode(),
        payload_encoded.encode(),
        hashlib.sha256
    ).digest()

    signature_encoded = base64.urlsafe_b64encode(
        signature
    ).decode().rstrip("=")

    return f"{payload_encoded}.{signature_encoded}"

# ============================================================
# LAMBDA HANDLER
# ============================================================

def lambda_handler(event, context):

    try:

        # ----------------------------------------------------
        # 1. GET REQUEST BODY
        # ----------------------------------------------------

        body = event.get("body", event)

        if isinstance(body, str):
            try:
                body = json.loads(body)
            except json.JSONDecodeError:
                return response(
                    400,
                    {
                        "message": "Request body contains invalid JSON"
                    }
                )

        if not isinstance(body, dict):
            return response(
                400,
                {
                    "message": "Request body must be a JSON object"
                }
            )

        # ----------------------------------------------------
        # 2. REQUIRED FIELDS
        # ----------------------------------------------------

        required_fields = [
            "employee_id",
            "employee_name",
            "leave_type",
            "start_date",
            "end_date",
            "reason"
        ]

        missing_fields = [
            field
            for field in required_fields
            if not body.get(field)
        ]

        if missing_fields:
            return response(
                400,
                {
                    "message": "Missing required fields",
                    "missing_fields": missing_fields
                }
            )

        # ----------------------------------------------------
        # 3. GET VALUES
        # ----------------------------------------------------

        employee_id = str(body["employee_id"])
        employee_name = str(body["employee_name"])
        leave_type = str(body["leave_type"]).lower().strip()
        start_date = str(body["start_date"])
        end_date = str(body["end_date"])
        reason = str(body["reason"]).strip()

        manager_id = str(body.get("manager_id", ""))
        manager_email = str(body.get("manager_email", ""))

        # ----------------------------------------------------
        # 4. VALIDATE DATE FORMAT
        # ----------------------------------------------------

        try:
            start = date.fromisoformat(start_date)
            end = date.fromisoformat(end_date)

        except ValueError:
            return response(
                400,
                {
                    "message": "Invalid date format. Use YYYY-MM-DD."
                }
            )

        # ----------------------------------------------------
        # 5. VALIDATE DATE RANGE
        # ----------------------------------------------------

        if end < start:
            return response(
                400,
                {
                    "message": "End date cannot be before start date"
                }
            )

        # ----------------------------------------------------
        # 6. CALCULATE LEAVE DAYS
        # ----------------------------------------------------

        days = (end - start).days + 1

        if days <= 0:
            return response(
                400,
                {
                    "message": "Leave duration must be at least 1 day"
                }
            )

        # ----------------------------------------------------
        # 7. GET LEAVE CONFIGURATION
        # ----------------------------------------------------

        config_response = leave_config_table.get_item(
            Key={
                "leave_type": leave_type
            }
        )

        config = config_response.get("Item")

        if not config:
            return response(
                400,
                {
                    "message": "Invalid leave type",
                    "leave_type": leave_type
                }
            )

        # ----------------------------------------------------
        # 8. GET EMPLOYEE BALANCE
        # ----------------------------------------------------

        current_year = start.year

        balance_response = leave_balances_table.get_item(
            Key={
                "employee_id": employee_id,
                "leave_type_year": f"{leave_type}#{current_year}"
            }
        )

        balance = balance_response.get("Item")

        if not balance:
            return response(
                400,
                {
                    "message": "Leave balance record not found",
                    "employee_id": employee_id,
                    "leave_type": leave_type,
                    "year": current_year
                }
            )

        remaining = int(balance.get("remaining", 0))

        # ----------------------------------------------------
        # 9. CHECK SUFFICIENT BALANCE
        # ----------------------------------------------------

        if leave_type != "unpaid" and days > remaining:
            return response(
                400,
                {
                    "message": "Insufficient leave balance",
                    "requested_days": days,
                    "remaining_days": remaining,
                    "leave_type": leave_type
                }
            )

        # ----------------------------------------------------
        # 10. CHECK OVERLAPPING APPROVED LEAVES
        # ----------------------------------------------------

        existing_response = leave_requests_table.query(
            KeyConditionExpression=Key("employee_id").eq(employee_id)
        )

        existing_leaves = existing_response.get("Items", [])

        for existing in existing_leaves:

            if existing.get("status") != "APPROVED":
                continue

            existing_start = existing.get("start_date")
            existing_end = existing.get("end_date")

            if not existing_start or not existing_end:
                continue

            # Date overlap condition:
            # new start <= old end AND new end >= old start

            if start_date <= existing_end and end_date >= existing_start:
                return response(
                    400,
                    {
                        "message": "Leave dates overlap with an existing approved leave",
                        "existing_start_date": existing_start,
                        "existing_end_date": existing_end
                    }
                )

        # ----------------------------------------------------
        # 11. CREATE REQUEST ID
        # ----------------------------------------------------

        request_id = str(uuid.uuid4())

        created_at = datetime.utcnow().isoformat() + "Z"

        # ----------------------------------------------------
        # 12. DETERMINE APPROVAL STATUS
        # ----------------------------------------------------

        status = "PENDING_MANAGER"

        # ----------------------------------------------------
        # 13. SAVE LEAVE REQUEST
        # ----------------------------------------------------

        leave_item = {
            "employee_id": employee_id,
            "request_id": request_id,
            "employee_name": employee_name,
            "leave_type": leave_type,
            "start_date": start_date,
            "end_date": end_date,
            "days": days,
            "reason": reason,
            "manager_id": manager_id,
            "manager_email": manager_email,
            "status": status,
            "created_at": created_at
        }

        leave_requests_table.put_item(
            Item=leave_item
        )

        # Notify manager through SNS
        # Notify manager through SNS with signed approval links
        if SNS_TOPIC_ARN:

            approve_token = create_approval_token(employee_id, request_id, "approve")
            reject_token = create_approval_token(employee_id, request_id, "reject")

            approve_url = (
                f"{APPROVAL_BASE_URL}?token={quote(approve_token)}"
            )

            reject_url = (
                f"{APPROVAL_BASE_URL}?token={quote(reject_token)}"
            )

            sns.publish(
                TopicArn=SNS_TOPIC_ARN,
                Subject="New Leave Request - Approval Required",
                Message=(
                    f"New leave request submitted.\n\n"
                    f"Employee: {employee_name}\n"
                    f"Employee ID: {employee_id}\n"
                    f"Leave Type: {leave_type}\n"
                    f"Start Date: {start_date}\n"
                    f"End Date: {end_date}\n"
                    f"Days: {days}\n"
                    f"Reason: {reason}\n"
                    f"Request ID: {request_id}\n\n"
                    f"Status: PENDING_MANAGER\n\n"
                    f"APPROVE LEAVE:\n"
                    f"{approve_url}\n\n"
                    f"REJECT LEAVE:\n"
                    f"{reject_url}\n\n"
                    f"These approval links expire after 48 hours."
                )
        )

        # ----------------------------------------------------
        # IMPORTANT:
        # We DO NOT deduct balance here.
        #
        # Balance will be deducted only after final approval.
        # This prevents double counting.
        # ----------------------------------------------------

        return response(
            201,
            {
                "message": "Leave request submitted successfully",
                "request_id": request_id,
                "employee_id": employee_id,
                "leave_type": leave_type,
                "start_date": start_date,
                "end_date": end_date,
                "days": days,
                "status": status
            }
      )

        # ============================================================
    # ERROR HANDLING
    # ============================================================

    except Exception as error:

        print("ERROR:", str(error))

        return response(
            500,
            {
                "message": "Internal server error",
                "error": str(error)
            }
        )