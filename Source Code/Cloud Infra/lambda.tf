locals {
  lambda_name = "vindelivery-backend"
}

# Zips the Python code in App/Algo at plan time, so no zip file is committed
data "archive_file" "lambda_zip" {
  type        = "zip"
  source_dir  = "${path.module}/../App/Algo"
  output_path = "${path.module}/build/lambda_function.zip"
  excludes    = ["__pycache__", "tests", ".venv", "venv", "README.md", "benchmark.py"]
}

resource "aws_cloudwatch_log_group" "lambda" {
  name              = "/aws/lambda/${local.lambda_name}"
  retention_in_days = 14
}

resource "aws_lambda_function" "lambda_func" {
  function_name    = local.lambda_name
  filename         = data.archive_file.lambda_zip.output_path
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256
  role             = aws_iam_role.lambda_role.arn
  handler          = "lambda_function.lambda_handler"
  runtime          = "python3.13"
  timeout          = 10
  memory_size      = 256

  vpc_config {
    subnet_ids         = [aws_subnet.sub_lbd.id]
    security_group_ids = [aws_security_group.lambda_sg.id]
  }

  environment {
    variables = {
      ITEMS_TABLE     = aws_dynamodb_table.items.name
      COUNTERS_TABLE  = aws_dynamodb_table.counters.name
      WHITELIST_TABLE = aws_dynamodb_table.whitelist.name
      STAFF_TABLE     = aws_dynamodb_table.staff_profiles.name
    }
  }

  depends_on = [
    aws_iam_role_policy_attachment.lambda_vpc,
    aws_iam_role_policy.lambda_dynamodb,
    aws_cloudwatch_log_group.lambda,
  ]
}