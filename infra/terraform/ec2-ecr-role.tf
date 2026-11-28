# EC2 may assume this role through an attached instance profile.
resource "aws_iam_role" "ec2_ecr_reader" {
  name = "mini-uptime-monitor-ec2-ecr-reader"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = "ec2.amazonaws.com"
      }
      Action = "sts:AssumeRole"
    }]
  })

  tags = {
    Project = "mini-uptime-monitor"
  }
}

resource "aws_iam_role_policy" "ec2_ecr_pull" {
  name = "pull-project-images"
  role = aws_iam_role.ec2_ecr_reader.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "AuthenticateToECR"
        Effect   = "Allow"
        Action   = "ecr:GetAuthorizationToken"
        Resource = "*"
      },
      {
        Sid    = "PullOnlyProjectImages"
        Effect = "Allow"
        Action = [
          "ecr:BatchCheckLayerAvailability",
          "ecr:BatchGetImage",
          "ecr:GetDownloadUrlForLayer",
        ]
        Resource = aws_ecr_repository.app.arn
      },
    ]
  })
}

# Creating the profile does not attach it to the existing EC2 instance.
resource "aws_iam_instance_profile" "app" {
  name = "mini-uptime-monitor-ec2"
  role = aws_iam_role.ec2_ecr_reader.name

  tags = {
    Project = "mini-uptime-monitor"
  }
}

output "ec2_instance_profile_name" {
  description = "Instance profile to attach to the existing project EC2 server."
  value       = aws_iam_instance_profile.app.name
}
