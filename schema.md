# DynamoDB Database Schema

## 1. Leave Config Table

### Table Name
`leave-config-dev`

### Primary Key
- Partition Key: `leave_type` (String)

### Purpose
Stores configurable rules for each leave type.

### Example Record

```json
{
  "leave_type": "sick",
  "annual_quota": 12,
  "carry_forward": true,
  "max_carry_forward": 5,
  "requires_hr_approval": false
}