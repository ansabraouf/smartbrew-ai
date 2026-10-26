"""Core tests for SmartBrew AI services."""

from src.services import (
    register_user, authenticate, list_drinks, recipe_availability, create_order,
    process_payment, get_receipt, save_favorite, get_favorites, update_ingredient,
    recommendations, parse_natural_language, get_events
)

def customer(db):
    """Authenticate the seeded demo customer.

    Args:
        db: Test database path.

    Returns:
        Authenticated customer record.
    """
    user = authenticate("customer", "BrewDemo123!", db)
    assert user
    return user

def test_registration_and_authentication(db_path):
    """Verify account creation, password checks, and duplicate handling."""
    ok, _ = register_user("newcustomer", "GoodPassword123", db_path)
    assert ok
    assert authenticate("newcustomer", "GoodPassword123", db_path)
    assert authenticate("newcustomer", "wrongpassword", db_path) is None
    assert not register_user("newcustomer", "GoodPassword123", db_path)[0]

def test_menu_and_inventory(db_path):
    """Verify seeded menu data and inventory checks."""
    drinks = list_drinks(db_path)
    assert len(drinks) >= 5
    latte = next(d for d in drinks if d["name"] == "Latte")
    assert recipe_availability(latte["recipe"], db_path)[0]
    ok, message = update_ingredient("milk", 0, 200, db_path=db_path)
    assert ok and "milk" in message.lower()
    assert not recipe_availability(latte["recipe"], db_path)[0]

def test_order_payment_receipt_and_favorite(db_path):
    """Verify successful order, payment, receipt, and favorite flow."""
    user = customer(db_path)
    latte = next(d for d in list_drinks(db_path) if d["name"] == "Latte")
    custom = {"size": "regular", "milk": "regular", "strength": "regular"}
    ok, _, order_id, total = create_order(user["id"], latte["id"], custom, db_path)
    assert ok and order_id and total > 0
    assert process_payment(order_id, True, db_path)[0]
    receipt = get_receipt(order_id, db_path)
    assert receipt and receipt["payment_status"] == "paid"
    assert save_favorite(user["id"], "My Latte", latte["id"], custom, db_path)[0]
    assert get_favorites(user["id"], db_path)[0]["name"] == "My Latte"

def test_failed_payment_has_no_receipt(db_path):
    """Verify failed payment never generates a paid receipt."""
    user = customer(db_path)
    drink = next(d for d in list_drinks(db_path) if d["name"] == "Espresso")
    ok, _, order_id, _ = create_order(user["id"], drink["id"], {}, db_path)
    assert ok
    assert not process_payment(order_id, False, db_path)[0]
    assert get_receipt(order_id, db_path) is None

def test_order_blocks_when_stock_insufficient(db_path):
    """Verify a recipe cannot be ordered when an ingredient is depleted."""
    user = customer(db_path)
    latte = next(d for d in list_drinks(db_path) if d["name"] == "Latte")
    update_ingredient("milk", 0, 200, db_path=db_path)
    ok, message, order_id, total = create_order(
        user["id"], latte["id"], {"size": "regular"}, db_path
    )
    assert not ok
    assert "Insufficient ingredients" in message
    assert order_id is None and total is None

def test_recommendations_and_natural_language(db_path):
    """Verify recommendations return scores and supported language is parsed."""
    user = customer(db_path)
    assert recommendations(user["id"], db_path)
    config, message = parse_natural_language(
        "Large hot latte with oat milk and an extra shot", db_path
    )
    assert config and config["drink_name"] == "Latte"
    assert config["customization"]["size"] == "large"
    assert config["customization"]["milk"] == "oat"
    assert parse_natural_language("surprise me with a unicorn drink", db_path)[0] is None

def test_events_record_inventory_updates(db_path):
    """Verify inventory changes are visible in the event monitor."""
    update_ingredient("beans", 900, 100, db_path=db_path)
    events = get_events(db_path=db_path)
    assert any("Inventory updated: beans" in event["message"] for event in events)
