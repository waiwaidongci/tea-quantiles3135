from sqlalchemy import Column,Integer,String,Float,ForeignKey
from src.config.database import Base
class CalibrationVersion(Base):
    __tablename__='calibration_versions'
    id=Column(Integer,primary_key=True)
    note=Column(String(500),default='')
    author=Column(String(120),nullable=False)
    checksum=Column(String(64),nullable=False)
    created_at=Column(String(40),nullable=False)
class CalibrationEntry(Base):
    __tablename__='calibration_entries'
    id=Column(Integer,primary_key=True)
    version_id=Column(Integer,ForeignKey('calibration_versions.id'),nullable=False)
    from_instrument=Column(String(40),nullable=False)
    to_instrument=Column(String(40),nullable=False)
    slope=Column(Float,nullable=False)
    intercept=Column(Float,nullable=False)
    lo=Column(Float,nullable=False)
    hi=Column(Float,nullable=False)
