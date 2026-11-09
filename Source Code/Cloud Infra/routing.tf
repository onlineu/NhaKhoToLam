# Public route table: default route to the internet gateway
resource "aws_route_table" "vert" {
  vpc_id = aws_vpc.main_vpc.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.igw.id
  }

  tags = {
    Name = "Public Route Table"
  }
}

resource "aws_route_table_association" "vert_assoc" {
  subnet_id      = aws_subnet.sub_ec.id
  route_table_id = aws_route_table.vert.id
}

# Private route table: no internet route, only the DynamoDB endpoint
resource "aws_route_table" "private_rt" {
  vpc_id = aws_vpc.main_vpc.id

  tags = {
    Name = "Private Route Table"
  }
}

resource "aws_route_table_association" "private_assoc" {
  subnet_id      = aws_subnet.sub_lbd.id
  route_table_id = aws_route_table.private_rt.id
}

# Gateway endpoint: Lambda reaches DynamoDB without leaving the AWS network
resource "aws_vpc_endpoint" "dynamodb" {
  vpc_id            = aws_vpc.main_vpc.id
  service_name      = "com.amazonaws.${var.aws_region}.dynamodb"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = [aws_route_table.private_rt.id]

  tags = {
    Name = "DynamoDB Endpoint"
  }
}