Feature: CIS AWS Foundations Benchmark Level 1
  As a security engineer
  I want to verify that AWS resources meet CIS Level 1 controls
  So that our infrastructure baseline is hardened before deployment

  # ---------------------------------------------------------------------------
  # CIS 2.2  Ensure CloudTrail log file validation is enabled
  # ---------------------------------------------------------------------------
  Scenario: CloudTrail must have log file integrity validation
    Given I have aws_cloudtrail resource configured
    Then it must have log_file_validation_enabled set to true

  # ---------------------------------------------------------------------------
  # CIS 2.3  Ensure the S3 bucket used to store CloudTrail logs is not
  #          publicly accessible
  # ---------------------------------------------------------------------------
  Scenario: S3 bucket must not be publicly accessible
    Given I have aws_s3_bucket resource configured
    Then it must not have public access enabled

  # ---------------------------------------------------------------------------
  # CIS 2.4  Ensure CloudTrail trails are integrated with CloudWatch Logs
  #          (tag-based governance)
  # ---------------------------------------------------------------------------
  Scenario: CloudTrail resources must carry mandatory governance tags
    Given I have aws_cloudtrail resource configured
    Then it must have tags including Environment
    And it must have tags including Owner

  # ---------------------------------------------------------------------------
  # CIS 2.6  Ensure S3 bucket access logging is enabled on the CloudTrail
  #          S3 bucket — checked via mandatory tag
  # ---------------------------------------------------------------------------
  Scenario: S3 buckets must carry mandatory governance tags
    Given I have aws_s3_bucket resource configured
    Then it must have tags including Environment
    And it must have tags including Owner

  # ---------------------------------------------------------------------------
  # CIS 2.7  Ensure CloudTrail logs are encrypted at rest using KMS
  # ---------------------------------------------------------------------------
  Scenario: S3 buckets used for CloudTrail must have encryption at rest
    Given I have aws_s3_bucket resource configured
    Then it must have encryption_at_rest set to true

  # ---------------------------------------------------------------------------
  # CIS 2.8  Ensure rotation for customer-created CMKs is enabled
  #          (deletion-protection proxy for RDS)
  # CIS 2.3.3 Ensure that Amazon RDS Instances have deletion protection enabled
  # ---------------------------------------------------------------------------
  Scenario: RDS instances must have deletion protection enabled
    Given I have aws_db_instance resource configured
    Then it must have deletion_protection set to true

  # ---------------------------------------------------------------------------
  # CIS 2.3.2  Ensure that public access is not given to RDS Instance
  # ---------------------------------------------------------------------------
  Scenario: RDS instances must not be publicly accessible
    Given I have aws_db_instance resource configured
    Then it must not have public access enabled

  # ---------------------------------------------------------------------------
  # CIS 2.3.1  Ensure that encryption is enabled for all RDS DB Instances
  # ---------------------------------------------------------------------------
  Scenario: RDS instances must have encryption at rest
    Given I have aws_db_instance resource configured
    Then it must have encryption_at_rest set to true

  # ---------------------------------------------------------------------------
  # CIS 2.3.x  Generic attribute enabled check (multi_az for RDS)
  # ---------------------------------------------------------------------------
  Scenario: RDS instances must run in multi-AZ mode
    Given I have aws_db_instance resource configured
    Then it must have multi_az enabled
