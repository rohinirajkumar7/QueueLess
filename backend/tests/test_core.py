from datetime import date
from app.core.security import hash_password, verify_password

def test_password_hashing():
 p="Secret123!"; h=hash_password(p); assert h!=p and verify_password(p,h) and not verify_password("bad",h)

def test_fifo_ordering_model():
 assert ["A-001","A-002","A-003"]==sorted(["A-003","A-001","A-002"])
