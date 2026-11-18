import math
from fastapi import HTTPException
from sqlalchemy import select,func
from src.models.calibration import CalibrationVersion,CalibrationEntry
from src.services.audits import log
from src.utils.serializers import record,now,checksum

def _canonical(entries):
    return [{k:e[k] for k in ('from_instrument','to_instrument','slope','intercept','lo','hi')} for e in entries]

def entries_of(db,version_id):
    return [record(e) for e in db.scalars(select(CalibrationEntry).where(CalibrationEntry.version_id==version_id).order_by(CalibrationEntry.id))]

def publish(db,data,user):
    entries=[]
    for i,e in enumerate(data.entries,1):
        f,t=e.from_instrument.strip(),e.to_instrument.strip()
        if not f or not t: raise HTTPException(422,f'第{i}条：仪器编号不能为空')
        if f==t: raise HTTPException(422,f'第{i}条：源仪器与目标仪器不能相同')
        for label,v in [('斜率',e.slope),('截距',e.intercept),('区间下限',e.lo),('区间上限',e.hi)]:
            if isinstance(v,bool) or not math.isfinite(v): raise HTTPException(422,f'第{i}条：{label}必须为有限数值')
        if e.slope==0: raise HTTPException(422,f'第{i}条：斜率不能为0')
        if not e.lo<e.hi: raise HTTPException(422,f'第{i}条：适用区间下限必须小于上限')
        entries.append({'from_instrument':f,'to_instrument':t,'slope':float(e.slope),'intercept':float(e.intercept),'lo':float(e.lo),'hi':float(e.hi)})
    version=CalibrationVersion(note=data.note.strip(),author=user.email,checksum=checksum(_canonical(entries)),created_at=now())
    db.add(version);db.flush()
    for e in entries: db.add(CalibrationEntry(version_id=version.id,**e))
    log(db,user,'calibration.publish',f'v{version.id}: {len(entries)}条')
    db.commit()
    return get_version(db,version.id)

def list_versions(db):
    out=[]
    for v in db.scalars(select(CalibrationVersion).order_by(CalibrationVersion.id.desc())):
        x=record(v)
        x['entry_count']=db.scalar(select(func.count()).select_from(CalibrationEntry).where(CalibrationEntry.version_id==v.id))
        out.append(x)
    return out

def get_version(db,version_id):
    v=db.get(CalibrationVersion,version_id)
    if not v: raise HTTPException(404,'校准表版本不存在')
    x=record(v);x['entries']=entries_of(db,v.id)
    return x

def latest(db):
    return db.scalar(select(CalibrationVersion).order_by(CalibrationVersion.id.desc()).limit(1))
