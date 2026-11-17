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
dnf install -y git python3-pip
pip3 install flask gunicorn boto3 "pyjwt[crypto]"

git clone ${var.repo_url} /opt/vindelivery/src
ln -s "/opt/vindelivery/src/Source Code/App/UI-UX" /opt/vindelivery/ui

cat > /etc/vindelivery.env <<ENV
AWS_REGION=${var.aws_region}
LAMBDA_FUNCTION_NAME=${aws_lambda_function.lambda_func.function_name}
COGNITO_USER_POOL_ID=${aws_cognito_user_pool.staff.id}
COGNITO_CLIENT_ID=${aws_cognito_user_pool_client.app.id}
ENV

cat > /etc/systemd/system/vindelivery.service <<UNIT
[Unit]
Description=VinDelivery web
After=network-online.target

[Service]
User=ec2-user
EnvironmentFile=/etc/vindelivery.env
WorkingDirectory=/opt/vindelivery/ui
ExecStart=/usr/bin/python3 -m gunicorn --workers 2 --bind 0.0.0.0:80 server:app
AmbientCapabilities=CAP_NET_BIND_SERVICE
NoNewPrivileges=true
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