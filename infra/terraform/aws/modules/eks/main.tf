variable "name_prefix" { type = string }
variable "vpc_id" { type = string }
variable "private_subnet_ids" { type = list(string) }
variable "tags" { type = map(string) }
variable "kubernetes_version" {
  type    = string
  default = "1.29"
}

resource "aws_iam_role" "cluster" {
  name = "${var.name_prefix}-eks-cluster-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "eks.amazonaws.com" }
    }]
  })
  tags = var.tags
}

resource "aws_iam_role_policy_attachment" "cluster_policy" {
  role       = aws_iam_role.cluster.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSClusterPolicy"
}

resource "aws_security_group" "cluster" {
  name_prefix = "${var.name_prefix}-eks-cluster-"
  vpc_id      = var.vpc_id
  tags        = merge(var.tags, { Name = "${var.name_prefix}-eks-cluster-sg" })
}

resource "aws_eks_cluster" "this" {
  name     = "${var.name_prefix}-cluster"
  role_arn = aws_iam_role.cluster.arn
  version  = var.kubernetes_version

  vpc_config {
    subnet_ids              = var.private_subnet_ids
    security_group_ids      = [aws_security_group.cluster.id]
    endpoint_private_access  = true
    endpoint_public_access   = true # restrict to your office/VPN CIDR via public_access_cidrs in real use
  }

  encryption_config {
    resources = ["secrets"]
    provider {
      key_arn = aws_kms_key.eks.arn
    }
  }

  depends_on = [aws_iam_role_policy_attachment.cluster_policy]
  tags       = var.tags
}

# Encrypts k8s Secret objects at the etcd layer — defense in depth even
# though secrets should be coming from External Secrets Operator
# (k8s/28-external-secrets.yml), not stored raw in k8s Secrets long-term.
resource "aws_kms_key" "eks" {
  description             = "${var.name_prefix} EKS secrets encryption"
  deletion_window_in_days = 30
  enable_key_rotation      = true
  tags                     = var.tags
}

resource "aws_iam_role" "node" {
  name = "${var.name_prefix}-eks-node-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
    }]
  })
  tags = var.tags
}

resource "aws_iam_role_policy_attachment" "node_policies" {
  for_each = toset([
    "arn:aws:iam::aws:policy/AmazonEKSWorkerNodePolicy",
    "arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy",
    "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly",
  ])
  role       = aws_iam_role.node.name
  policy_arn = each.value
}

# General-purpose on-demand node group — api pods, pgbouncer, anything
# that shouldn't get interrupted mid-request.
resource "aws_eks_node_group" "general" {
  cluster_name    = aws_eks_cluster.this.name
  node_group_name = "${var.name_prefix}-general"
  node_role_arn   = aws_iam_role.node.arn
  subnet_ids      = var.private_subnet_ids

  scaling_config {
    desired_size = 3
    min_size     = 3
    max_size     = 20 # cluster autoscaler / Karpenter can push past this baseline under real load
  }

  instance_types = ["m6i.large"]
  capacity_type  = "ON_DEMAND"

  depends_on = [aws_iam_role_policy_attachment.node_policies]
  tags       = var.tags
}

# Spot node group — Celery workers. Workflow execution is already built
# to retry/DLQ on failure (core/execution_engine.py), which is exactly
# the workload profile spot interruption tolerance is good for; running
# workers on spot meaningfully cuts the compute bill at 1M-user scale.
resource "aws_eks_node_group" "workers_spot" {
  cluster_name    = aws_eks_cluster.this.name
  node_group_name = "${var.name_prefix}-workers-spot"
  node_role_arn   = aws_iam_role.node.arn
  subnet_ids      = var.private_subnet_ids

  scaling_config {
    desired_size = 2
    min_size     = 2
    max_size      = 50
  }

  instance_types = ["m6i.large", "m6a.large", "m5.large"] # multiple types = better spot availability
  capacity_type  = "SPOT"

  depends_on = [aws_iam_role_policy_attachment.node_policies]
  tags       = var.tags
}

resource "aws_security_group" "node" {
  name_prefix = "${var.name_prefix}-eks-node-"
  vpc_id      = var.vpc_id
  tags        = merge(var.tags, { Name = "${var.name_prefix}-eks-node-sg" })
}

output "cluster_endpoint" { value = aws_eks_cluster.this.endpoint }
output "cluster_name" { value = aws_eks_cluster.this.name }
output "node_security_group_id" { value = aws_security_group.node.id }
