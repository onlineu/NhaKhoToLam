output "web_url" {
  value = "http://${aws_eip.web_eip.public_ip}"
}

output "ec2_public_ip" {
  value = aws_eip.web_eip.public_ip
}

output "lambda_function_name" {
  value = aws_lambda_function.lambda_func.function_name
}

output "cognito_user_pool_id" {
  value = aws_cognito_user_pool.staff.id
}

output "cognito_client_id" {
  value = aws_cognito_user_pool_client.app.id
}

output "dynamodb_tables" {
  value = {
    items     = aws_dynamodb_table.items.name
    counters  = aws_dynamodb_table.counters.name
    whitelist = aws_dynamodb_table.whitelist.name
    staff     = aws_dynamodb_table.staff_profiles.name
  }
}