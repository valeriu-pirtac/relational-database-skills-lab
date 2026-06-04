from sqlalchemy import Column, DateTime, Float, Integer, String
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class SensorData(Base):
    """
    A declarative RANGE partitioned table for time-series data.
    """

    __tablename__ = "sensor_data"
    __table_args__ = {"postgresql_partition_by": "RANGE (timestamp)"}

    # In partitioned tables, the partition key must be part of any unique/primary key constraints.
    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, primary_key=True, nullable=False)
    device_id = Column(String(50), nullable=False)
    temperature = Column(Float, nullable=False)

    def __repr__(self) -> str:
        return (
            f"<SensorData(id={self.id}, device='{self.device_id}', temp={self.temperature}, time='{self.timestamp}')>"
        )
