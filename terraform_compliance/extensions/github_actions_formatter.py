# -*- coding: utf-8 -*-
"""
github_actions_formatter.py — radish extension that emits GitHub Actions
workflow commands for each compliance failure.

When ``--output github-actions`` is passed to tfguard, this formatter is
loaded instead of the default gherkin formatter.  It hooks into radish's
``after.each_scenario`` lifecycle event and writes one ``::error`` command per
failed step to stdout, which GitHub Actions picks up automatically and renders
as PR / commit annotations.

Output format::

    ::error file=FEATURE_FILE,line=STEP_LINE::RESOURCE: MESSAGE
    ::warning file=FEATURE_FILE,line=STEP_LINE::RESOURCE: MESSAGE

``::error`` is used for hard failures and ``::warning`` for steps that were
marked as failures but whose scenarios were set to ``no_failure`` mode.

References:
    https://docs.github.com/en/actions/writing-workflows/choosing-what-your-workflow-does/workflow-commands-for-github-actions#setting-an-error-message
"""

import sys

from radish.extensionregistry import extension
from radish.hookregistry import after
from radish.stepmodel import Step


def _feature_path(step):
    """Return the filesystem path of the feature file that contains *step*."""
    try:
        return step.parent.parent.path
    except AttributeError:
        return 'unknown'


def _step_line(step):
    """Return the 1-based line number of *step* inside its feature file."""
    return getattr(step, 'line', 0)


def _resource_label(step):
    """Return a short label identifying the resource(s) under test."""
    ctx = getattr(step, 'context', None)
    if ctx is None:
        return 'unknown'
    addresses = getattr(ctx, 'addresses', None)
    if isinstance(addresses, list):
        return ', '.join(str(a) for a in addresses) if addresses else getattr(ctx, 'name', 'unknown')
    if addresses:
        return str(addresses)
    return getattr(ctx, 'name', 'unknown')


def _failure_message(step):
    """Extract a single-line failure message from *step*."""
    failure = getattr(step, 'failure', None)
    if failure is None:
        return ''
    raw = getattr(failure, 'traceback', None) or getattr(failure, 'reason', None) or ''
    # Collapse multi-line tracebacks to a single line for the annotation.
    return raw.replace('\n', ' ').replace('\r', '').strip()


def _emit(level, feature_path, line, resource, message):
    """Write a GitHub Actions workflow command to stdout."""
    # Strip ANSI escape codes (colorful adds them) before printing.
    import re
    ansi_escape = re.compile(r'\x1b\[[0-9;]*m')
    clean_message = ansi_escape.sub('', message)
    clean_resource = ansi_escape.sub('', resource)
    print(
        '::{} file={},line={}::{}: {}'.format(
            level, feature_path, line, clean_resource, clean_message
        ),
        flush=True,
    )


@extension
class GitHubActionsFormatter(object):
    """Radish extension that formats compliance failures as GH Actions annotations."""

    LOAD_IF = staticmethod(lambda config: config.formatter == 'github_actions_formatter')
    LOAD_PRIORITY = 30

    def __init__(self):
        after.each_scenario(self._after_scenario)

    def _after_scenario(self, scenario):
        """Emit ``::error`` / ``::warning`` commands for all failed steps."""
        if scenario.state not in ('failed',):
            return

        feature_path = _feature_path(scenario.all_steps[0]) if scenario.all_steps else 'unknown'

        for step in scenario.all_steps:
            if step.state != Step.State.FAILED:
                continue

            line = _step_line(step)
            resource = _resource_label(step)
            message = _failure_message(step)

            # Use ::warning when the scenario ran in no_failure mode (exit 0).
            ctx = getattr(step, 'context', None)
            no_failure = getattr(ctx, 'no_failure', False) if ctx else False
            level = 'warning' if no_failure else 'error'

            _emit(level, feature_path, line, resource, message)
