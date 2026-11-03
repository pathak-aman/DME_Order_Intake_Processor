"""
Database and Service-level CRUD and Multi-Tenant Isolation Tests.
Tests user creation, order CRUD operations, tenant isolation, and zero-guessing persistence.
"""

from datetime import datetime, timezone
import os
import sys
import unittest

# Ensure api is in sys.path
api_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "api")
if api_dir not in sys.path:
    sys.path.insert(0, api_dir)

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import Order, User
from app.services.validator import validate_and_sanitize_order


class TestDatabaseCRUD(unittest.TestCase):
    """Test suite for Order database models, CRUD operations, and tenant isolation."""

    @classmethod
    def setUpClass(cls):
        """Create an in-memory SQLite database for test isolation."""
        cls.engine = create_engine("sqlite:///:memory:", echo=False)
        Base.metadata.create_all(bind=cls.engine)
        cls.Session = sessionmaker(bind=cls.engine)

    def setUp(self):
        self.db = self.Session()

    def tearDown(self):
        self.db.rollback()
        self.db.close()

    # ─── 1. User & Tenant Isolation Tests ────────────────────────────────────

    def test_user_creation_and_isolation(self):
        """Verify two distinct users have strictly isolated order sets."""
        # Create User A
        user_a = User(email="doctor_a@clinic.org", hashed_password="hashed_secret_a")
        # Create User B
        user_b = User(email="doctor_b@hospital.net", hashed_password="hashed_secret_b")
        self.db.add_all([user_a, user_b])
        self.db.commit()

        # User A creates 2 orders
        order_a1 = Order(
            user_id=user_a.id,
            patient_first_name="Alice",
            patient_last_name="Adams",
            patient_dob="1985-04-12",
            provider_name="Dr. Smith",
            provider_npi="1234567893",
            status="verified",
        )
        order_a2 = Order(
            user_id=user_a.id,
            patient_first_name="Aaron",
            patient_last_name="Aaronson",
            patient_dob="1990-01-01",
            provider_name="Dr. Smith",
            provider_npi="1234567893",
            status="verified",
        )

        # User B creates 1 order
        order_b1 = Order(
            user_id=user_b.id,
            patient_first_name="Bob",
            patient_last_name="Baker",
            patient_dob="1978-09-23",
            provider_name="Dr. Jones",
            provider_npi="1083692859",
            status="verified",
        )

        self.db.add_all([order_a1, order_a2, order_b1])
        self.db.commit()

        # Query orders for User A
        orders_a = self.db.query(Order).filter(Order.user_id == user_a.id).all()
        # Query orders for User B
        orders_b = self.db.query(Order).filter(Order.user_id == user_b.id).all()

        # User A must only see their 2 orders
        self.assertEqual(len(orders_a), 2)
        self.assertTrue(all(o.user_id == user_a.id for o in orders_a))
        self.assertNotIn(order_b1.id, [o.id for o in orders_a])

        # User B must only see their 1 order
        self.assertEqual(len(orders_b), 1)
        self.assertEqual(orders_b[0].id, order_b1.id)
        self.assertEqual(orders_b[0].patient_first_name, "Bob")

    # ─── 2. Order CRUD Operations ────────────────────────────────────────────

    def test_order_lifecycle_crud(self):
        """Test full Create, Read, Update, Delete lifecycle of an Order."""
        user = User(email="intake_nurse@dme.com", hashed_password="pw")
        self.db.add(user)
        self.db.commit()

        # CREATE
        raw_extracted = {
            "patient_first_name": "Eleanor",
            "patient_last_name": "Vance",
            "patient_dob": "05/14/1980",
            "provider_name": "Dr. Marcus Welby, MD",
            "provider_npi": "1234567893",
        }
        sanitized, _ = validate_and_sanitize_order(raw_extracted)

        order = Order(
            user_id=user.id,
            patient_first_name=sanitized["patient_first_name"],
            patient_last_name=sanitized["patient_last_name"],
            patient_dob=sanitized["patient_dob"],
            provider_name=sanitized["provider_name"],
            provider_npi=sanitized["provider_npi"],
            status=sanitized["status"],
        )
        self.db.add(order)
        self.db.commit()
        self.db.refresh(order)

        order_id = order.id
        self.assertIsNotNone(order_id)
        self.assertEqual(order.status, "verified")

        # READ
        fetched = self.db.query(Order).filter(Order.id == order_id).first()
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.patient_first_name, "Eleanor")
        self.assertEqual(fetched.patient_dob, "1980-05-14")

        # UPDATE
        fetched.patient_first_name = "Eleanor-Marie"
        self.db.commit()
        self.db.refresh(fetched)
        self.assertEqual(fetched.patient_first_name, "Eleanor-Marie")

        # DELETE
        self.db.delete(fetched)
        self.db.commit()
        deleted = self.db.query(Order).filter(Order.id == order_id).first()
        self.assertIsNone(deleted)

    # ─── 3. Zero-Guessing Policy Persistence Tests ───────────────────────────

    def test_missing_fields_persisted_strictly_as_none(self):
        """Verify that when PDF is missing fields, they are stored as NULL/None in DB."""
        user = User(email="test_zero_guess@dme.com", hashed_password="pw")
        self.db.add(user)
        self.db.commit()

        # Simulate extracted messy fax where NPI and DOB could not be found
        messy_extracted = {
            "patient_first_name": "Samuel",
            "patient_last_name": "Jackson",
            "patient_dob": None,  # Not found
            "provider_name": "Dr. Nick",
            "provider_npi": "N/A",  # Not provided
        }
        sanitized, issues = validate_and_sanitize_order(messy_extracted)

        order = Order(
            user_id=user.id,
            patient_first_name=sanitized["patient_first_name"],
            patient_last_name=sanitized["patient_last_name"],
            patient_dob=sanitized["patient_dob"],
            provider_name=sanitized["provider_name"],
            provider_npi=sanitized["provider_npi"],
            status=sanitized["status"],
        )
        self.db.add(order)
        self.db.commit()
        self.db.refresh(order)

        # Status must be needs_review
        self.assertEqual(order.status, "needs_review")
        # Missing values must be strictly None (NULL in SQL), NEVER guessed or placeholder
        self.assertIsNone(order.patient_dob)
        self.assertIsNone(order.provider_npi)
        # Present values preserved
        self.assertEqual(order.patient_first_name, "Samuel")
        self.assertEqual(order.patient_last_name, "Jackson")


if __name__ == "__main__":
    unittest.main()

