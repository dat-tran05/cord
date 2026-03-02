from app.agent.tools import SUPERVISOR_TOOLS, get_tool_schemas


def test_tool_schemas_are_valid_openai_format():
    schemas = get_tool_schemas()
    assert isinstance(schemas, list)
    assert len(schemas) > 0
    for schema in schemas:
        assert schema["type"] == "function"
        assert "name" in schema["function"]
        assert "description" in schema["function"]
        assert "parameters" in schema["function"]


def test_all_expected_tools_present():
    names = {t["function"]["name"] for t in get_tool_schemas()}
    expected = {"lookup_profile", "transition_stage", "get_objection_counters", "log_outcome"}
    assert expected.issubset(names)
