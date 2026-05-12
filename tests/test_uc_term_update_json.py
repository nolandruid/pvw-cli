import os
import sys
import json
import types
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


azure_module = types.ModuleType("azure")
azure_identity_module = types.ModuleType("azure.identity")
azure_identity_aio_module = types.ModuleType("azure.identity.aio")
azure_core_module = types.ModuleType("azure.core")
azure_core_credentials_module = types.ModuleType("azure.core.credentials")
azure_core_exceptions_module = types.ModuleType("azure.core.exceptions")
rich_module = types.ModuleType("rich")
rich_console_module = types.ModuleType("rich.console")
rich_table_module = types.ModuleType("rich.table")
rich_text_module = types.ModuleType("rich.text")
rich_syntax_module = types.ModuleType("rich.syntax")


class _DummyDefaultAzureCredential:
    async def get_token(self, *_args, **_kwargs):
        raise RuntimeError("Test stub should not request Azure tokens")

    async def close(self):
        return None


class _DummyClientAuthenticationError(Exception):
    pass


class _DummyClientSecretCredential:
    def __init__(self, *_args, **_kwargs):
        pass

    def get_token(self, *_args, **_kwargs):
        raise RuntimeError("Test stub should not request Azure tokens")


class _DummyAccessToken:
    def __init__(self, token="", expires_on=0):
        self.token = token
        self.expires_on = expires_on


class _DummyConsole:
    def __init__(self, *_args, **_kwargs):
        pass

    def print(self, *_args, **_kwargs):
        return None

    def status(self, *_args, **_kwargs):
        class _StatusContext:
            def __enter__(self_inner):
                return self_inner

            def __exit__(self_inner, *_exc):
                return False

            def update(self_inner, *_args, **_kwargs):
                return None

        return _StatusContext()


class _DummyTable:
    def __init__(self, *_args, **_kwargs):
        pass

    def add_column(self, *_args, **_kwargs):
        return None

    def add_row(self, *_args, **_kwargs):
        return None


class _DummyText:
    def __init__(self, *_args, **_kwargs):
        pass


class _DummySyntax:
    def __init__(self, *_args, **_kwargs):
        pass


azure_identity_module.DefaultAzureCredential = _DummyDefaultAzureCredential
azure_identity_module.ClientSecretCredential = _DummyClientSecretCredential
azure_identity_aio_module.DefaultAzureCredential = _DummyDefaultAzureCredential
azure_core_credentials_module.AccessToken = _DummyAccessToken
azure_core_exceptions_module.ClientAuthenticationError = _DummyClientAuthenticationError
rich_console_module.Console = _DummyConsole
rich_table_module.Table = _DummyTable
rich_text_module.Text = _DummyText
rich_syntax_module.Syntax = _DummySyntax

sys.modules.setdefault("azure", azure_module)
sys.modules.setdefault("azure.identity", azure_identity_module)
sys.modules.setdefault("azure.identity.aio", azure_identity_aio_module)
sys.modules.setdefault("azure.core", azure_core_module)
sys.modules.setdefault("azure.core.credentials", azure_core_credentials_module)
sys.modules.setdefault("azure.core.exceptions", azure_core_exceptions_module)
sys.modules.setdefault("rich", rich_module)
sys.modules.setdefault("rich.console", rich_console_module)
sys.modules.setdefault("rich.table", rich_table_module)
sys.modules.setdefault("rich.text", rich_text_module)
sys.modules.setdefault("rich.syntax", rich_syntax_module)

from purviewcli.cli.cli import main
from purviewcli.client._unified_catalog import UnifiedCatalogClient


RUNNER = CliRunner()


def invoke(*args, **kwargs):
    return RUNNER.invoke(main, list(args), catch_exceptions=False, **kwargs)


class TestUcTermUpdateJsonCli:
    @patch("purviewcli.cli.unified_catalog.UnifiedCatalogClient")
    def test_update_json_accepts_id_and_passes_structured_fields(self, mock_client_cls, tmp_path):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.update_term.return_value = {"id": "term-guid-1"}

        payload_file = tmp_path / "updates.json"
        payload_file.write_text(
            json.dumps(
                {
                    "updates": [
                        {
                            "id": "term-guid-1",
                            "managedAttributes": [
                                {
                                    "name": "DataGovernance.Classification",
                                    "value": "PII",
                                }
                            ],
                            "contacts": {
                                "expert": [{"id": "expert-guid-1"}]
                            },
                            "expert_ids": ["expert-guid-2"],
                            "add_expert_ids": ["expert-guid-3"],
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )

        result = invoke("uc", "term", "update-json", "--json-file", str(payload_file))

        assert result.exit_code == 0, result.output
        mock_client.update_term.assert_called_once()
        args = mock_client.update_term.call_args[0][0]
        assert args["--term-id"] == ["term-guid-1"]
        assert args["--managed-attributes"][0][0]["name"] == "DataGovernance.Classification"
        assert args["--contacts"][0]["expert"][0]["id"] == "expert-guid-1"
        assert args["--expert-id"] == ["expert-guid-2"]
        assert args["--add-expert-id"] == ["expert-guid-3"]

    @patch("purviewcli.cli.unified_catalog.UnifiedCatalogClient")
    def test_update_json_prefers_id_over_term_id(self, mock_client_cls, tmp_path):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.update_term.return_value = {"id": "preferred-guid"}

        payload_file = tmp_path / "updates.json"
        payload_file.write_text(
            json.dumps(
                {
                    "updates": [
                        {
                            "id": "preferred-guid",
                            "term_id": "legacy-guid",
                            "name": "Updated Term",
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )

        result = invoke("uc", "term", "update-json", "--json-file", str(payload_file))

        assert result.exit_code == 0, result.output
        args = mock_client.update_term.call_args[0][0]
        assert args["--term-id"] == ["preferred-guid"]


class TestUnifiedCatalogClientUpdateTerm:
    @patch("purviewcli.client.endpoint.get_data")
    @patch.object(UnifiedCatalogClient, "get_term_by_id")
    def test_update_term_preserves_owner_when_updating_expert(self, mock_get_term_by_id, mock_get_data):
        mock_get_term_by_id.return_value = {
            "id": "term-guid-1",
            "name": "Term",
            "description": "Desc",
            "domain": "domain-guid",
            "status": "Draft",
            "contacts": {
                "owner": [{"id": "owner-guid-1"}],
                "expert": [{"id": "expert-guid-1"}],
            },
            "managedAttributes": [],
        }
        mock_get_data.side_effect = lambda http_dict: http_dict

        client = UnifiedCatalogClient()
        result = client.update_term(
            {
                "--term-id": ["term-guid-1"],
                "--expert-id": ["expert-guid-2"],
            }
        )

        assert result["payload"]["contacts"]["owner"] == [{"id": "owner-guid-1"}]
        assert result["payload"]["contacts"]["expert"] == [{"id": "expert-guid-2"}]

    @patch("purviewcli.client.endpoint.get_data")
    @patch.object(UnifiedCatalogClient, "get_term_by_id")
    def test_update_term_merges_managed_attributes_from_direct_list_and_custom_attributes(
        self, mock_get_term_by_id, mock_get_data
    ):
        mock_get_term_by_id.return_value = {
            "id": "term-guid-1",
            "name": "Term",
            "description": "Desc",
            "domain": "domain-guid",
            "status": "Draft",
            "contacts": {},
            "managedAttributes": [
                {"name": "Existing.Field", "value": "old"},
            ],
        }
        mock_get_data.side_effect = lambda http_dict: http_dict

        client = UnifiedCatalogClient()
        result = client.update_term(
            {
                "--term-id": ["term-guid-1"],
                "--managed-attributes": [[{"name": "Direct.Field", "value": "direct"}]],
                "--custom-attributes": [json.dumps({"Nested": {"Field": "nested"}})],
            }
        )

        managed_attrs = result["payload"]["managedAttributes"]
        managed_map = {item["name"]: item["value"] for item in managed_attrs}
        assert managed_map["Existing.Field"] == "old"
        assert managed_map["Direct.Field"] == "direct"
        assert managed_map["Nested.Field"] == "nested"
