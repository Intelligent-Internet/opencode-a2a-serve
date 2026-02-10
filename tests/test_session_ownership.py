from unittest.mock import AsyncMock, MagicMock, PropertyMock

import pytest
from a2a.server.agent_execution import RequestContext
from a2a.server.context import ServerCallContext
from a2a.server.events.event_queue import EventQueue

from opencode_a2a.agent import OpencodeAgentExecutor
from opencode_a2a.config import Settings
from opencode_a2a.opencode_client import OpencodeClient


@pytest.fixture
def mock_client():
    client = AsyncMock(spec=OpencodeClient)
    # Define sessions to return
    sessions = ["session-1", "session-2", "session-3"]
    current_idx = 0

    async def side_effect(title=None, directory=None):
        nonlocal current_idx
        res = sessions[current_idx]
        current_idx += 1
        return res

    client.create_session.side_effect = side_effect
    # Mock response for send_message
    response = MagicMock()
    response.text = "OpenCode response"
    response.session_id = "session-1"
    response.message_id = "msg-1"
    client.send_message.return_value = response

    # Use PropertyMock for properties
    type(client).directory = PropertyMock(return_value="/tmp/workspace")
    type(client).settings = PropertyMock(
        return_value=Settings(
            A2A_BEARER_TOKEN="test",
            A2A_JWT_AUDIENCE="test",
            A2A_JWT_ISSUER="test",
            OPENCODE_BASE_URL="http://localhost",
            A2A_ALLOW_DIRECTORY_OVERRIDE=True,
        )
    )
    return client


@pytest.mark.asyncio
async def test_identity_isolation(mock_client):
    executor = OpencodeAgentExecutor(mock_client, streaming_enabled=False)
    event_queue = AsyncMock(spec=EventQueue)

    # User 1, Context A
    context1 = MagicMock(spec=RequestContext)
    context1.task_id = "task-1"
    context1.context_id = "context-A"
    context1.call_context = MagicMock(spec=ServerCallContext)
    context1.call_context.state = {"identity": "user-1"}
    context1.get_user_input.return_value = "hello"
    context1.current_task = None
    context1.message = None
    context1.metadata = None

    await executor.execute(context1, event_queue)
    mock_client.create_session.assert_called_once()
    assert executor._sessions.get("user-1", "context-A") == "session-1"

    # User 2, Context A (Same context ID, different user)
    context2 = MagicMock(spec=RequestContext)
    context2.task_id = "task-2"
    context2.context_id = "context-A"
    context2.call_context = MagicMock(spec=ServerCallContext)
    context2.call_context.state = {"identity": "user-2"}
    context2.get_user_input.return_value = "hello"
    context2.current_task = None
    context2.message = None
    context2.metadata = None

    await executor.execute(context2, event_queue)
    # Should create a NEW session for user-2
    assert mock_client.create_session.call_count == 2
    assert executor._sessions.get("user-2", "context-A") == "session-2"
    # User 1's session should still be there
    assert executor._sessions.get("user-1", "context-A") == "session-1"


@pytest.mark.asyncio
async def test_session_hijack_prevention(mock_client):
    executor = OpencodeAgentExecutor(mock_client, streaming_enabled=False)
    event_queue = AsyncMock(spec=EventQueue)

    # User 1 creates session-1
    context1 = MagicMock(spec=RequestContext)
    context1.task_id = "task-1"
    context1.context_id = "context-A"
    context1.call_context = MagicMock(spec=ServerCallContext)
    context1.call_context.state = {"identity": "user-1"}
    context1.get_user_input.return_value = "hello"
    context1.current_task = None
    context1.message = None
    context1.metadata = None

    await executor.execute(context1, event_queue)
    assert executor._session_owners["session-1"] == "user-1"

    # User 2 tries to bind to session-1 via metadata
    context2 = MagicMock(spec=RequestContext)
    context2.task_id = "task-2"
    context2.context_id = "context-B"
    context2.call_context = MagicMock(spec=ServerCallContext)
    context2.call_context.state = {"identity": "user-2"}
    context2.get_user_input.return_value = "hello"
    context2.metadata = {"opencode_session_id": "session-1"}
    context2.message = None

    # This should fail and emit an error
    await executor.execute(context2, event_queue)

    # Verify error emission
    # Note: we check call_args_list to find the Task
    from a2a.types import Task

    found_error_task = False
    for call in event_queue.enqueue_event.call_args_list:
        event = call[0][0]
        if isinstance(event, Task) and event.status.state.name == "failed":
            # Handle a2a types where parts contain root models
            part = event.status.message.parts[0]
            text = getattr(part, "text", None) or getattr(part.root, "text", "")
            if "not owned by you" in text:
                found_error_task = True
                break
    assert found_error_task
