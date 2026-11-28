terraform {
  backend "s3" {
    bucket              = "pulse-944464821297-tfstate-eu-north-1"
    key                 = "pulse/terraform.tfstate"
    region              = "eu-north-1"
    encrypt             = true
    use_lockfile        = true
    allowed_account_ids = ["944464821297"]
  }
}
