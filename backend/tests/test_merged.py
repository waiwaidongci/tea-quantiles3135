"""服务层：发布撞上排队（版本冻结）、重跑一致、排除留档与分母一致。"""
import json,os
import pytest
from pathlib import Path
from fastapi import HTTPException
from src.models.merged import MergedRun
from src.schemas.calibration import CalibrationPublishInput,MergedRunInput
from src.services import calibration,merged
from tests.conftest import entry,make_study

def publish(db,user,entries,note=''):
    return calibration.publish(db,CalibrationPublishInput(note=note,entries=entries),user)

def create_run(db,user,batches,target='M0',resamples=200):
    return merged.create(db,MergedRunInput(name='合并核算',target_instrument=target,batches=batches,resamples=resamples),user)

def execute(db,run_id):
    run=db.get(MergedRun,run_id)
    merged.execute(db,run)
    run.status='completed';db.commit();db.refresh(run)
    return run

def test_publish_collides_with_queue(db,user):
    # 发布撞上排队：研究排队时冻结 v1；随后发布 v2，排队研究仍按 v1 换算
    v1=publish(db,user,[entry('M1','M0',1,1,0,100)],note='v1')
    s=make_study(db,'批A',[1,2,3,4,5])
    run=create_run(db,user,[{'study_id':s.id,'instrument':'M1'}])
    assert run['calibration_version_id']==v1['id']
    v2=publish(db,user,[entry('M1','M0',1,10,0,100)],note='v2')
    assert calibration.latest(db).id==v2['id']
    run=execute(db,run['id'])
    assert run.status=='completed'
    details=run.result['conversion_details']
    assert all(abs(d['converted']-(d['original']+1))<1e-9 for d in details)  # v1: +1 而非 v2: +10
    assert run.result['calibration_version_id']==v1['id']
    assert run.result['metrics']['均值']==pytest.approx(4.0)

def test_rerun_matches_original(db,user):
    # 旧研究重跑：复用同一冻结快照，checksum 与结果明细保持一致
    publish(db,user,[entry('M1','M0',0.98,0.12,0,15)])
    s=make_study(db,'批A',[3.1,4.2,5.3,6.4])
    run=execute(db,create_run(db,user,[{'study_id':s.id,'instrument':'M1'}])['id'])
    clone=merged.rerun(db,run.id,user)
    assert clone['checksum']==run.checksum and clone['snapshot']==run.snapshot
    clone=execute(db,clone['id'])
    assert clone.result==run.result
    assert clone.result['conversion_details']==run.result['conversion_details']
    assert clone.result['exclusions']==run.result['exclusions']
    artifact=Path(os.environ['ARTIFACTS_DIR'])/f'merged-{clone.id}.json'
    assert json.loads(artifact.read_text())==clone.result

def test_exclusions_archived_and_denominator_consistent(db,user):
    # 区间失效（无路径）+ 最短路径分歧 同时出现：排除单列留档，纳入数=分布分母
    publish(db,user,[
        entry('M1','M0',1,0,0,10),          # 区间外读数 → no-path
        entry('M2','A',1,0,0,100),entry('A','M0',1,0,0,100),
        entry('M2','B',1,0,0,100),entry('B','M0',1,0.05,0,100),  # 并列最短分歧 0.05 → divergent
    ])
    s1=make_study(db,'批A',[1,2,3,50])     # 50 超出 [0,10]
    s2=make_study(db,'批B',[4,5,6])        # M2 全部最短路径分歧
    run=execute(db,create_run(db,user,[{'study_id':s1.id,'instrument':'M1'},{'study_id':s2.id,'instrument':'M2'}])['id'])
    res=run.result
    reasons=sorted(e['reason'] for e in res['exclusions'])
    assert reasons==['divergent','divergent','divergent','no-path']
    divergent=[e for e in res['exclusions'] if e['reason']=='divergent'][0]
    assert len(divergent['candidates'])==2
    m=res['metrics']
    assert m['样本量']==m['纳入数']==len(res['conversion_details'])==3   # 纳入数与分布分母一致
    assert m['总样本数']==m['纳入数']+m['排除数']==7
    assert {d['source_key'] for d in res['conversion_details']}=={'批A-001','批A-002','批A-003'}

def test_multi_batch_merge_to_designated_instrument(db,user):
    publish(db,user,[entry('M1','M0',1,0.1,0,100),entry('M2','M0',2,0,0,100)])
    s1=make_study(db,'批A',[1,2,3])
    s2=make_study(db,'批B',[2,3,4])
    s3=make_study(db,'批C',[5,6,7])       # 已在目标仪器，零步路径
    run=execute(db,create_run(db,user,[
        {'study_id':s1.id,'instrument':'M1'},
        {'study_id':s2.id,'instrument':'M2'},
        {'study_id':s3.id,'instrument':'M0'}])['id'])
    res=run.result
    assert res['metrics']['样本量']==9
    by_batch={}
    for d in res['conversion_details']: by_batch.setdefault(d['batch'],[]).append(d)
    assert all(abs(d['converted']-(d['original']+0.1))<1e-9 for d in by_batch['批A'])
    assert all(abs(d['converted']-2*d['original'])<1e-9 for d in by_batch['批B'])
    assert all(d['converted']==d['original'] and d['step_count']==0 for d in by_batch['批C'])

def test_too_few_included_fails(db,user):
    publish(db,user,[entry('M1','M0',1,0,0,10)])
    s=make_study(db,'批A',[1,2,50])       # 仅 2 份可纳入
    run=db.get(MergedRun,create_run(db,user,[{'study_id':s.id,'instrument':'M1'}])['id'])
    with pytest.raises(ValueError,match='不足3份'):
        merged.execute(db,run)

def test_publish_validation(db,user):
    with pytest.raises(HTTPException): publish(db,user,[entry('M1','M1',1,0,0,10)])       # 源=目标
    with pytest.raises(HTTPException): publish(db,user,[entry('M1','M0',0,0,0,10)])       # 斜率 0
    with pytest.raises(HTTPException): publish(db,user,[entry('M1','M0',1,0,10,0)])       # 区间倒置
    with pytest.raises(HTTPException): publish(db,user,[entry('M1','M0',1,float('nan'),0,10)])
    with pytest.raises(HTTPException): create_run(db,user,[{'study_id':1,'instrument':'M1'}])  # 无校准表

def test_create_requires_calibration_and_observations(db,user):
    publish(db,user,[entry('M1','M0',1,0,0,10)])
    empty=make_study(db,'空批',[])
    with pytest.raises(HTTPException): create_run(db,user,[{'study_id':empty.id,'instrument':'M1'}])
    s=make_study(db,'批A',[1,2,3])
    with pytest.raises(HTTPException): create_run(db,user,[{'study_id':s.id,'instrument':'M1'},{'study_id':s.id,'instrument':'M2'}])
