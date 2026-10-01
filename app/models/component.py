<<<<<<< HEAD
from sqlalchemy import Column, Integer, String, Float, DateTime
=======
from sqlalchemy import Column, Integer, String, Float
>>>>>>> c984055 (feat(frontend): complete UI for auth, results, index and history)
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
<<<<<<< HEAD
    price_source = Column(String, nullable=True)
    price_updated_at = Column(DateTime, nullable=True)
=======
>>>>>>> c984055 (feat(frontend): complete UI for auth, results, index and history)


class GPU(Base):
    __tablename__ = "gpus"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    tdp = Column(Integer, default=0)
    score = Column(Integer, default=0)
    vram = Column(Integer, default=0)
    target_res = Column(String, default="1080p")
    price = Column(Float, default=0.0)
<<<<<<< HEAD
    price_source = Column(String, nullable=True)
    price_updated_at = Column(DateTime, nullable=True)
=======
>>>>>>> c984055 (feat(frontend): complete UI for auth, results, index and history)


class Motherboard(Base):
    __tablename__ = "motherboards"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    socket = Column(String, default="Other")
    ram_type = Column(String, default="DDR4")
