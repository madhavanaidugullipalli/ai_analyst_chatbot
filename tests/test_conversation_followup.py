from src.conversation.conversation_manager import ConversationManager


def test_follow_up_enrichment():
    cm = ConversationManager()
    cm.add_user("Which product has the highest revenue?")
    cm.add_assistant("Product A", sql="SELECT product_name FROM sales LIMIT 1")
    q = "Show the same for the South region"
    assert cm.looks_like_follow_up(q)
    enriched = cm.enrich_question(q)
    assert "Follow-up" in enriched
    assert "South" in enriched


def test_clarification_for_vague():
    cm = ConversationManager()
    msg = cm.needs_clarification("analyze this", ["region", "sales_amount"])
    assert msg is not None
    assert "broad" in msg.lower()
