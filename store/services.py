import requests
import logging

logger = logging.getLogger(__name__)

# Docker service network hostnames
CURRENCY_SERVICE_URL = "http://currency_service:5001/api/convert"
FIREBASE_SERVICE_URL = "http://firebase_service:5002/api/log-order"

def convert_php_to_usd(php_amount: float) -> dict:
    """Calls the Currency Converter Microservice."""
    try:
        response = requests.get(
            CURRENCY_SERVICE_URL,
            params={"amount": php_amount},
            timeout=5
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Currency conversion microservice error: {e}")
        # Fallback approximation if service is unreachable
        return {
            "status": "FALLBACK",
            "original_php": php_amount,
            "usd_amount": round(php_amount / 56.0, 2),
            "exchange_rate": 0.0178
        }

def log_order_to_firebase(order_id: str, customer_name: str, php_total: float, usd_paid: float) -> dict:
    """Calls the Firebase Cloud DB Microservice."""
    payload = {
        "order_id": str(order_id),
        "customer": customer_name,
        "php_total": float(php_total),
        "usd_paid": float(usd_paid)
    }
    try:
        response = requests.post(
            FIREBASE_SERVICE_URL,
            json=payload,
            timeout=5
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Firebase logging microservice error: {e}")
        return {"status": "ERROR", "message": str(e)}

def send_email_receipt(email, order_id, total):
    try:
        payload = {
            "customer_email": email,
            "order_id": order_id,
            "total_amount": total
        }
       
        response = requests.post("http://email_service:5004/api/send-receipt", json=payload, timeout=5)
        return response.json()
    except Exception as e:
        return {"status": "ERROR", "message": str(e)}

def get_product_recommendations():
    try:
        response = requests.get("http://recommendation_service:5005/api/recommendations", timeout=5)
        if response.status_code == 200:
            return response.json()
        return []
    except Exception as e:
        print(f"Recommendation Error: {e}")
        return []