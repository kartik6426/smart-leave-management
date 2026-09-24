import os
import boto3
from decimal import Decimal
from collections import defaultdict

dynamodb = boto3.resource("dynamodb")
ses = boto3.client("ses")

LEAVE_BALANCES_TABLE = os.environ.get("LEAVE_BALANCES_TABLE", "leave_balances_dev")
SES_EMAIL = os.environ.get("SES_EMAIL", "")

balances_table = dynamodb.Table(LEAVE_BALANCES_TABLE)


def send_summary_email(employee_id, balances):
    if not SES_EMAIL:
        return

    lines = [
        f"Weekly Leave Balance Summary for {employee_id}",
        "",
        "Leave Type | Allocated | Used | Remaining | Carry Forward",
        "-" * 65,
    ]

    for balance in balances:
        leave_type_year = balance.get("leave_type_year", "")
        leave_type = leave_type_year.split("#")[0]

        allocated = Decimal(str(balance.get("allocated", 0)))
        used = Decimal(str(balance.get("used", 0)))
        remaining = Decimal(str(balance.get("remaining", 0)))
        carry_forward = Decimal(str(balance.get("carry_forward", 0)))

        lines.append(
            f"{leave_type} | {allocated} | {used} | "
            f"{remaining} | {carry_forward}"
        )

    body = "\n".join(lines)

    ses.send_email(
        Source=SES_EMAIL,
        Destination={
            "ToAddresses": [SES_EMAIL]
        },
        Message={
            "Subject": {
                "Data": f"Weekly Leave Balance Summary - {employee_id}"
            },
            "Body": {
                "Text": {
                    "Data": body
                }
            },
        },
    )


def lambda_handler(event, context):
    response = balances_table.scan()
    items = response.get("Items", [])

    # Handle DynamoDB pagination
    while "LastEvaluatedKey" in response:
        response = balances_table.scan(
            ExclusiveStartKey=response["LastEvaluatedKey"]
        )
        items.extend(response.get("Items", []))

    employees = defaultdict(list)
    updated_count = 0

    for item in items:
        employee_id = item.get("employee_id")
        if not employee_id:
            continue

        carry_forward = Decimal(str(item.get("carry_forward", 0)))
        allocated = Decimal(str(item.get("allocated", 0)))
        used = Decimal(str(item.get("used", 0)))

        # Re-credit any available carry-forward amount.
        if carry_forward > 0:
            allocated += carry_forward
            carry_forward = Decimal("0")

            remaining = max(allocated - used, Decimal("0"))

            balances_table.update_item(
                Key={
                    "employee_id": employee_id,
                    "leave_type_year": item["leave_type_year"],
                },
                UpdateExpression="""
                    SET allocated = :allocated,
                        remaining = :remaining,
                        carry_forward = :carry_forward
                """,
                ExpressionAttributeValues={
                    ":allocated": allocated,
                    ":remaining": remaining,
                    ":carry_forward": carry_forward,
                },
            )

            item["allocated"] = allocated
            item["remaining"] = remaining
            item["carry_forward"] = carry_forward

            updated_count += 1

        employees[employee_id].append(item)

    # Send one summary for each employee.
    email_count = 0

    for employee_id, employee_balances in employees.items():
        try:
            send_summary_email(employee_id, employee_balances)
            email_count += 1
        except Exception as exc:
            print(
                f"Failed to send balance summary for "
                f"{employee_id}: {str(exc)}"
            )

    return {
        "statusCode": 200,
        "message": "Weekly balance processing completed",
        "employees_processed": len(employees),
        "balances_updated": updated_count,
        "summary_emails_attempted": email_count,
    }