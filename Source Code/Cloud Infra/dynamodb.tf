# Items: numeric ID, searchable by name through the GSI
resource "aws_dynamodb_table" "items" {
  name         = "vindelivery-items"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "item_id"

  attribute {
    name = "item_id"
    type = "N"
  }

  attribute {
    name = "name"
    type = "S"
  }

  global_secondary_index {
    name            = "name-index"
    hash_key        = "name"
    projection_type = "ALL"
  }

  point_in_time_recovery {
    enabled = true
  }
}

# Counter for auto-assigned IDs (atomic ADD creates it on first use)
resource "aws_dynamodb_table" "counters" {
  name         = "vindelivery-counters"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "counter_name"

  attribute {
    name = "counter_name"
    type = "S"
  }
}

# Approved devices. One special row, device_id = "LOCKDOWN", holds the lockdown flag.
resource "aws_dynamodb_table" "whitelist" {
  name         = "vindelivery-device-whitelist"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "device_id"

  attribute {
    name = "device_id"
    type = "S"
  }
}

# Seed the lockdown flag as off. Terraform won't overwrite it once the app changes it.
resource "aws_dynamodb_table_item" "lockdown_flag" {
  table_name = aws_dynamodb_table.whitelist.name
  hash_key   = aws_dynamodb_table.whitelist.hash_key

  item = jsonencode({
    device_id = { S = "LOCKDOWN" }
    active    = { BOOL = false }
  })

  lifecycle {
    ignore_changes = [item]
  }
}

# Staff roles (e.g. Manager). Logins themselves live in Cognito, not here.
resource "aws_dynamodb_table" "staff_profiles" {
  name         = "vindelivery-staff-profiles"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "staff_id"

  attribute {
    name = "staff_id"
    type = "S"
  }
}