# -*- coding: utf-8 -*-
"""
CIS Benchmark step definitions for terraform-compliance.

Provides reusable Given/When/Then phrases that map to common CIS AWS Foundations
Benchmark Level 1 controls.  Each step iterates over the resources already placed
into the radish step context stash by a preceding Given/When step and calls the
shared Error() helper on the first violation it finds.
"""

from radish import then
from terraform_compliance.common.error_handling import Error


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _values(resource):
    """Return the ``values`` dict for a stash entry, falling back to ``{}``."""
    if isinstance(resource, dict):
        return resource.get('values') or {}
    return {}


def _address(resource):
    """Return a human-readable address string for a stash entry."""
    if isinstance(resource, dict):
        return resource.get('address', str(resource))
    return str(resource)


# ---------------------------------------------------------------------------
# CIS step definitions
# ---------------------------------------------------------------------------

@then(u'it must have {attribute:ANY} enabled')
def cis_attribute_enabled(_step_obj, attribute):
    """CIS generic control: assert that *attribute* is a truthy boolean value.

    Typical usage::

        Then it must have storage_encrypted enabled
        Then it must have multi_az enabled
    """
    for resource in _step_obj.context.stash:
        vals = _values(resource)
        addr = _address(resource)
        value = vals.get(attribute)
        if not value:
            Error(
                _step_obj,
                'Resource {} does not have {} enabled ({}={}).'.format(
                    addr, attribute, attribute, value),
            )


@then(u'it must not have public access enabled')
def cis_no_public_access(_step_obj):
    """CIS 2.x / S3.x: verify that the resource exposes no public-access path.

    Checks three common public-access vectors across AWS resource types:

    * ``publicly_accessible`` must be falsy (RDS, ElastiCache, …).
    * ``acl`` must not be ``public-read`` or ``public-read-write`` (S3 bucket).
    * ``public_access_block`` / ``public_access_block_configuration`` must have
      all four block flags set to ``true`` (S3 bucket public-access block).
    """
    _PUBLIC_ACLS = {'public-read', 'public-read-write'}
    _BLOCK_FLAGS = (
        'block_public_acls',
        'ignore_public_acls',
        'block_public_policy',
        'restrict_public_buckets',
    )

    for resource in _step_obj.context.stash:
        vals = _values(resource)
        addr = _address(resource)

        # publicly_accessible attribute (RDS, ElastiCache, etc.)
        if 'publicly_accessible' in vals:
            if vals['publicly_accessible'] not in (False, None, ''):
                Error(
                    _step_obj,
                    'Resource {} has publicly_accessible set to {}.'.format(
                        addr, vals['publicly_accessible']),
                )

        # S3 bucket ACL
        if 'acl' in vals:
            if vals['acl'] in _PUBLIC_ACLS:
                Error(
                    _step_obj,
                    'Resource {} has a public ACL set to "{}".'.format(
                        addr, vals['acl']),
                )

        # S3 public-access block (both attribute name variants)
        block = (
            vals.get('public_access_block_configuration')
            or vals.get('public_access_block')
            or {}
        )
        if isinstance(block, list) and block:
            block = block[0]
        if isinstance(block, dict):
            for flag in _BLOCK_FLAGS:
                if not block.get(flag, True):
                    Error(
                        _step_obj,
                        'Resource {} has {} disabled in public_access_block.'.format(
                            addr, flag),
                    )


@then(u'it must have encryption_at_rest set to true')
def cis_encryption_at_rest(_step_obj):
    """CIS 2.x: assert that at-rest encryption is enabled on the resource.

    Recognises the following attribute names used by common AWS providers:

    * ``storage_encrypted`` (aws_db_instance, aws_rds_cluster)
    * ``at_rest_encryption_enabled`` (aws_elasticache_replication_group)
    * ``encrypted`` (aws_ebs_volume, ebs_block_device)
    * ``enable_blob_encryption`` (azurerm_storage_account)
    * ``server_side_encryption_configuration`` block (aws_s3_bucket)
    """
    _BOOL_ATTRS = (
        'storage_encrypted',
        'at_rest_encryption_enabled',
        'encrypted',
        'enable_blob_encryption',
    )

    for resource in _step_obj.context.stash:
        vals = _values(resource)
        addr = _address(resource)

        # S3-style SSE configuration block
        if 'server_side_encryption_configuration' in vals:
            sse = vals['server_side_encryption_configuration']
            if not sse:
                Error(
                    _step_obj,
                    'Resource {} does not have server_side_encryption_configuration'
                    ' set.'.format(addr),
                )
            continue

        found = False
        for attr in _BOOL_ATTRS:
            if attr in vals:
                found = True
                if not vals[attr]:
                    Error(
                        _step_obj,
                        'Resource {} does not have encryption at rest enabled'
                        ' ({}={}).'.format(addr, attr, vals[attr]),
                    )
                break

        if not found:
            Error(
                _step_obj,
                'Resource {} does not expose a recognised encryption-at-rest'
                ' attribute.'.format(addr),
            )


@then(u'it must have deletion_protection set to true')
def cis_deletion_protection(_step_obj):
    """CIS DB controls: assert that deletion protection is enabled.

    Checks ``deletion_protection`` on RDS instances / clusters and similar
    resources that surface this attribute.
    """
    for resource in _step_obj.context.stash:
        vals = _values(resource)
        addr = _address(resource)
        value = vals.get('deletion_protection')
        if not value:
            Error(
                _step_obj,
                'Resource {} does not have deletion_protection enabled'
                ' (deletion_protection={}).'.format(addr, value),
            )


@then(u'it must have log_file_validation_enabled set to true')
def cis_log_file_validation(_step_obj):
    """CIS 2.2: assert that CloudTrail log file integrity validation is on.

    Accepts both ``enable_log_file_validation`` (provider <= 3.x) and
    ``log_file_validation_enabled`` (provider >= 4.x) attribute names.
    """
    _LOG_ATTRS = ('enable_log_file_validation', 'log_file_validation_enabled')

    for resource in _step_obj.context.stash:
        vals = _values(resource)
        addr = _address(resource)

        found = False
        for attr in _LOG_ATTRS:
            if attr in vals:
                found = True
                if not vals[attr]:
                    Error(
                        _step_obj,
                        'Resource {} does not have log file validation enabled'
                        ' ({}={}).'.format(addr, attr, vals[attr]),
                    )
                break

        if not found:
            Error(
                _step_obj,
                'Resource {} does not expose enable_log_file_validation or'
                ' log_file_validation_enabled.'.format(addr),
            )


@then(u'it must have tags including {tag_key:ANY}')
def cis_has_tag(_step_obj, tag_key):
    """CIS tagging control: assert that a specific tag key is present.

    The resource's ``tags`` attribute must be a dict that contains *tag_key*.

    Example::

        Then it must have tags including Environment
        Then it must have tags including CostCenter
    """
    for resource in _step_obj.context.stash:
        vals = _values(resource)
        addr = _address(resource)
        tags = vals.get('tags') or {}

        if not isinstance(tags, dict):
            Error(
                _step_obj,
                'Resource {} does not have a tags map (tags={}).'.format(addr, tags),
            )
            continue

        if tag_key not in tags:
            Error(
                _step_obj,
                'Resource {} is missing required tag "{}".'.format(addr, tag_key),
            )
