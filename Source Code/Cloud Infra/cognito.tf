resource "aws_cognito_user_pool" "staff" {
  name = "vindelivery-staff"

  # Only admins create staff accounts; no self sign-up
  admin_create_user_config {
    allow_admin_create_user_only = true
  }

  password_policy {
    minimum_length    = 12
    require_lowercase = true
    require_uppercase = true
    require_numbers   = true
    require_symbols   = true
  }
}

resource "aws_cognito_user_pool_client" "app" {
  name            = "vindelivery-web"
  user_pool_id    = aws_cognito_user_pool.staff.id
  generate_secret = false

  explicit_auth_flows = [
    "ALLOW_USER_PASSWORD_AUTH",
    "ALLOW_REFRESH_TOKEN_AUTH",
  ]

  prevent_user_existence_errors = "ENABLED"
}

resource "aws_cognito_user_group" "admin" {
  name         = "admin"
  user_pool_id = aws_cognito_user_pool.staff.id
  description  = "Managers: whitelist devices, clear lockdown, delete items"
}

resource "aws_cognito_user_group" "staff" {
  name         = "staff"
  user_pool_id = aws_cognito_user_pool.staff.id
  description  = "Warehouse staff: store and find items"
}