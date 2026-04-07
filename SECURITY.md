# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.2.x   | :white_check_mark: |
| 0.1.x   | :white_check_mark: |

## Local-Only Architecture

homelife.ai is designed as a **local-only** system. All captured data -- camera frames, screenshots, audio recordings, transcriptions, analysis results, and the SQLite database -- remains on the user's machine. No data is transmitted to external servers beyond the configured LLM API calls (Gemini or Claude) required for analysis.

Users should be aware that:

- LLM API calls send captured images, audio, and text to the configured provider (Google Gemini or Anthropic Claude) for analysis.
- Optional notification integrations (Discord, LINE) transmit report summaries to those platforms.
- No other network communication occurs during normal operation.

## Reporting a Vulnerability

If you discover a security vulnerability in homelife.ai, please report it responsibly. **Do not open a public GitHub issue for security vulnerabilities.**

### How to Report

1. **GitHub Security Advisory** (preferred): Navigate to the repository's Security tab and create a private security advisory.
2. **Email**: Send a detailed report to the repository maintainer via the contact information listed on their GitHub profile.

### What to Include

- A clear description of the vulnerability
- Steps to reproduce the issue
- The potential impact
- Any suggested fixes, if applicable

### Response Timeline

- **Acknowledgment**: Within 48 hours of receiving the report
- **Initial assessment**: Within 7 days
- **Fix or mitigation**: Targeted within 30 days, depending on severity and complexity

### What to Expect

- You will receive confirmation that your report has been received.
- We will work with you to understand and validate the issue.
- A fix will be developed and tested before public disclosure.
- You will be credited in the release notes (unless you prefer to remain anonymous).

## Responsible Disclosure

We ask that you:

- Allow reasonable time for us to address the issue before any public disclosure.
- Avoid accessing or modifying other users' data.
- Act in good faith to avoid disruption to the project and its users.

## Security Best Practices for Users

- Keep your `data/life.db` settings table (containing API keys) and `.env` file out of version control and restrict file permissions on the `data/` directory.
- Run the daemon and MJPEG live feed (port 3002) on a trusted local network or localhost only.
- Regularly update dependencies to receive security patches.
- Review settings in the Settings UI to ensure capture settings match your privacy preferences.
