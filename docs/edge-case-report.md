# Smart Leave & Absence Management Engine
## Edge-Case Report

### 1. Insufficient Leave Balance

#### Scenario
An employee attempts to apply for more leave days than the available balance for the selected leave type.

#### Expected Behavior
The application checks the employee's balance before creating the approval request.

#### System Behavior
The request is rejected and the reason is recorded rather than allowing the request to proceed through the approval workflow.

#### Purpose
This prevents employees from exceeding their configured annual leave allocation.

---

### 2. Overlapping Leave

#### Scenario
An employee submits a leave request whose dates overlap with an existing approved leave.

#### Expected Behavior
The application checks existing approved leave records for the employee before accepting the new request.

#### System Behavior
The conflicting request is prevented from proceeding as a valid new leave request.

#### Purpose
This prevents duplicate or overlapping approved absences.

---

### 3. Manager Inaction for More Than 48 Hours

#### Scenario
A leave request remains pending manager approval without a response for more than 48 hours.

#### Expected Behavior
The system automatically identifies requests that have exceeded the manager response window.

#### System Behavior
The manager-timeout Lambda marks the request as:

`MANAGER_TIMEOUT`

and records the timeout reason:

`Manager did not respond within 48 hours`

#### Automation
The manager-timeout Lambda is triggered by EventBridge on a scheduled basis.

#### Purpose
This prevents requests from remaining indefinitely in the manager approval queue.

---

### 4. Leave Requests Longer Than Five Days

#### Scenario
An employee requests more than five days of leave.

#### Expected Behavior
Manager approval is followed by an HR approval stage.

#### System Behavior
AWS Step Functions coordinates the additional approval workflow.

The workflow records the execution and allows HR to provide the final decision.

---

### 5. Rejected Requests

Rejected requests do not receive a final balance deduction.

The request status and rejection reason remain available through the leave history and management interfaces.

---

### Summary

The system handles the primary operational edge cases required for a leave-management workflow:

- Insufficient balance
- Date conflicts
- Manager inactivity beyond 48 hours
- Additional HR approval for long-duration leave
- Rejected requests without inappropriate balance deduction
