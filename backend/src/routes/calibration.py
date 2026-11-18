from fastapi import APIRouter,Depends
from src.config.database import get_db
from src.middlewares.auth import current_user,writer
from src.schemas.calibration import CalibrationPublishInput,MergedRunInput
from src.controllers import calibration as ctl
router=APIRouter()
@router.get('/calibrations')
def list_calibrations(db=Depends(get_db),user=Depends(current_user)): return ctl.list_versions(db)
@router.post('/calibrations')
def publish_calibration(data:CalibrationPublishInput,db=Depends(get_db),user=Depends(writer)): return ctl.publish(db,data,user)
@router.get('/calibrations/{version_id}')
def get_calibration(version_id:int,db=Depends(get_db),user=Depends(current_user)): return ctl.get_version(db,version_id)
@router.get('/merged-runs')
def list_merged(db=Depends(get_db),user=Depends(current_user)): return ctl.list_merged(db)
@router.post('/merged-runs')
def create_merged(data:MergedRunInput,db=Depends(get_db),user=Depends(writer)): return ctl.create_merged(db,data,user)
@router.get('/merged-runs/{run_id}')
def get_merged(run_id:int,db=Depends(get_db),user=Depends(current_user)): return ctl.get_merged(db,run_id)
@router.post('/merged-runs/{run_id}/rerun')
def rerun_merged(run_id:int,db=Depends(get_db),user=Depends(writer)): return ctl.rerun_merged(db,run_id,user)
