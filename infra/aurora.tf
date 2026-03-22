resource "aws_db_subnet_group" "aurora" {
  name       = "${local.name_prefix}-aurora"
  subnet_ids = [aws_subnet.private_a.id, aws_subnet.private_c.id]

  tags = { Name = "${local.name_prefix}-aurora-subnet-group" }
}

resource "aws_rds_cluster" "main" {
  cluster_identifier = "${local.name_prefix}-cluster"
  engine             = "aurora-postgresql"
  engine_mode        = "provisioned"
  engine_version     = "16.4"

  database_name   = var.db_name
  master_username = var.db_username
  master_password = var.db_password

  db_subnet_group_name   = aws_db_subnet_group.aurora.name
  vpc_security_group_ids = [aws_security_group.aurora.id]

  skip_final_snapshot = true

  serverlessv2_scaling_configuration {
    min_capacity = 0.5
    max_capacity = 2.0
  }

  tags = { Name = "${local.name_prefix}-cluster" }
}

resource "aws_rds_cluster_instance" "main" {
  identifier         = "${local.name_prefix}-instance-1"
  cluster_identifier = aws_rds_cluster.main.id
  instance_class     = "db.serverless"
  engine             = aws_rds_cluster.main.engine
  engine_version     = aws_rds_cluster.main.engine_version

  tags = { Name = "${local.name_prefix}-instance-1" }
}
