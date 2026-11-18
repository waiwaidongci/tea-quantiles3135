from pydantic import BaseModel,Field
class CalibrationEntryInput(BaseModel):
    from_instrument:str=Field(min_length=1,max_length=40)
    to_instrument:str=Field(min_length=1,max_length=40)
    slope:float
    intercept:float
    lo:float
    hi:float
class CalibrationPublishInput(BaseModel):
    note:str=Field(default='',max_length=500)
    entries:list[CalibrationEntryInput]=Field(min_length=1,max_length=200)
class MergedBatchInput(BaseModel):
    study_id:int=Field(gt=0)
    instrument:str=Field(min_length=1,max_length=40)
class MergedRunInput(BaseModel):
    name:str=Field(min_length=2,max_length=120)
    target_instrument:str=Field(min_length=1,max_length=40)
    batches:list[MergedBatchInput]=Field(min_length=1,max_length=20)
    resamples:int=Field(default=2000,ge=200,le=20000)
