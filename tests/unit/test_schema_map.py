from app.agents.schema_agent import SchemaAgent


def test_schema_map_includes_foreign_key_relationships() -> None:
    schema = {
        "tables": ["accounts", "subscriptions"],
        "columns": {
            "accounts": [
                {
                    "column": "account_id",
                    "type": "text",
                    "nullable": False,
                    "constraint": "PRIMARY KEY",
                    "foreign_table": None,
                    "foreign_column": None,
                }
            ],
            "subscriptions": [
                {
                    "column": "account_id",
                    "type": "text",
                    "nullable": False,
                    "constraint": "FOREIGN KEY",
                    "foreign_table": "accounts",
                    "foreign_column": "account_id",
                }
            ],
        },
    }

    compact = SchemaAgent(connector=None)._build_compact_map(schema)  # type: ignore[arg-type]

    assert "subscriptions(account_id:text [FK -> accounts.account_id])" in compact
