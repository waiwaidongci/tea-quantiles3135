from sqlalchemy import Column,Integer,String,JSON,Text,ForeignKey
from src.config.database import Base
class MergedDistributionRun(Base):
    __tablename__='merged_runs'
    id=Column(Integer,primary_key=True)
    name=Column(String(120),nullable=False)
    status=Column(String(20),default='queued')
    target_instrument=Column(String(40),nullable=False)
    calibration_version_id=Column(Integer,ForeignKey('calibration_versions.id'),nullable=False)
    parameters=Column(JSON,nullable=False)
    snapshot=Column(JSON,nullable=False)
    checksum=Column(String(64),nullable=False)
    result=Column(JSON,nullable=True)
    error=Column(Text,default='')
    created_at=Column(String(40),nullable=False)
MergedRun=MergedDistributionRun
