from sqlalchemy import Column, Integer, String
from app.database.database import Base

class CPU(Base):
    __tablename__ = "cpus"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    socket = Column(String, nullable=False)
    cores = Column(Integer, default=6)
    tdp = Column(Integer, default=65)
    score = Column(Integer, default=10000)

class GPU(Base):
    __tablename__ = "gpus"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    tdp = Column(Integer, default=150)
    score = Column(Integer, default=15000)
    vram = Column(Integer, default=8)
    target_res = Column(String, default="1080p")

class Motherboard(Base):
    __tablename__ = "motherboards"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    socket = Column(String, nullable=False)
    ram_type = Column(String, default="DDR4")