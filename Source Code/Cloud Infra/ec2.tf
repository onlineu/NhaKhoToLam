data "aws_ami" "al2023" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-2023.*-x86_64"]
  }

  filter {
    name   = "architecture"
    values = ["x86_64"]
  }
}

resource "aws_instance" "web" {
  ami                    = data.aws_ami.al2023.id
  instance_type          = var.instance_type
  subnet_id              = aws_subnet.sub_ec.id
  vpc_security_group_ids = [aws_security_group.ez_ec_ui.id]
  iam_instance_profile   = aws_iam_instance_profile.ec2_profile.name

  metadata_options {
    http_endpoint = "enabled"
    http_tokens   = "required" # IMDSv2 only
  }

  root_block_device {
    volume_type = "gp3"
    volume_size = 8
    encrypted   = true
  }

  user_data_replace_on_change = true
  user_data                   = <<EOT
#!/bin/bash
dnf install -y python3-pip
pip3 install flask gunicorn boto3 requests "pyjwt[crypto]"

mkdir -p /opt/vindelivery/www
echo "VinDelivery infrastructure is up" > /opt/vindelivery/www/index.html

cat > /etc/vindelivery.env <<ENV
AWS_REGION=${var.aws_region}
LAMBDA_FUNCTION_NAME=${aws_lambda_function.lambda_func.function_name}
COGNITO_USER_POOL_ID=${aws_cognito_user_pool.staff.id}
COGNITO_CLIENT_ID=${aws_cognito_user_pool_client.app.id}
ENV

# Placeholder web server on port 80, replaced by the real app later
cat > /etc/systemd/system/vindelivery.service <<UNIT
[Unit]
Description=VinDelivery web
After=network.target

[Service]
EnvironmentFile=/etc/vindelivery.env
ExecStart=/usr/bin/python3 -m http.server 80 --directory /opt/vindelivery/www
Restart=always

[Install]
WantedBy=multi-user.target
UNIT

systemctl daemon-reload
systemctl enable --now vindelivery
EOT

  tags = {
    Name = "VinDelivery Web UI"
  }
}

resource "aws_eip" "web_eip" {
  domain     = "vpc"
  instance   = aws_instance.web.id
  depends_on = [aws_internet_gateway.igw]

  tags = {
    Name = "web_eip"
  }
}