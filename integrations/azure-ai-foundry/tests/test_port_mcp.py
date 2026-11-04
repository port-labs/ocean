from helpers.port_mcp import port_mcp_connection_name


def test_port_mcp_connection_name_sanitizes_agent_id() -> None:
    name = port_mcp_connection_name("my-agent_123")
    assert name.startswith("port-")
    assert len(name) <= 33
    assert name == "port-my-agent_123"


def test_port_mcp_connection_name_short_agent_id() -> None:
    name = port_mcp_connection_name("ab")
    assert name.startswith("port-")
    assert len(name) >= 3
