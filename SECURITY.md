# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

## Security Architecture & Triple-Lock Protection

Wise Hybrid MCP interacts directly with real-world financial accounts, multi-currency balances, and bank transfer rails. To guarantee zero unintended financial movement, the server enforces a strict **Triple-Lock Security Model**:

1. **Lock 1: Read-Only by Default (`WISE_MCP_ENABLE_WRITE_TOOLS=false`)**
   - All write operations (`create_quote`, `create_recipient`, `stage_transfer`, `fund_transfer`) are completely disabled and omitted from the MCP tool surface unless explicitly opted into via server configuration.

2. **Lock 2: Explicit Confirmation Parameter (`confirm: true`)**
   - Every write tool requires an explicit parameter `confirm: true`. LLM agents cannot execute write actions without first prompting the user and obtaining explicit approval of the specific financial values, currencies, and destination accounts.

3. **Lock 3: Native Hardware Biometric Gate (`Touch ID` / `Windows Hello`)**
   - High-risk financial operations trigger a native OS verification modal (Apple LocalAuthentication on macOS, Windows Hello UserConsentVerifier on Windows) requiring physical biometric or passcode verification before the HTTP request is dispatched to Wise.
   - On headless Linux environments, write operations fail-closed by default.

## Credential Protection & Host Whitelisting

- **Zero Hardcoded Secrets**: All API tokens and RSA private keys are resolved exclusively from OS Keyrings (macOS Keychain, Windows Credential Manager) or environment variables.
- **Strict Host Validation**: Unless explicitly overridden via `WISE_MCP_ALLOW_CUSTOM_API_URL=true` (strictly for local unit test mocks), the client strictly rejects any request not directed to official Wise endpoints (`api.wise.com`, `api.transferwise.com`, `api.sandbox.transferwise.tech`, `api.wise-sandbox.com`).

## Reporting a Vulnerability

If you discover a security vulnerability, please do NOT file a public issue. Send your report directly to the project security maintainers or file a private security advisory on GitHub.

We will acknowledge receipt within 48 hours and coordinate a coordinated disclosure timeline.
