# Wise Hybrid MCP Server (`wise-mcp`)

[![Python Version](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Checked with mypy](https://img.shields.io/badge/mypy-checked-blue)](https://mypy-lang.org/)
[![Coverage](https://img.shields.io/badge/coverage-%3E80%25-green)](https://pytest-cov.readthedocs.io/)

A secure, vendor-neutral, standalone [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) server and Python SDK for **Wise** (formerly TransferWise) multi-currency business treasury, EEA/UK PSD2 Strong Customer Authentication (SCA) digital signing, foreign exchange quotes, balance statement exports, and payout staging.

---

## 🌟 Highlights

- **Vendor-Neutral & Open-Source**: Standalone Python package (`wise` SDK + `wise_mcp` server), free of hardcoded proprietary data or proprietary identifiers.
- **Triple-Lock Security Architecture**:
  - **Lock 1 (Policy)**: Read-only by default (`WISE_MCP_ENABLE_WRITE_TOOLS=false`). Write tools are hidden from the MCP tool surface unless explicitly enabled by the operator.
  - **Lock 2 (Intent)**: Every write tool enforces an explicit `confirm: true` parameter, requiring the calling agent to explain and verify financial values with the human user.
  - **Lock 3 (Physical Presence)**: Hardware biometric presence verification via native OS modals (**Touch ID** / **Face ID** / Apple LocalAuthentication on macOS; **Windows Hello** PIN / Fingerprint / Facial Recognition on Windows).
- **EEA / UK PSD2 Strong Customer Authentication (SCA) Engine**: Transparent interception of HTTP `403` responses containing `x-2fa-approval` headers, automatically signing the one-time challenge token with an RSA-2048 private key via `X-Signature` (SHA256withRSA) and retrying requests without human intervention.
- **Native OS Keychain & Credential Manager Integration**: Zero plain-text credentials in config files or environment variables; securely stores API Bearer tokens and RSA private keys in the OS keyring with open application ACLs on macOS to eliminate repeated password popups.
- **Strict Host Validation**: Whitelists only official Wise endpoints (`api.wise.com`, `api.transferwise.com`, `api.sandbox.transferwise.tech`, `api.wise-sandbox.com`).

---

## 🛠️ Tool Catalog (13 Tools)

### Read Tools (Enabled by Default)

| Tool Name | Description |
| :--- | :--- |
| `list_profiles` | List all personal and business profiles associated with the API token. Returns `profileId`, account holder name, and business metadata. |
| `list_balances` | Retrieve real-time multi-currency account balances and savings jars for a profile (`STANDARD` and `SAVINGS` jars). |
| `get_exchange_rate` | Fetch live and historical mid-market foreign exchange rates between any currency pair (e.g., `EUR` $\leftrightarrow$ `ZAR`, `USD`, `GBP`). |
| `get_quote` | Inspect an existing FX quote by ID or UUID, including guaranteed exchange rate, fee breakdown, and estimated delivery timeline. |
| `get_balance_statement` | Retrieve official balance statements with automatic EEA PSD2 SCA signing. Supports `json`, `csv`, `xml` (`camt.053`), and `mt940` formats with itemized or flat fee accounting layouts. |
| `list_recipients` | List and search registered beneficiary bank accounts by currency, recipient name, or account identifiers. |
| `list_transfers` | List recent transfer orders and inspect their lifecycle status (`incoming_payment_waiting`, `processing`, `funds_converted`, `outgoing_payment_sent`, `cancelled`). |
| `get_transfer` | Retrieve transfer details, applied exchange rates, and fee metadata for accounting and invoice reconciliation. |

### Write Tools (Opt-in via `WISE_MCP_ENABLE_WRITE_TOOLS=true` + `confirm: true` + Biometric Gate)

| Tool Name | Description |
| :--- | :--- |
| `create_quote` | Create an authenticated quote locking in the mid-market exchange rate and transfer fee for 30 minutes. Defaults to `pay_in="BALANCE"` (€0 fee for EUR SEPA) and returns `quoteUuid` needed for transfer staging. |
| `create_recipient` | Register a new beneficiary recipient bank account (supports SEPA IBAN for EUR, UK Sort Code for GBP, South African clearing codes for ZAR, and US ACH for USD). |
| `stage_transfer` | Create and queue an unfunded transfer in Wise in `incoming_payment_waiting` state with an invoice reference and client idempotency UUID (`customerTransactionId`). |
| `cancel_transfer` | Cancel an existing pending or unfunded transfer in Wise before it is funded or processed. |
| `fund_transfer` | **High-Risk Operation**: Irrevocably fund and execute a pending transfer order from a Wise multi-currency balance (always requires fresh biometric prompt). |

---

## 🔐 The Triple-Lock Security Model

```
                    ┌─────────────────────────────────┐
                    │  AI Agent Calls Tool Execution  │
                    └────────────────┬────────────────┘
                                     │
           [Lock 1] Server Policy    ▼
    Is WISE_MCP_ENABLE_WRITE_TOOLS=true?  ── No ──► [403] Tool Disabled by Policy
                                     │ Yes
           [Lock 2] Explicit Intent  ▼
               Did user confirm=true?     ── No ──► [400] Explicit Confirmation Required
                                     │ Yes
        [Lock 3] Physical Biometric  ▼
       Touch ID / Windows Hello Pass?     ── No ──► [401] Biometric Verification Denied
                                     │ Yes
                                     ▼
                      ┌───────────────────────────────┐
                      │ Execute HTTP Request to Wise  │
                      └──────────────┬────────────────┘
                                     │
                 HTTP 403 & x-2fa-approval challenge?
                                     │ Yes
                                     ▼
                      ┌───────────────────────────────┐
                      │ Sign One-Time Token (RSA-2048)│
                      │ Retry with X-Signature Header │
                      └───────────────────────────────┘
```

---

## 🚀 Quickstart & Installation

### 1. Installation

Install via `pip` or `uv`:

```bash
# Using uv (recommended)
uv pip install wise-mcp

# Or standard pip
pip install wise-mcp
```

Or install in development mode from source:

```bash
git clone https://github.com/hemelbesem90s/Wise-MCP.git
cd Wise-MCP
uv venv
source .venv/bin/activate
uv pip install -e ".[dev]"
```

---

### 2. Configure Credentials in OS Keyring

Store your Wise API token securely in your operating system's native credential store:

```bash
# Stores token in macOS Keychain or Windows Credential Manager under service 'wise_mcp'
wise-mcp --set-token "your-wise-api-token"
```

To eliminate repeated macOS password prompts when calling Keychain from command-line tools:

```bash
wise-mcp --fix-keychain-acl
```

---

### 3. Generate Strong Customer Authentication (SCA) Keys

Under EEA/UK PSD2 regulations, sensitive actions (such as pulling balance statements or funding transfers) require 2-factor cryptographic signing.

Generate an RSA-2048 keypair directly from the CLI:

```bash
# Generates RSA-2048 keypair and stores private key in OS Keyring:
wise-mcp --generate-sca-keys

# Or save the private key to a protected local PEM file:
wise-mcp --generate-sca-keys ~/.config/wise/private.pem
```

The CLI prints the **Public Key (`-----BEGIN PUBLIC KEY----- ...`)** to your terminal. Save that block as `wise_public.pem` and upload it to Wise:
1. Log in to [Wise Business](https://wise.com).
2. Go to **Settings** $\rightarrow$ **API tokens**.
3. Under **Manage 2FA keys** (or **Add new key**), upload `wise_public.pem` and copy your API token.

---

### 4. Verify Setup

Run the configuration check and test your hardware biometric verification:

```bash
# Validate credentials and configuration
wise-mcp --check-config

# Test native Touch ID / Windows Hello hardware prompt
wise-mcp --test-biometric
```

---

## ⚙️ Configuration Reference

Configuration can be supplied via environment variables or a `.env` file:

| Variable | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `WISE_MCP_API_TOKEN` | String | *(Keyring)* | Wise API Bearer token. Recommended to store in OS keyring via `wise-mcp --set-token`. |
| `WISE_MCP_API_URL` | URL | `https://api.wise.com` | Base URL for Wise API. Set to `https://api.sandbox.transferwise.tech` for Sandbox. |
| `WISE_MCP_PROFILE_ID` | Integer | `None` | Default profile ID. If omitted and the token has exactly one profile, it is selected automatically. |
| `WISE_MCP_SCA_PRIVATE_KEY_PEM` | String | *(Keyring)* | RSA-2048 private key in PEM format for SCA digital signing. |
| `WISE_MCP_SCA_PRIVATE_KEY_PATH` | Path | `None` | Path to private key `.pem` file on disk. |
| `WISE_MCP_ENABLE_WRITE_TOOLS` | Boolean | `false` | **Lock 1**: Enable write operations (`create_quote`, `create_recipient`, `stage_transfer`, `cancel_transfer`, `fund_transfer`). |
| `WISE_MCP_REQUIRE_BIOMETRIC` | Boolean | `true` | **Lock 3**: Require native Touch ID / Windows Hello verification for write actions. |
| `WISE_MCP_BIOMETRIC_TTL_SECONDS` | Integer | `300` | In-memory approval window (default: 5 min) across batch write operations (0 = prompt every call). `fund_transfer` always requires fresh verification. |
| `WISE_MCP_KEYRING_SERVICE` | String | `wise_mcp` | OS Keyring service identifier name. |
| `WISE_MCP_LOG_LEVEL` | String | `WARNING` | Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`). |
| `WISE_MCP_ALLOW_CUSTOM_API_URL`| Boolean | `false` | Bypass host whitelist strictly for test mock servers. |

---

## 🖥️ MCP Client Integration

### Claude Desktop (`claude_desktop_config.json`)

Add `wise-mcp` to your Claude Desktop configuration:

**macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`  
**Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "wise": {
      "command": "wise-mcp",
      "env": {
        "WISE_MCP_ENABLE_WRITE_TOOLS": "false"
      }
    }
  }
}
```

*Note: With credentials stored in OS Keyring, you do not need to put `WISE_MCP_API_TOKEN` in plain text.*

---

### Google Antigravity / Cursor IDE

Add `wise` to your MCP configuration (`mcp_config.json` or workspace settings):

```json
{
  "mcpServers": {
    "wise": {
      "command": "/Users/user/.venv/bin/wise-mcp",
      "args": [],
      "env": {
        "WISE_MCP_ENABLE_WRITE_TOOLS": "true",
        "WISE_MCP_REQUIRE_BIOMETRIC": "true"
      }
    }
  }
}
```

---

## 🧪 Development & Testing

Run tests and quality checks using `make` or direct commands:

```bash
# Run pytest with code coverage (enforcing >=80%)
pytest --cov=wise --cov=wise_mcp -v

# Run linting and format checks
ruff check .
ruff format --check .

# Run static type checking
mypy .

# Run security static analysis
bandit -q -r wise wise_mcp
```

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
