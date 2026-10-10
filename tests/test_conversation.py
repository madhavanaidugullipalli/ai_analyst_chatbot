from src.conversation.conversation_manager import ConversationManager


def test_conversation_history():
    cm = ConversationManager(max_turns=4)
    cm.add_user("q1")
    cm.add_assistant("a1", sql="SELECT 1", row_count=1)
    cm.add_user("q2")
    cm.add_assistant("a2")
    assert len(cm.turns) == 4
    ctx = cm.recent_context(2)
    assert len(ctx) == 2
    cm.reset()
    assert cm.turns == []
