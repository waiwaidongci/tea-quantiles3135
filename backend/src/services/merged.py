import os,json
from pathlib import Path
from redis import Redis
from sqlalchemy import select
from fastapi import HTTPException
from src.models.merged import MergedRun
from src.services import studies,calibration
from src.services.audits import log
from src.services.merged_algorithm import calculate_merged
from src.utils.serializers import record,now,checksum

QUEUE='merged-queue'

def create(db,data,user):
    version=calibration.latest(db)
    if not version: raise HTTPException(422,'请先发布至少一版校准表，再发起合并研究')
    ids=[b.study_id for b in data.batches]
    if len(set(ids))!=len(ids): raise HTTPException(422,'同一批次不能重复选择')
    batches=[]
    for b in data.batches:
        s=studies.require(db,b.study_id)
        rows=studies.observations(db,b.study_id)
        if not rows: raise HTTPException(422,f'批次「{s.name}」没有观测，无法纳入合并')
        instrument=b.instrument.strip()
        if not instrument: raise HTTPException(422,f'批次「{s.name}」必须标注实测仪器')
        obs=[{'source_key':r['source_key'],'moisture':r['values'].get('moisture')} for r in rows]
        batches.append({'study_id':s.id,'study_name':s.name,'instrument':instrument,'observations':obs})
    target=data.target_instrument.strip()
    if not target: raise HTTPException(422,'目标仪器编号不能为空')
    # 排队即冻结一整版校准表与全部输入；之后发布新版不影响本研究
    snapshot={'target_instrument':target,'calibration_version_id':version.id,
              'calibration_entries':calibration.entries_of(db,version.id),
              'batches':batches,'resamples':data.resamples}
    run=MergedRun(name=data.name,target_instrument=target,calibration_version_id=version.id,
                  parameters={'batches':[{'study_id':b['study_id'],'instrument':b['instrument']} for b in batches],
                              'resamples':data.resamples},
                  snapshot=snapshot,checksum=checksum(snapshot),created_at=now(),status='queued')
    db.add(run);db.flush();log(db,user,'merged.queue',str(run.id));db.commit()
    Redis.from_url(os.environ['REDIS_URL']).rpush(QUEUE,run.id)
    return record(run)

def get(db,id):
    run=db.get(MergedRun,id)
    if not run: raise HTTPException(404,'合并研究不存在')
    return record(run)

def list_runs(db):
    return [record(x) for x in db.scalars(select(MergedRun).order_by(MergedRun.id.desc()))]

def rerun(db,id,user):
    run=db.get(MergedRun,id)
    if not run: raise HTTPException(404,'合并研究不存在')
    # 重跑复用同一冻结快照（同一校准表整版与输入），checksum 与结果保持一致
    clone=MergedRun(name=run.name+' · 重跑',target_instrument=run.target_instrument,
                    calibration_version_id=run.calibration_version_id,parameters=run.parameters,
                    snapshot=run.snapshot,checksum=run.checksum,created_at=now(),status='queued')
    db.add(clone);db.flush();log(db,user,'merged.rerun',f'{id}→{clone.id}');db.commit()
    Redis.from_url(os.environ['REDIS_URL']).rpush(QUEUE,clone.id)
    return record(clone)

def execute(db,run):
    """worker 调用：仅依据冻结快照计算并留档。异常由调用方标记 failed。"""
    if checksum(run.snapshot)!=run.checksum: raise ValueError('输入快照校验失败')
    result=calculate_merged(run.snapshot)
    result['input_sha256']=run.checksum
    run.result=result
    artifacts=Path(os.environ.get('ARTIFACTS_DIR','/app/artifacts'));artifacts.mkdir(parents=True,exist_ok=True)
    (artifacts/f'merged-{run.id}.json').write_text(json.dumps(result,ensure_ascii=False,allow_nan=False))
