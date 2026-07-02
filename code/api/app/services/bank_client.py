"""Generic banking client wrapper.

Simulates fetching from a generic external banking REST API.
This is meant to be stubbed or replaced with a real provider (like Plaid) later.
"""
from typing import Any

class BankError(Exception):
    pass

def fetch_transactions(api_key: str, since_iso: str | None = None) -> list[dict[str, Any]]:
    """Fetch recent transactions from the bank.
    
    Returns a list of dicts with:
      - transaction_id (str)
      - date (ISO format string)
      - amount (float)
      - merchant (str)
      - category (str)
    """
    if not api_key:
        raise BankError("Missing API key")
        
    # In a real implementation, we would hit a provider's API.
    # For now, if the API key is "mock_key", return dummy data, else return empty.
    if api_key == "mock_key":
        return [
            {
                "transaction_id": "txn_mock_1",
                "date": "2026-07-02T10:00:00Z",
                "amount": -5.50,
                "merchant": "Coffee Shop",
                "category": "Food & Drink"
            },
            {
                "transaction_id": "txn_mock_2",
                "date": "2026-07-01T15:30:00Z",
                "amount": -100.00,
                "merchant": "Grocery Store",
                "category": "Groceries"
            }
        ]
        
    return []
