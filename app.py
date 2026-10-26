"""Streamlit graphical interface for the SmartBrew AI prototype."""

import json
import streamlit as st
from src.database import initialize_database
from src.services import (
    authenticate, register_user, list_drinks, get_inventory, update_ingredient,
    recipe_availability, update_preferences, recommendations, parse_natural_language,
    create_order, process_payment, get_receipt, save_favorite, get_favorites, get_events
)

st.set_page_config(page_title="SmartBrew AI", page_icon="☕", layout="wide")
initialize_database()

def init_state():
    """Initialize session-state keys used by the user interface.

    Args:
        None.

    Returns:
        None.
    """
    defaults = {"user": None, "pending_order": None, "last_receipt": None, "nl_config": None}
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

init_state()

st.title("☕ SmartBrew AI")
st.caption("Personalized coffee ordering prototype · simulated payments · local demo data")

if st.session_state.user is None:
    tab_login, tab_register = st.tabs(["Sign in", "Create account"])
    with tab_login:
        st.info("Demo customer: `customer` / `BrewDemo123!` · Admin: `admin` / `AdminDemo123!`")
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Sign in", use_container_width=True)
        if submitted:
            user = authenticate(username, password)
            if user:
                st.session_state.user = user
                st.rerun()
            else:
                st.error("Invalid username or password.")
    with tab_register:
        with st.form("register_form"):
            new_username = st.text_input("Choose username")
            new_password = st.text_input("Choose password (at least 8 characters)", type="password")
            create = st.form_submit_button("Create customer account", use_container_width=True)
        if create:
            ok, message = register_user(new_username, new_password)
            (st.success if ok else st.error)(message)
    st.stop()

user = st.session_state.user
with st.sidebar:
    st.write(f"Signed in as **{user['username']}**")
    st.write(f"Role: `{user['role']}`")
    if st.button("Sign out", use_container_width=True):
        st.session_state.user = None
        st.session_state.pending_order = None
        st.rerun()
    page = st.radio("Navigate", [
        "Menu & customize", "Recommendations", "Natural-language order",
        "Favorites", "Checkout & receipt", "Admin inventory & events"
    ])

if page == "Menu & customize":
    st.header("Browse beverages")
    drinks = list_drinks()
    categories = ["All"] + sorted({d["category"] for d in drinks})
    category = st.selectbox("Category", categories)
    shown = [d for d in drinks if category == "All" or d["category"] == category]
    cols = st.columns(3)
    for i, drink in enumerate(shown):
        with cols[i % 3]:
            st.subheader(drink["name"])
            st.caption(drink["category"])
            st.write(drink["description"])
            st.write(f"**€{drink['price']:.2f}** · {drink['calories']} kcal")
            ok, missing = recipe_availability(drink["recipe"])
            st.write("🟢 Ingredients available" if ok else "🔴 " + ", ".join(missing))
    st.divider()
    st.subheader("Customize and order")
    options = {d["name"]: d for d in drinks}
    selected_name = st.selectbox("Choose a beverage", list(options))
    selected = options[selected_name]
    with st.form("customize_form"):
        size = st.selectbox("Size", ["small", "regular", "large"], index=1)
        milk = st.selectbox("Milk", ["regular", "oat", "almond", "none"])
        strength = st.selectbox("Coffee strength", ["regular", "extra"])
        temperature = st.selectbox("Temperature", ["hot", "iced"])
        sugar = st.selectbox("Sugar", ["regular", "low", "none"])
        syrup = st.selectbox("Syrup shots", [0, 1, 2, 3])
        save_as = st.text_input("Optional favorite name")
        submit_order = st.form_submit_button("Validate and create order", use_container_width=True)
    if submit_order:
        custom = {"size": size, "milk": milk, "strength": strength, "temperature": temperature,
                  "sugar": sugar, "syrup_shots": syrup}
        ok, missing = recipe_availability(selected["recipe"])
        if not ok:
            st.error("Cannot order: " + ", ".join(missing))
        else:
            success, message, order_id, total = create_order(user["id"], selected["id"], custom)
            if success:
                st.session_state.pending_order = {"id": order_id, "total": total, "drink_id": selected["id"],
                                                  "customization": custom, "name": selected["name"]}
                st.success(message)
                if save_as.strip():
                    saved, msg = save_favorite(user["id"], save_as, selected["id"], custom)
                    (st.success if saved else st.warning)(msg)
                st.info(f"Amount due: €{total:.2f}. Continue to Checkout & receipt.")
            else:
                st.error(message)

elif page == "Recommendations":
    st.header("Personalized recommendations")
    drinks = list_drinks()
    current = user.get("preferences", {})
    with st.form("preferences"):
        category = st.selectbox("Preferred category", ["Any"] + sorted({d["category"] for d in drinks}),
                                index=(["Any"] + sorted({d["category"] for d in drinks})).index(current.get("category", "Any"))
                                if current.get("category", "Any") in ["Any"] + sorted({d["category"] for d in drinks}) else 0)
        milk = st.checkbox("I like milk-based drinks", value=bool(current.get("milk")))
        save = st.form_submit_button("Save preferences")
    if save:
        prefs = {"category": None if category == "Any" else category, "milk": milk}
        update_preferences(user["id"], prefs)
        user["preferences"] = prefs
        st.success("Preferences saved.")
    for drink in recommendations(user["id"])[:5]:
        st.write(f"**{drink['name']}** — €{drink['price']:.2f} · recommendation score {drink['score']}")
        st.caption(drink["description"])

elif page == "Natural-language order":
    st.header("Describe your drink")
    st.write('Example: "Large hot latte with oat milk and an extra shot"')
    request = st.text_input("What would you like?")
    if st.button("Interpret request"):
        config, message = parse_natural_language(request)
        st.session_state.nl_config = config
        (st.success if config else st.warning)(message)
    if st.session_state.nl_config:
        config = st.session_state.nl_config
        st.json(config["customization"])
        st.write(f"**{config['drink_name']}** · base €{config['base_price']:.2f}")
        if st.button("Confirm interpreted order"):
            ok, message, order_id, total = create_order(
                user["id"], config["drink_id"], config["customization"]
            )
            if ok:
                st.session_state.pending_order = {"id": order_id, "total": total,
                    "drink_id": config["drink_id"], "customization": config["customization"],
                    "name": config["drink_name"]}
                st.success(message + f" Amount due: €{total:.2f}")
            else:
                st.error(message)

elif page == "Favorites":
    st.header("Saved beverage recipes")
    favorites = get_favorites(user["id"])
    if not favorites:
        st.info("No favorites yet. Save a recipe from Menu & customize.")
    for favorite in favorites:
        with st.expander(f"{favorite['name']} — {favorite['drink_name']}"):
            st.json(favorite["customization"])
            if st.button("Load as pending order", key=f"fav_{favorite['id']}"):
                st.session_state.pending_order = {
                    "id": None, "total": None, "drink_id": favorite["drink_id"],
                    "customization": favorite["customization"], "name": favorite["drink_name"],
                    "favorite_name": favorite["name"]
                }
                st.info("Recipe loaded. Open Menu & customize to submit a fresh order.")

elif page == "Checkout & receipt":
    st.header("Checkout & digital receipt")
    pending = st.session_state.pending_order
    if pending and pending.get("id"):
        st.write(f"Order **#{pending['id']}** · {pending['name']} · **€{pending['total']:.2f}**")
        st.json(pending["customization"])
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Simulate successful payment", use_container_width=True):
                ok, message = process_payment(pending["id"], True)
                if ok:
                    st.success(message)
                    st.session_state.last_receipt = get_receipt(pending["id"])
                else:
                    st.error(message)
        with col2:
            if st.button("Simulate failed payment", use_container_width=True):
                ok, message = process_payment(pending["id"], False)
                st.warning(message)
        if st.session_state.last_receipt:
            receipt = st.session_state.last_receipt
            st.subheader("Digital receipt")
            st.write(f"Receipt code: `{receipt['receipt_code']}`")
            st.write(f"Order #{receipt['order_id']} · {receipt['drink_name']} · €{receipt['total']:.2f}")
            st.write(f"Customer: {receipt['username']} · Paid: {receipt['payment_status']}")
            st.json(receipt["customization"])
            st.download_button("Download receipt JSON", json.dumps(receipt, indent=2), "smartbrew_receipt.json", "application/json")
    elif pending and pending.get("drink_id"):
        st.info("A saved recipe is loaded. Submit it from Menu & customize to create a new order.")
    else:
        st.info("Create an order from Menu & customize or Natural-language order first.")
    st.caption("Payments are simulated. No real card or wallet is charged.")

elif page == "Admin inventory & events":
    if user["role"] != "admin":
        st.error("Administrator access required. Sign out and sign in with the admin demo account.")
        st.stop()
    st.header("Admin: inventory and event monitoring")
    inventory = get_inventory()
    st.dataframe(inventory, use_container_width=True, hide_index=True)
    with st.form("stock_update"):
        names = [i["name"] for i in inventory]
        ingredient = st.selectbox("Ingredient", names)
        quantity = st.number_input("New stock quantity", min_value=0.0, value=100.0, step=10.0)
        minimum = st.number_input("Low-stock threshold", min_value=0.0, value=10.0, step=5.0)
        update = st.form_submit_button("Update inventory")
    if update:
        ok, message = update_ingredient(ingredient, quantity, minimum, actor=user["username"])
        (st.success if ok else st.error)(message)
        st.rerun()
    st.subheader("Recent system events")
    st.dataframe(get_events(), use_container_width=True, hide_index=True)
