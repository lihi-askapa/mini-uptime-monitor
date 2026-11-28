# Register GitHub's identity issuer. This alone grants no repository access.
# A separate, restricted IAM role and policy will be added in the next step.
resource "aws_iam_openid_connect_provider" "github" {
  url            = "https://token.actions.githubusercontent.com"
  client_id_list = ["sts.amazonaws.com"]

  tags = {
    Project = "mini-uptime-monitor"
  }
}
