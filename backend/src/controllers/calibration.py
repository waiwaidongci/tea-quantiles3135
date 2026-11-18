from src.services import calibration,merged
# Controllers keep endpoint contracts separate from persistence and calculation.
def publish(db,data,user): return calibration.publish(db,data,user)
def list_versions(db): return calibration.list_versions(db)
def get_version(db,id): return calibration.get_version(db,id)
def create_merged(db,data,user): return merged.create(db,data,user)
def list_merged(db): return merged.list_runs(db)
def get_merged(db,id): return merged.get(db,id)
def rerun_merged(db,id,user): return merged.rerun(db,id,user)
