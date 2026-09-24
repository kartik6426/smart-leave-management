# Smart Leave & Absence Management Engine
## Final Demonstration Checklist

### Employee Portal

- [x] Cognito login
- [x] Employee leave application form
- [x] Leave balance display
- [x] Leave history
- [x] Status badges
- [x] Leave submission through API Gateway

### Backend

- [x] DynamoDB leave request storage
- [x] DynamoDB employee balances
- [x] DynamoDB leave configuration
- [x] Balance validation
- [x] Leave conflict validation
- [x] Manager approval/rejection
- [x] Signed approval token
- [x] Balance deduction after final approval

### Approval Workflow

- [x] Manager notification
- [x] Manager approval
- [x] Manager rejection
- [x] Step Functions workflow for leaves longer than five days
- [x] HR approval
- [x] Final approval
- [x] Employee status notification through SES implementation

### Automation

- [x] Manager inactivity timeout
- [x] 48-hour timeout handling
- [x] EventBridge scheduled timeout processing
- [x] Weekly balance processing
- [x] Balance summary processing

### Management Portal

- [x] Manager pending approvals
- [x] HR pending approvals
- [x] Team absence calendar
- [x] Request filtering
- [x] Leave status visibility
- [x] Downloadable leave report

### Hosting and Authentication

- [x] S3 static website
- [x] Cognito User Pool
- [x] Cognito web application client
- [x] Secure frontend login
- [x] Public S3 deployment

### Evidence for Demonstration

The final demonstration should show:

1. Employee login
2. Employee balance
3. Employee submits leave
4. Request appears as pending
5. Manager approves
6. Step Functions execution for a leave longer than five days
7. HR approval where applicable
8. Final request status
9. Updated leave balance
10. SES notification
11. HR absence calendar
12. Downloadable leave report

### Repository Deliverables

The GitHub repository contains:

- Backend Lambda functions
- Frontend application
- DynamoDB schema documentation
- Step Functions state machine definition
- Execution input
- Balance logic walkthrough
- Edge-case report
- Final demonstration checklist
