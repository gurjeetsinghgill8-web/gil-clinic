"""GIL AI Wallet — owner-owned prepaid AI credits (Phase 1 blueprint).

Puter primary rehta hai; ye mode sasta backup hai:
- clinic UPI se recharge karti hai (manual UTR approval — Rasta A)
- har AI call par feature-price x margin kaat liya jata hai
- ledger (ai_wallet_txns) mein har entry record
"""
from sqlalchemy import BigInteger, Column, DateTime, Integer, String, func

from src.shared.infrastructure.database import Base


class AIWalletModel(Base):
    __tablename__ = "ai_wallets"

    clinic_id = Column(String(36), primary_key=True)
    balance_paise = Column(BigInteger, default=0, nullable=False)
    total_recharged_paise = Column(BigInteger, default=0, nullable=False)
    total_spent_paise = Column(BigInteger, default=0, nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class AIRechargeModel(Base):
    __tablename__ = "ai_recharges"

    id = Column(Integer, primary_key=True, autoincrement=True)
    clinic_id = Column(String(36), nullable=False, index=True)
    amount_paise = Column(BigInteger, nullable=False)
    utr = Column(String(64), default="")
    status = Column(String(16), default="pending")  # pending / approved / rejected
    created_at = Column(DateTime, default=func.now())


class AIWalletTxnModel(Base):
    __tablename__ = "ai_wallet_txns"

    id = Column(Integer, primary_key=True, autoincrement=True)
    clinic_id = Column(String(36), nullable=False, index=True)
    delta_paise = Column(BigInteger, nullable=False)  # + credit / - debit
    reason = Column(String(200), default="")
    created_at = Column(DateTime, default=func.now())
