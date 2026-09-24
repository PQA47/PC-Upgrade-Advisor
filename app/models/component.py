from sqlalchemy import Column, Integer, String, Float
from app.database.database import Base


class CPU(Base):
    __tablename__ = "cpus"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    tdp = Column(Integer, default=65)
    score = Column(Integer, default=0)
    socket = Column(String, default="Other")
    cores = Column(Integer, default=0)
    price = Column(Float, default=0.0)


class GPU(Base):
    __tablename__ = "gpus"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    tdp = Column(Integer, default=0)
    score = Column(Integer, default=0)
    vram = Column(Integer, default=0)
    target_res = Column(String, default="1080p")
    price = Column(Float, default=0.0)


class Motherboard(Base):
    __tablename__ = "motherboards"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    socket = Column(String, default="Other")
    ram_type = Column(String, default="DDR4")
