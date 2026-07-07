from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from database import Base


class CustomerModel(Base):
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True)
    name = Column(String(100))


class MembershipModel(Base):
    __tablename__ = "memberships"

    id = Column(Integer, primary_key=True)
    card_number = Column(String(50), unique=True)
    customer_id = Column(Integer, ForeignKey("customers.id"))  # Ràng buộc khóa ngoại