# Smart Leave & Absence Management Engine
## Balance and Quota Logic Walkthrough

### 1. Leave Configuration

Leave types and their annual quotas are maintained in the `leave_config_dev` DynamoDB table.

The application supports configurable leave categories such as:

- Sick Leave
- Casual Leave
- Earned Leave
- Unpaid Leave

The application reads the configured values instead of relying on fixed quota values in the frontend.

### 2. Employee Balance

Employee balances are maintained in the `leave_balances_dev` DynamoDB table.

Each balance record is associated with:

- Employee ID
- Leave type
- Leave year
- Allocated balance
- Used balance
- Remaining balance
- Carry-forward information where applicable

### 3. Leave Submission

When an employee submits a leave request:

1. The employee selects the leave type and dates.
2. The application calculates the requested number of days.
3. The configured leave balance is retrieved.
4. The available balance is checked.
5. Existing approved leave records are checked for date conflicts.
6. If the request passes validation, a leave request is stored in `leave_requests_dev`.
7. The request initially receives the `PENDING_MANAGER` status.
8. The manager receives an approval notification.

### 4. Insufficient Balance

If the employee does not have sufficient available balance for the selected leave type, the request is rejected instead of creating an approval request.

The rejection reason is recorded so that the employee/management interface can identify why the request was not accepted.

### 5. Balance Deduction

Balance is not deducted when the employee submits the request.

The balance is deducted only after the request reaches its final approval stage.

This prevents pending or rejected requests from incorrectly reducing the employee's available leave.

### 6. Approval Workflow

For normal leave requests:

Employee Submission
→ Manager Approval
→ Final Approval
→ Balance Deduction

For leave requests longer than five days:

Employee Submission
→ Manager Approval
→ Step Functions Workflow
→ HR Approval
→ Final Approval
→ Balance Deduction

### 7. Weekly Balance Processing

The weekly balance Lambda processes employee balance records and sends balance summary notifications through SES.

The EventBridge schedule invokes this process automatically.

### 8. Key Design Principle

The central balance rule is:

`Available Balance = Allocated Balance - Used Balance + Applicable Carry Forward`

The application updates the used/remaining balance only after final approval.
