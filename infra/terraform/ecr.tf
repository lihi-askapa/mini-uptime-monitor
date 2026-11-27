# A private registry repository for versioned application images.
resource "aws_ecr_repository" "app" {
  name                 = "mini-uptime-monitor"
  image_tag_mutability = "IMMUTABLE"
  force_delete         = false

  tags = {
    Project = "mini-uptime-monitor"
  }

  lifecycle {
    prevent_destroy = true
  }
}

output "ecr_repository_url" {
  description = "Repository address used to push and pull application images."
  value       = aws_ecr_repository.app.repository_url
}
