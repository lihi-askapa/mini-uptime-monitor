# GitHub uses immutable owner/repository IDs for this repository's OIDC subject.
# Verified using the repository's OIDC customization API before configuration.
resource "aws_iam_role" "github_ecr_publisher" {
  name = "mini-uptime-monitor-github-ecr-publisher"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Federated = aws_iam_openid_connect_provider.github.arn
      }
      Action = "sts:AssumeRoleWithWebIdentity"
      Condition = {
        StringEquals = {
          "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com"
          "token.actions.githubusercontent.com:sub" = "repo:lihi-askapa@223032576/mini-uptime-monitor@1470667743:ref:refs/heads/main"
        }
      }
    }]
  })

  tags = {
    Project = "mini-uptime-monitor"
  }
}

resource "aws_iam_role_policy" "github_ecr_publish" {
  name = "publish-project-images"
  role = aws_iam_role.github_ecr_publisher.id

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
        Sid    = "PublishOnlyProjectImages"
        Effect = "Allow"
        Action = [
          "ecr:BatchCheckLayerAvailability",
          "ecr:InitiateLayerUpload",
          "ecr:UploadLayerPart",
          "ecr:CompleteLayerUpload",
          "ecr:PutImage",
          "ecr:BatchGetImage",
          "ecr:GetDownloadUrlForLayer",
          "ecr:DescribeImages",
        ]
        Resource = aws_ecr_repository.app.arn
      },
    ]
  })
}

output "github_ecr_publisher_role_arn" {
  description = "Role for the main branch workflow to publish this project's images."
  value       = aws_iam_role.github_ecr_publisher.arn
}
