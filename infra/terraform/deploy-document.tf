resource "aws_ssm_document" "deploy" {
  name            = "mini-uptime-monitor-deploy"
  document_type   = "Command"
  document_format = "JSON"

  content = jsonencode({
    schemaVersion = "2.2"
    description   = "Deploy a commit-tagged Pulse ECR image and verify web and scheduler health."
    parameters = {
      ImageTag = {
        type              = "String"
        description       = "Full commit SHA of an image already published by CI."
        allowedPattern    = "^[0-9a-f]{40}$"
        interpolationType = "ENV_VAR"
      }
    }
    mainSteps = [{
      action       = "aws:runShellScript"
      name         = "deployPulse"
      precondition = { StringEquals = ["platformType", "Linux"] }
      inputs = {
        timeoutSeconds = "900"
        runCommand = [
          "/bin/bash <<'PULSE_DEPLOY_SCRIPT'",
          file("${path.module}/scripts/deploy.sh"),
          "PULSE_DEPLOY_SCRIPT",
        ]
      }
    }]
  })

  tags = {
    Project = "mini-uptime-monitor"
  }
}

output "deployment_document_name" {
  description = "Bounded SSM document invoked by the deployment workflow."
  value       = aws_ssm_document.deploy.name
}
