import os,time,json,logging
from pathlib import Path
from redis import Redis
from sqlalchemy import select
from src.config.database import Session
from src.models.run import Run
from src.models.merged import MergedRun
from src.models import user,study,observation,review,audit,calibration,merged
from src.services.algorithm import calculate
from src.services.merged import execute as execute_merged,QUEUE as MERGED_QUEUE
from src.utils.serializers import checksum
redis=Redis.from_url(os.environ['REDIS_URL'])
ARTIFACTS=Path(os.environ.get('ARTIFACTS_DIR','/app/artifacts'));ARTIFACTS.mkdir(parents=True,exist_ok=True)
# Recover jobs interrupted after dequeue. A project runs exactly one worker.
with Session() as db:
    for run in db.scalars(select(Run).where(Run.status.in_(['queued','running']))): redis.rpush('analysis-queue',run.id)
    for run in db.scalars(select(MergedRun).where(MergedRun.status.in_(['queued','running']))): redis.rpush(MERGED_QUEUE,run.id)
while True:
    Path('/tmp/worker-heartbeat').touch()
    job=redis.blpop(['analysis-queue',MERGED_QUEUE],timeout=2)
    if not job: continue
    queue,id=job[0].decode(),int(job[1])
    with Session() as db:
        model=Run if queue=='analysis-queue' else MergedRun
        run=db.get(model,id)
        if not run or run.status in ('completed','failed'): continue
        run.status='running';db.commit()
        try:
            if queue=='analysis-queue':
                if checksum(run.snapshot)!=run.checksum: raise ValueError('输入快照校验失败')
                result=calculate(run.snapshot,run.parameters)
                result['input_sha256']=run.checksum
                run.result=result
                (ARTIFACTS/f'run-{id}.json').write_text(json.dumps(result,ensure_ascii=False,allow_nan=False))
            else:
                execute_merged(db,run)
            run.status='completed'
        except Exception as e:
            logging.exception('analysis failed');run.status='failed';run.error=str(e)
        db.commit()
