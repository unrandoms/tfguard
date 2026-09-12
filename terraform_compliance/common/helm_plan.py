# -*- coding: utf-8 -*-
"""
helm_plan.py — Helm chart → pseudo Terraform plan converter.

Usage::

    from terraform_compliance.common.helm_plan import write_helm_plan

    plan_path = write_helm_plan('/path/to/chart', '/path/to/values.yaml')
    # plan_path is a temporary JSON file that TerraformParser can consume.

The generated JSON mimics a Terraform plan's ``planned_values.root_module``
structure so that the existing step definitions can traverse it unchanged.
Each Kubernetes manifest becomes a ``kubernetes_manifest.<Kind>_<name>``
resource whose ``values`` dict contains the manifest's top-level keys
(``api_version``, ``kind``, ``metadata``, ``spec``).
"""

import json
import os
import subprocess
import tempfile

try:
    import yaml
except ImportError:
    yaml = None  # surfaced as a runtime error in render_helm_chart

# Terraform plan envelope that TerraformParser accepts without version errors.
_PLAN_FORMAT_VERSION = '1.0'
_PLAN_TERRAFORM_VERSION = '1.5.0'


def render_helm_chart(chart_dir, values_file=None):
    """Run ``helm template`` and return the list of parsed manifest dicts.

    :param chart_dir: Absolute or relative path to the Helm chart directory.
    :param values_file: Optional path to a ``-f``/``--values`` YAML file.
    :returns: List of non-null Kubernetes resource dicts.
    :raises RuntimeError: When the ``yaml`` package is unavailable.
    :raises subprocess.CalledProcessError: When ``helm template`` fails.
    """
    if yaml is None:
        raise RuntimeError(
            'PyYAML is required for Helm support.  '
            'Install it with: pip install pyyaml'
        )

    cmd = ['helm', 'template', chart_dir]
    if values_file:
        cmd.extend(['-f', values_file])

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=True,
    )

    manifests = list(yaml.safe_load_all(result.stdout))
    return [m for m in manifests if m is not None]


def _resource_name_from_manifest(manifest):
    """Derive a Terraform-style resource name from a Kubernetes manifest.

    For a manifest with ``kind: Deployment`` and ``metadata.name: my-app``,
    this returns ``'deployment_my_app'``.
    """
    kind = manifest.get('kind', 'Unknown').lower()
    meta = manifest.get('metadata') or {}
    name = meta.get('name', 'unknown').lower()
    # Replace characters that are invalid in Terraform resource names.
    safe_name = name.replace('-', '_').replace('.', '_').replace('/', '_')
    return '{}_{}'.format(kind, safe_name)


def helm_manifests_to_plan_dict(manifests):
    """Convert a list of Kubernetes manifest dicts to a pseudo Terraform plan.

    The returned dict has the same top-level shape as a real ``terraform show
    -json`` plan file so that :class:`TerraformParser` can parse it without
    modification.

    Resource addresses follow the pattern::

        kubernetes_manifest.<Kind>_<name>

    and the ``values`` sub-dict exposes ``api_version``, ``kind``,
    ``metadata``, and ``spec`` so that feature steps can assert against them.

    :param manifests: List of dicts from :func:`render_helm_chart`.
    :returns: Dict suitable for writing as a Terraform plan JSON file.
    """
    resources = []
    for manifest in manifests:
        rname = _resource_name_from_manifest(manifest)
        kind = manifest.get('kind', 'Unknown')
        meta = manifest.get('metadata') or {}

        resources.append({
            'address': 'kubernetes_manifest.{}'.format(rname),
            'mode': 'managed',
            'type': 'kubernetes_manifest',
            'name': rname,
            'provider_name': 'registry.terraform.io/hashicorp/kubernetes',
            'schema_version': 0,
            'values': {
                'api_version': manifest.get('apiVersion', ''),
                'kind': kind,
                'metadata': meta,
                'spec': manifest.get('spec') or {},
            },
            'sensitive_values': {},
        })

    return {
        'format_version': _PLAN_FORMAT_VERSION,
        'terraform_version': _PLAN_TERRAFORM_VERSION,
        'variables': {},
        'planned_values': {
            'root_module': {
                'resources': resources,
            }
        },
        'resource_changes': [],
        'configuration': {
            'root_module': {
                'resources': [],
            }
        },
    }


def write_helm_plan(chart_dir, values_file=None, output_path=None):
    """Render a Helm chart and write the pseudo-plan JSON to *output_path*.

    If *output_path* is ``None`` a temporary file is created automatically.
    The caller is responsible for cleaning up the file when it is no longer
    needed (``terraform_compliance``'s ``atexit`` cleanup covers the usual
    cache directory, but not arbitrary temp files).

    :param chart_dir: Path to the Helm chart directory.
    :param values_file: Optional path to a Helm values YAML file.
    :param output_path: Optional destination path for the generated JSON.
    :returns: Absolute path to the written JSON file.
    """
    manifests = render_helm_chart(chart_dir, values_file)
    plan = helm_manifests_to_plan_dict(manifests)

    if output_path is None:
        fd, output_path = tempfile.mkstemp(
            suffix='.json', prefix='tfguard_helm_plan_'
        )
        os.close(fd)

    with open(output_path, 'w', encoding='utf-8') as fh:
        json.dump(plan, fh, indent=2)

    return os.path.abspath(output_path)
