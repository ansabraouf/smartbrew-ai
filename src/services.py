"""SmartBrew application services: menu, orders, inventory, payments and personalization."""

from __future__ import annotations
import json
import secrets
import sqlite3
from typing import Any
from src.database import connection
from src.security import hash_password, verify_password

def log_event(actor: str, severity: str, message: str, db_path="smartbrew.db") -> None:
    """Record an operational event.

    Args:
        actor: Username or subsystem producing the event.
        severity: Event severity such as INFO, WARNING, or ERROR.
        message: Human-readable event description.
        db_path: Optional database path.

    Returns:
        None.
    """
    with connection(db_path) as conn:
        conn.execute("INSERT INTO events(actor,severity,message) VALUES(?,?,?)",
                     (actor, severity.upper(), message))

def register_user(username: str, password: str, db_path="smartbrew.db") -> tuple[bool, str]:
    """Create a customer account after basic input validation.

    Args:
        username: Unique username.
        password: Password to hash and store.
        db_path: Optional database path.

    Returns:
        Success flag and a user-facing result message.
    """
    username = username.strip()
    if len(username) < 3 or len(password) < 8:
        return False, "Username must be at least 3 characters and password at least 8 characters."
    try:
        with connection(db_path) as conn:
            conn.execute("INSERT INTO users(username,password_hash,role) VALUES(?,?,?)",
                         (username, hash_password(password), "customer"))
        return True, "Account created. You can now sign in."
    except sqlite3.IntegrityError:
        return False, "That username is already in use."

def authenticate(username: str, password: str, db_path="smartbrew.db") -> dict[str, Any] | None:
    """Authenticate a user by username and password.

    Args:
        username: Account username.
        password: Candidate password.
        db_path: Optional database path.

    Returns:
        User dictionary without password hash, or None for invalid credentials.
    """
    with connection(db_path) as conn:
        row = conn.execute("SELECT * FROM users WHERE username=?", (username.strip(),)).fetchone()
    if row and verify_password(password, row["password_hash"]):
        return {"id": row["id"], "username": row["username"], "role": row["role"],
                "preferences": json.loads(row["preferences"])}
    return None

def list_drinks(db_path="smartbrew.db") -> list[dict[str, Any]]:
    """Return all menu drinks with parsed recipe definitions.

    Args:
        db_path: Optional database path.

    Returns:
        List of drink dictionaries.
    """
    with connection(db_path) as conn:
        rows = conn.execute("SELECT * FROM drinks ORDER BY category,name").fetchall()
    result = []
    for row in rows:
        item = dict(row)
        item["recipe"] = json.loads(item["recipe"])
        result.append(item)
    return result

def get_inventory(db_path="smartbrew.db") -> list[dict[str, Any]]:
    """Read ingredient stock and compute low-stock status.

    Args:
        db_path: Optional database path.

    Returns:
        Ingredient records with a low_stock boolean.
    """
    with connection(db_path) as conn:
        rows = conn.execute("SELECT * FROM ingredients ORDER BY name").fetchall()
    return [{**dict(row), "low_stock": row["quantity"] <= row["minimum"]} for row in rows]

def update_ingredient(name: str, quantity: float, minimum: float | None = None,
                      actor="admin", db_path="smartbrew.db") -> tuple[bool, str]:
    """Set an ingredient quantity and optionally update its warning threshold.

    Args:
        name: Existing ingredient name.
        quantity: New non-negative quantity.
        minimum: Optional non-negative low-stock threshold.
        actor: Authenticated administrator username.
        db_path: Optional database path.

    Returns:
        Success flag and result message.
    """
    if quantity < 0 or (minimum is not None and minimum < 0):
        return False, "Quantities and thresholds cannot be negative."
    with connection(db_path) as conn:
        row = conn.execute("SELECT * FROM ingredients WHERE name=?", (name,)).fetchone()
        if not row:
            return False, f"Unknown ingredient: {name}"
        if minimum is None:
            conn.execute("UPDATE ingredients SET quantity=? WHERE name=?", (quantity, name))
        else:
            conn.execute("UPDATE ingredients SET quantity=?, minimum=? WHERE name=?",
                         (quantity, minimum, name))
    level = "WARNING" if minimum is not None and quantity <= minimum else "INFO"
    log_event(actor, level, f"Inventory updated: {name} = {quantity}", db_path)
    return True, f"Updated {name} stock to {quantity:g} {row['unit']}."

def recipe_availability(recipe: dict[str, float], db_path="smartbrew.db") -> tuple[bool, list[str]]:
    """Check whether all recipe ingredients have sufficient stock.

    Args:
        recipe: Ingredient names mapped to quantities needed.
        db_path: Optional database path.

    Returns:
        Availability flag and list of missing/insufficient ingredients.
    """
    with connection(db_path) as conn:
        rows = conn.execute("SELECT name,quantity FROM ingredients").fetchall()
    stock = {r["name"]: r["quantity"] for r in rows}
    missing = [f"{name} (need {qty:g}, have {stock.get(name, 0):g})"
               for name, qty in recipe.items() if stock.get(name, 0) < qty]
    return not missing, missing

def update_preferences(user_id: int, preferences: dict[str, Any], db_path="smartbrew.db") -> None:
    """Persist a customer's recommendation preferences.

    Args:
        user_id: Customer account ID.
        preferences: JSON-serializable preference dictionary.
        db_path: Optional database path.

    Returns:
        None.
    """
    with connection(db_path) as conn:
        conn.execute("UPDATE users SET preferences=? WHERE id=?",
                     (json.dumps(preferences), user_id))

def recommendations(user_id: int, db_path="smartbrew.db") -> list[dict[str, Any]]:
    """Rank drinks using preferences and historical paid orders.

    Args:
        user_id: Customer account ID.
        db_path: Optional database path.

    Returns:
        Drinks sorted by recommendation score, with score attached.
    """
    with connection(db_path) as conn:
        user = conn.execute("SELECT preferences FROM users WHERE id=?", (user_id,)).fetchone()
        history = conn.execute(
            "SELECT drink_name, COUNT(*) AS n FROM orders WHERE user_id=? AND payment_status='paid' GROUP BY drink_name",
            (user_id,)
        ).fetchall()
    prefs = json.loads(user["preferences"]) if user else {}
    history_counts = {r["drink_name"]: r["n"] for r in history}
    drinks = list_drinks(db_path)
    for drink in drinks:
        score = 0
        if prefs.get("category") == drink["category"]:
            score += 5
        if prefs.get("milk") and "milk" in drink["recipe"]:
            score += 2
        score += history_counts.get(drink["name"], 0) * 3
        drink["score"] = score
    return sorted(drinks, key=lambda d: (-d["score"], d["name"]))

def parse_natural_language(request: str, db_path="smartbrew.db") -> tuple[dict[str, Any] | None, str]:
    """Translate a limited supported natural-language request into drink options.

    Args:
        request: Customer's free-form drink request.
        db_path: Optional database path.

    Returns:
        Parsed configuration and explanation, or None and a clarification message.
    """
    text = request.lower()
    drinks = list_drinks(db_path)
    matched = next((d for d in drinks if d["name"].lower() in text), None)
    if not matched:
        aliases = {"coffee": "Americano", "chocolate": "Hot Chocolate", "latte": "Latte",
                   "mocha": "Mocha", "espresso": "Espresso", "cappuccino": "Cappuccino"}
        matched_name = next((v for k, v in aliases.items() if k in text), None)
        matched = next((d for d in drinks if d["name"] == matched_name), None)
    if not matched:
        return None, "I couldn't identify a supported drink. Try latte, cappuccino, mocha, espresso, Americano, or hot chocolate."
    custom = {"size": "large" if "large" in text else "regular",
              "temperature": "iced" if "iced" in text or "cold" in text else "hot",
              "milk": "oat" if "oat milk" in text else ("almond" if "almond milk" in text else "regular"),
              "strength": "extra" if "extra shot" in text or "strong" in text or "kick" in text else "regular",
              "sugar": "low" if "little sugar" in text or "low sugar" in text or "less sugar" in text else "regular"}
    return {"drink_id": matched["id"], "drink_name": matched["name"], "customization": custom,
            "base_price": matched["price"]}, f"Interpreted as {matched['name']}. Please review before ordering."

def create_order(user_id: int, drink_id: int, customization: dict[str, Any],
                 db_path="smartbrew.db") -> tuple[bool, str, int | None, float | None]:
    """Validate stock and create an unpaid order while deducting stock atomically.

    Args:
        user_id: Customer account ID.
        drink_id: Selected menu drink ID.
        customization: Validated customer options.
        db_path: Optional database path.

    Returns:
        Success flag, message, order ID if created, and calculated total.
    """
    with connection(db_path) as conn:
        drink = conn.execute("SELECT * FROM drinks WHERE id=?", (drink_id,)).fetchone()
        if not drink:
            return False, "Drink not found.", None, None
        recipe = json.loads(drink["recipe"])
        # Apply simple size multiplier to recipe quantities and price.
        size = customization.get("size", "regular")
        multiplier = 1.4 if size == "large" else (0.75 if size == "small" else 1.0)
        recipe = {k: v * multiplier for k, v in recipe.items()}
        stock_rows = conn.execute("SELECT name,quantity FROM ingredients").fetchall()
        stock = {r["name"]: r["quantity"] for r in stock_rows}
        missing = [f"{k} (need {v:g}, have {stock.get(k, 0):g})"
                   for k, v in recipe.items() if stock.get(k, 0) < v]
        if missing:
            return False, "Insufficient ingredients: " + ", ".join(missing), None, None
        price = float(drink["price"]) * multiplier
        if customization.get("strength") == "extra":
            price += 0.75
        if customization.get("milk") in ("oat", "almond"):
            price += 0.50
        for ingredient, qty in recipe.items():
            conn.execute("UPDATE ingredients SET quantity=quantity-? WHERE name=?", (qty, ingredient))
        cursor = conn.execute(
            "INSERT INTO orders(user_id,drink_id,drink_name,customization,total,status,payment_status) VALUES(?,?,?,?,?,?,?)",
            (user_id, drink_id, drink["name"], json.dumps(customization), round(price, 2), "submitted", "pending")
        )
        order_id = cursor.lastrowid
        conn.execute("INSERT INTO events(actor,severity,message) VALUES(?,?,?)",
                     ("ordering", "INFO", f"Order #{order_id} submitted"))
    return True, f"Order #{order_id} created. Complete payment to finalize.", order_id, round(price, 2)

def process_payment(order_id: int, success: bool, db_path="smartbrew.db") -> tuple[bool, str]:
    """Simulate payment confirmation or failure for a pending order.

    Args:
        order_id: Order being paid.
        success: Whether the simulated payment should succeed.
        db_path: Optional database path.

    Returns:
        Success flag and outcome message.
    """
    with connection(db_path) as conn:
        order = conn.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
        if not order:
            return False, "Order not found."
        if order["payment_status"] != "pending":
            return False, "This order has already had a payment outcome recorded."
        if success:
            conn.execute("UPDATE orders SET payment_status='paid',status='confirmed' WHERE id=?", (order_id,))
            code = secrets.token_urlsafe(8).upper()
            conn.execute("INSERT INTO receipts(order_id,receipt_code) VALUES(?,?)", (order_id, code))
            conn.execute("INSERT INTO events(actor,severity,message) VALUES(?,?,?)",
                         ("payment", "INFO", f"Payment succeeded for order #{order_id}"))
        else:
            conn.execute("UPDATE orders SET payment_status='failed',status='payment_failed' WHERE id=?", (order_id,))
            conn.execute("INSERT INTO events(actor,severity,message) VALUES(?,?,?)",
                         ("payment", "WARNING", f"Payment failed for order #{order_id}"))
    return (True, "Payment successful. Receipt generated.") if success else (False, "Payment failed; order is not marked paid.")

def get_receipt(order_id: int, db_path="smartbrew.db") -> dict[str, Any] | None:
    """Retrieve receipt details for a paid order.

    Args:
        order_id: Order ID.
        db_path: Optional database path.

    Returns:
        Receipt and order details, or None if no receipt exists.
    """
    with connection(db_path) as conn:
        row = conn.execute("""
        SELECT r.receipt_code,r.created_at AS receipt_time,o.id AS order_id,o.drink_name,
               o.customization,o.total,o.payment_status,o.created_at AS order_time,u.username
        FROM receipts r JOIN orders o ON o.id=r.order_id JOIN users u ON u.id=o.user_id
        WHERE o.id=? AND o.payment_status='paid'
        """, (order_id,)).fetchone()
    if not row:
        return None
    result = dict(row)
    result["customization"] = json.loads(result["customization"])
    return result

def save_favorite(user_id: int, name: str, drink_id: int, customization: dict[str, Any],
                  db_path="smartbrew.db") -> tuple[bool, str]:
    """Save a named recipe for a customer.

    Args:
        user_id: Customer account ID.
        name: User-defined favorite name.
        drink_id: Base drink ID.
        customization: Recipe options to retain.
        db_path: Optional database path.

    Returns:
        Success flag and user-facing message.
    """
    if not name.strip():
        return False, "Favorite name cannot be empty."
    try:
        with connection(db_path) as conn:
            conn.execute("INSERT INTO favorites(user_id,name,drink_id,customization) VALUES(?,?,?,?)",
                         (user_id, name.strip(), drink_id, json.dumps(customization)))
        return True, "Favorite saved."
    except sqlite3.IntegrityError:
        return False, "A favorite with that name already exists."

def get_favorites(user_id: int, db_path="smartbrew.db") -> list[dict[str, Any]]:
    """List a customer's saved recipes.

    Args:
        user_id: Customer account ID.
        db_path: Optional database path.

    Returns:
        Favorite records with decoded customization.
    """
    with connection(db_path) as conn:
        rows = conn.execute("""
        SELECT f.id,f.name,f.drink_id,f.customization,d.name AS drink_name
        FROM favorites f JOIN drinks d ON d.id=f.drink_id WHERE f.user_id=? ORDER BY f.name
        """, (user_id,)).fetchall()
    result = [dict(row) for row in rows]
    for item in result:
        item["customization"] = json.loads(item["customization"])
    return result

def get_events(limit: int = 100, db_path="smartbrew.db") -> list[dict[str, Any]]:
    """Return recent operational events.

    Args:
        limit: Maximum number of events to return.
        db_path: Optional database path.

    Returns:
        Event records ordered newest first.
    """
    with connection(db_path) as conn:
        rows = conn.execute("SELECT * FROM events ORDER BY id DESC LIMIT ?", (max(1, min(limit, 1000)),)).fetchall()
    return [dict(row) for row in rows]
