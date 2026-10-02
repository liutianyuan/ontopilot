from ontopilot.agent import _parse_text_tool_calls


def test_parses_xml_like_text_tool_call_without_domain_assumptions():
    content = """<tool_call>
function=object_query>
<parameter=object_type>
Asset
</parameter>
<parameter=properties>
["id", "serial_number", "temperature"]
</parameter>
<parameter=filters>
{"serial_number": "SN-42"}
</parameter>
</function>
</tool_call>"""

    calls = _parse_text_tool_calls(content)

    assert len(calls) == 1
    assert calls[0]["name"] == "object_query"
    assert calls[0]["args"] == {
        "object_type": "Asset",
        "properties": ["id", "serial_number", "temperature"],
        "filters": {"serial_number": "SN-42"},
    }


def test_parses_json_text_tool_call():
    calls = _parse_text_tool_calls(
        '<tool_call>{"name":"get_object_context","arguments":{"object_key":"A-1"}}</tool_call>'
    )

    assert calls[0]["name"] == "get_object_context"
    assert calls[0]["args"] == {"object_key": "A-1"}
