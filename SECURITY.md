# Security Policy

Remirdy Blender Studio MCP controls Blender through a local bridge. Please treat
reported vulnerabilities seriously, especially anything that could bypass the
named-operation registry, write outside the configured workspace, or expose API
keys.

## Supported Versions

The `main` branch and the latest tagged release receive security fixes.

## Reporting a Vulnerability

Please do not open a public issue for sensitive reports. Send a private report
to the project maintainers with:

- Affected version or commit
- Steps to reproduce
- Expected and actual impact
- Any relevant logs, screenshots, or proof-of-concept files

We will acknowledge valid reports as quickly as possible and publish a fix or
mitigation once the issue is understood.

## Security Model

- The Blender add-on dispatches named operations registered in
  `blender_addon/blender_ops/registry.py`.
- The MCP server should not send arbitrary Python source to Blender.
- Generated files should remain inside `REMIRDY_WORKSPACE`.
- API keys belong in `.env` or the MCP client environment, never in committed
  files.
