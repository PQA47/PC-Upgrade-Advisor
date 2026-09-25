from datetime import datetime

from sqlalchemy import Column, DateTime, Float, Integer, String, Text

from app.database.database import Base


class Analysis(Base):
    __tablename__ = "analyses"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)

    cpu_name = Column(String(255), nullable=False)
    gpu_name = Column(String(255), nullable=False)
    motherboard_name = Column(String(255), nullable=False)

    ram_gb = Column(Integer, nullable=False)
    storage_type = Column(String(100), nullable=False)
    resolution = Column(String(50), nullable=False)
    usage = Column(String(100), nullable=False)
    psu_watt = Column(Integer, nullable=False)
    budget = Column(Float, default=0.0, nullable=False)
    result_json = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
