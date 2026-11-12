"""Direct execution tests for all Wise MCP tools."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
import pytest

from wise_mcp.tools import (
    CancelTransferTool,
    CreateQuoteTool,
    CreateRecipientTool,
    FundTransferTool,
    GetBalanceStatementTool,
    GetExchangeRateTool,
    GetQuoteTool,
    GetTransferTool,
    ListBalancesTool,
    ListProfilesTool,
    ListRecipientsTool,
    ListTransfersTool,
    StageTransferTool,
    ToolRegistry,
    register_all_tools,
)


def test_registry_registration() -> None:
    reg = ToolRegistry()
    register_all_tools(reg)
    tools = reg.list_tools()
    assert len(tools) == 13
    assert reg.get("list_profiles") is not None
    assert reg.get("stage_transfer") is not None
    assert reg.get("cancel_transfer") is not None
    assert reg.get("fund_transfer") is not None


@pytest.mark.asyncio
async def test_list_profiles_tool() -> None:
    tool = ListProfilesTool()
    client = AsyncMock()
    client.list_profiles.return_value = [
        MagicMock(model_dump=lambda: {"id": 1, "type": "business"})
    ]
    res = await tool.execute(client, {})
    assert res["count"] == 1
    assert res["profiles"][0]["id"] == 1


@pytest.mark.asyncio
async def test_list_balances_auto_select_profile() -> None:
    tool = ListBalancesTool()
    client = AsyncMock()
    client.config.profile_id = None
    client.list_profiles.return_value = [MagicMock(id=9999)]
    client.list_balances.return_value = [
        MagicMock(model_dump=lambda: {"id": 1, "currency": "EUR"})
    ]

    res = await tool.execute(client, {})
    assert res["profile_id"] == 9999
    assert res["count"] == 1


@pytest.mark.asyncio
async def test_list_balances_missing_profile_raises() -> None:
    tool = ListBalancesTool()
    client = AsyncMock()
    client.config.profile_id = None
    client.list_profiles.return_value = [MagicMock(id=1), MagicMock(id=2)]

    with pytest.raises(ValueError, match="profile_id is required"):
        await tool.execute(client, {})


@pytest.mark.asyncio
async def test_rates_tool() -> None:
    tool = GetExchangeRateTool()
    client = AsyncMock()
    client.get_exchange_rates.return_value = [
        MagicMock(model_dump=lambda: {"rate": 20.0, "source": "EUR", "target": "ZAR"})
    ]

    res = await tool.execute(client, {"source": "EUR", "target": "ZAR"})
    assert res["rates"][0]["rate"] == 20.0


@pytest.mark.asyncio
async def test_quote_tools() -> None:
    get_tool = GetQuoteTool()
    create_tool = CreateQuoteTool()
    client = AsyncMock()
    client.config.profile_id = None
    client.list_profiles.return_value = [MagicMock(id=111)]
    client.get_quote.return_value = MagicMock(model_dump=lambda: {"id": "q-1", "rate": 20.0})
    client.create_quote.return_value = MagicMock(model_dump=lambda: {"id": "q-2", "rate": 20.0})

    # Auto profile select in get_quote
    res_get = await get_tool.execute(client, {"quote_id": "q-1"})
    assert res_get["id"] == "q-1"

    # Auto profile select in create_quote
    res_create = await create_tool.execute(
        client,
        {"source_currency": "EUR", "target_currency": "ZAR", "source_amount": 500.0},
    )
    assert res_create["id"] == "q-2"
    client.create_quote.assert_called_with(
        111,
        "EUR",
        "ZAR",
        source_amount=500.0,
        target_amount=None,
        target_account_id=None,
        pay_in="BALANCE",
    )

    # Missing profile raises
    client.list_profiles.return_value = [MagicMock(id=1), MagicMock(id=2)]
    with pytest.raises(ValueError, match="profile_id is required"):
        await get_tool.execute(client, {"quote_id": "q-1"})

    with pytest.raises(ValueError, match="profile_id is required"):
        await create_tool.execute(
            client,
            {"source_currency": "EUR", "target_currency": "ZAR", "source_amount": 500.0},
        )


@pytest.mark.asyncio
async def test_statements_tool_dict_and_raw() -> None:
    tool = GetBalanceStatementTool()
    client = AsyncMock()
    client.config.profile_id = 12345
    client.get_balance_statement.return_value = {"transactions": []}

    res_dict = await tool.execute(
        client,
        {
            "balance_id": 101,
            "currency": "EUR",
            "interval_start": "2026-01-01T00:00:00Z",
            "interval_end": "2026-01-31T23:59:59Z",
        },
    )
    assert "statement" in res_dict

    client.get_balance_statement.return_value = "CSV RAW CONTENT"
    res_raw = await tool.execute(
        client,
        {
            "balance_id": 101,
            "currency": "EUR",
            "interval_start": "2026-01-01T00:00:00Z",
            "interval_end": "2026-01-31T23:59:59Z",
            "format": "csv",
        },
    )
    assert res_raw["content"] == "CSV RAW CONTENT"

    # Auto select profile and missing profile
    client.config.profile_id = None
    client.list_profiles.return_value = [MagicMock(id=888)]
    res_auto = await tool.execute(
        client,
        {
            "balance_id": 101,
            "currency": "EUR",
            "interval_start": "2026-01-01T00:00:00Z",
            "interval_end": "2026-01-31T23:59:59Z",
        },
    )
    assert res_auto["profile_id"] == 888

    client.list_profiles.return_value = [MagicMock(id=1), MagicMock(id=2)]
    with pytest.raises(ValueError, match="profile_id is required"):
        await tool.execute(
            client,
            {
                "balance_id": 101,
                "currency": "EUR",
                "interval_start": "2026-01-01T00:00:00Z",
                "interval_end": "2026-01-31T23:59:59Z",
            },
        )


@pytest.mark.asyncio
async def test_recipients_tools() -> None:
    list_tool = ListRecipientsTool()
    create_tool = CreateRecipientTool()
    client = AsyncMock()
    client.config.profile_id = None
    client.list_profiles.return_value = [MagicMock(id=777)]
    client.list_recipients.return_value = [MagicMock(model_dump=lambda: {"id": 1})]
    client.create_recipient.return_value = MagicMock(model_dump=lambda: {"id": 2, "accountHolderName": "Test"})

    res_list = await list_tool.execute(client, {"currency": "EUR"})
    assert res_list["count"] == 1

    res_create = await create_tool.execute(
        client,
        {
            "account_holder_name": "Test",
            "currency": "EUR",
            "type": "iban",
            "details": {"iban": "NL00BANK0123456789"},
        },
    )
    assert res_create["id"] == 2

    # Multiple profiles
    client.list_profiles.return_value = [MagicMock(id=1), MagicMock(id=2)]
    with pytest.raises(ValueError, match="profile_id is required"):
        await create_tool.execute(
            client,
            {
                "account_holder_name": "Test",
                "currency": "EUR",
                "type": "iban",
                "details": {"iban": "NL00BANK0123456789"},
            },
        )


@pytest.mark.asyncio
async def test_transfers_tools_execution() -> None:
    list_tool = ListTransfersTool()
    get_tool = GetTransferTool()
    stage_tool = StageTransferTool()
    cancel_tool = CancelTransferTool()
    fund_tool = FundTransferTool()

    client = AsyncMock()
    client.config.profile_id = 12345
    client.list_transfers.return_value = [MagicMock(model_dump=lambda: {"id": 11})]
    client.get_transfer.return_value = MagicMock(model_dump=lambda: {"id": 11, "status": "processing"})
    client.stage_transfer.return_value = MagicMock(model_dump=lambda: {"id": 12, "status": "incoming_payment_waiting"})
    client.cancel_transfer.return_value = MagicMock(model_dump=lambda: {"id": 12, "status": "cancelled"})
    client.fund_transfer.return_value = MagicMock(model_dump=lambda: {"status": "COMPLETED"})

    res_list = await list_tool.execute(client, {})
    assert res_list["count"] == 1

    res_get = await get_tool.execute(client, {"transfer_id": 11})
    assert res_get["id"] == 11

    res_stage = await stage_tool.execute(
        client,
        {
            "target_account_id": 55,
            "quote_uuid": "quote-xyz",
            "reference": "TEST-REF",
        },
    )
    assert res_stage["status"] == "incoming_payment_waiting"

    res_cancel = await cancel_tool.execute(client, {"transfer_id": 12})
    assert res_cancel["status"] == "cancelled"
    client.cancel_transfer.assert_called_with(12)

    res_fund = await fund_tool.execute(client, {"transfer_id": 12})
    assert res_fund["status"] == "COMPLETED"

    # Missing profile
    client.config.profile_id = None
    client.list_profiles.return_value = [MagicMock(id=1), MagicMock(id=2)]
    with pytest.raises(ValueError, match="profile_id is required"):
        await list_tool.execute(client, {})
    with pytest.raises(ValueError, match="profile_id is required"):
        await fund_tool.execute(client, {"transfer_id": 12})
