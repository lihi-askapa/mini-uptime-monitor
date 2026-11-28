# The deployment role is separate from the ECR publishing role.
resource "aws_iam_role" "github_deployer" {
  name = "mini-uptime-monitor-github-deployer"

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

resource "aws_iam_role_policy" "github_deploy" {
  name = "deploy-only-project-instance"
  role = aws_iam_role.github_deployer.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "RunOnlyProjectDeployment"
        Effect = "Allow"
        Action = "ssm:SendCommand"
        Resource = [
          "arn:aws:ec2:eu-north-1:944464821297:instance/i-07451294bf374f84c",
          # Reserved for the bounded deployment document, created in the next step.
          # This does not authorize AWS-RunShellScript or arbitrary documents.
          "arn:aws:ssm:eu-north-1:944464821297:document/mini-uptime-monitor-deploy",
        ]
      },
      {
        Sid    = "ReadCommandResult"
        Effect = "Allow"
        Action = "ssm:GetCommandInvocation"
        # AWS does not support resource-level scoping for this read action.
        Resource = "*"
      },
    ]
  })
}

output "github_deployer_role_arn" {
  description = "Role for the main branch workflow to request the bounded EC2 deployment."
  value       = aws_iam_role.github_deployer.arn
}
