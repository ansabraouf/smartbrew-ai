"""SQLite persistence helpers for SmartBrew AI."""

from __future__ import annotations
import sqlite3
import json
from pathlib import Path
from contextlib import contextmanager

DEFAULT_DB = Path(__file__).resolve().parent.parent / "smartbrew.db"

@contextmanager
def connection(db_path: str | Path = DEFAULT_DB):
    """Open a SQLite connection and ensure it is closed.

    Args:
        db_path: Filesystem path to the SQLite database.

    Yields:
        A configured SQLite connection with row access by column name.
    """
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def initialize_database(db_path: str | Path = DEFAULT_DB) -> None:
    """Create required tables and seed demo data if the database is empty.

    Args:
        db_path: Filesystem path to the SQLite database.

    Returns:
        None.
    """
    with connection(db_path) as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'customer',
            preferences TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS ingredients (
            name TEXT PRIMARY KEY,
            quantity REAL NOT NULL CHECK(quantity >= 0),
            minimum REAL NOT NULL DEFAULT 5 CHECK(minimum >= 0),
            unit TEXT NOT NULL DEFAULT 'g'
        );
        CREATE TABLE IF NOT EXISTS drinks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            category TEXT NOT NULL,
            description TEXT NOT NULL,
            price REAL NOT NULL CHECK(price >= 0),
            calories INTEGER NOT NULL DEFAULT 0,
            recipe TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id),
            drink_id INTEGER NOT NULL REFERENCES drinks(id),
            drink_name TEXT NOT NULL,
            customization TEXT NOT NULL,
            total REAL NOT NULL,
            status TEXT NOT NULL,
            payment_status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS favorites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id),
            name TEXT NOT NULL,
            drink_id INTEGER NOT NULL REFERENCES drinks(id),
            customization TEXT NOT NULL,
            UNIQUE(user_id, name)
        );
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            actor TEXT NOT NULL,
            severity TEXT NOT NULL,
            message TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS receipts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER UNIQUE NOT NULL REFERENCES orders(id),
            receipt_code TEXT UNIQUE NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """)
        count = conn.execute("SELECT COUNT(*) FROM drinks").fetchone()[0]
        if count == 0:
            drinks = [
                ("Espresso", "Coffee", "Short, intense coffee.", 2.50, 5,
                 {"beans": 18, "water": 30}),
                ("Americano", "Coffee", "Espresso softened with hot water.", 3.00, 10,
                 {"beans": 18, "water": 180}),
                ("Cappuccino", "Milk Coffee", "Espresso with steamed milk foam.", 3.75, 110,
                 {"beans": 18, "milk": 120, "water": 30}),
                ("Latte", "Milk Coffee", "Smooth espresso with milk.", 4.00, 150,
                 {"beans": 18, "milk": 180, "water": 30}),
                ("Mocha", "Specialty", "Coffee, milk and cocoa.", 4.50, 220,
                 {"beans": 18, "milk": 150, "cocoa": 15, "water": 30}),
                ("Hot Chocolate", "Non-Coffee", "Chocolate drink with milk.", 3.50, 240,
                 {"milk": 200, "cocoa": 25}),
            ]
            for name, category, desc, price, calories, recipe in drinks:
                conn.execute(
                    "INSERT INTO drinks(name,category,description,price,calories,recipe) VALUES(?,?,?,?,?,?)",
                    (name, category, desc, price, calories, json.dumps(recipe))
                )
        seed_ingredients = [
            ("beans", 1000, 100, "g"), ("milk", 2000, 200, "ml"),
            ("water", 5000, 500, "ml"), ("cocoa", 500, 50, "g"),
            ("cups", 100, 10, "pcs"), ("syrup", 300, 30, "ml"),
        ]
        for row in seed_ingredients:
            conn.execute(
                "INSERT OR IGNORE INTO ingredients(name,quantity,minimum,unit) VALUES(?,?,?,?)", row
            )
        # Demo accounts use documented passwords and must be changed for real deployment.
        from src.security import hash_password
        conn.execute(
            "INSERT OR IGNORE INTO users(username,password_hash,role) VALUES(?,?,?)",
            ("customer", hash_password("BrewDemo123!"), "customer")
        )
        conn.execute(
            "INSERT OR IGNORE INTO users(username,password_hash,role) VALUES(?,?,?)",
            ("admin", hash_password("AdminDemo123!"), "admin")
        )
