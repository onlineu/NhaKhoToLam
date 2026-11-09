resource "aws_security_group" "ez_ec_ui" {
  name        = "ec2-web-ui"
  description = "Web UI: HTTP in, SSH from admin IP only"
  vpc_id      = aws_vpc.main_vpc.id

  ingress {
    description = "HTTP"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "SSH from admin IP only"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.admin_cidr]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "EC2 Web UI SG"
  }
}

resource "aws_security_group" "lambda_sg" {
  name        = "lambda-sg"
  description = "Lambda: outbound HTTPS to DynamoDB endpoint only"
  vpc_id      = aws_vpc.main_vpc.id

  egress {
    description     = "HTTPS to DynamoDB via gateway endpoint"
    from_port       = 443
    to_port         = 443
    protocol        = "tcp"
    prefix_list_ids = [aws_vpc_endpoint.dynamodb.prefix_list_id]
  }

  tags = {
    Name = "Lambda SG"
  }
}