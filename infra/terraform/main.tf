terraform {
  # Terraform 1.10+ is required for native S3 state lockfiles.
  required_version = ">= 1.10, < 2.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
}

provider "aws" {
  region = "eu-north-1"

  # Restrict this personal learning project to Lihi's personal AWS account.
  allowed_account_ids = ["944464821297"]
}
