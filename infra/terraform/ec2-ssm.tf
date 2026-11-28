# Allow the existing EC2 instance role to communicate with Systems Manager.
# Permissions for GitHub to send deployment commands are configured separately.
resource "aws_iam_role_policy_attachment" "ec2_ssm_core" {
  role       = aws_iam_role.ec2_ecr_reader.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}
