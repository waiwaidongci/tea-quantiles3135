"""API 层：登录、角色约束、发布校准表→发起合并研究→查看换算依据 全链路。"""
import pytest
from fastapi.testclient import TestClient
from tests.conftest import entry,make_study

@pytest.fixture()
def client(db,monkeypatch):
    monkeypatch.setattr('src.middlewares.rate_limit.redis',__import__('tests.conftest',fromlist=['FakeRedis']).FakeRedis())
    from src.main import app
    with TestClient(app) as c: yield c

def login(client,email):
    r=client.post('/auth/login',json={'email':email,'password':'Research2026!'})
    assert r.status_code==200,r.text
    return {'Authorization':'Bearer '+r.json()['token']}

@pytest.fixture()
def users(db):
    from src.models.user import User
    from src.utils.security import hash_password
    for role in ('admin','analyst','viewer'):
        db.add(User(email=role+'@demo.local',role=role,password_hash=hash_password('Research2026!')))
    db.commit()

def test_full_flow_and_roles(client,users,db):
    analyst=login(client,'analyst@demo.local')
    viewer=login(client,'viewer@demo.local')
    s=make_study(db,'批A',[1,2,3,4,5])
    # 观察员不能发布校准表
    r=client.post('/calibrations',json={'note':'v1','entries':[entry('M1','M0',1,1,0,100)]},headers=viewer)
    assert r.status_code==403
    # 分析师发布校准表
    r=client.post('/calibrations',json={'note':'v1','entries':[entry('M1','M0',1,1,0,100)]},headers=analyst)
    assert r.status_code==200,r.text
    version=r.json()
    assert version['entries'][0]['from_instrument']=='M1' and version['checksum']
    # 版本列表与换算依据
    r=client.get('/calibrations',headers=viewer);assert r.status_code==200 and r.json()[0]['entry_count']==1
    r=client.get(f"/calibrations/{version['id']}",headers=viewer);assert r.status_code==200
    # 未登录拒绝
    assert client.get('/calibrations').status_code==401
    # 发起合并研究：排队并冻结当前版本
    r=client.post('/merged-runs',json={'name':'合并核算','target_instrument':'M0','resamples':200,
                                       'batches':[{'study_id':s.id,'instrument':'M1'}]},headers=analyst)
    assert r.status_code==200,r.text
    run=r.json()
    assert run['status']=='queued' and run['calibration_version_id']==version['id']
    assert len(run['snapshot']['calibration_entries'])==1 and len(run['snapshot']['batches'][0]['observations'])==5
    # 观察员不能发起研究
    assert client.post('/merged-runs',json={'name':'x研究','target_instrument':'M0','batches':[{'study_id':s.id,'instrument':'M1'}]},headers=viewer).status_code==403
    # 详情与列表可读（换算依据留档）
    r=client.get(f"/merged-runs/{run['id']}",headers=viewer);assert r.status_code==200 and r.json()['checksum']==run['checksum']
    assert client.get('/merged-runs',headers=viewer).status_code==200
    # 重跑生成同一 checksum 的新排队研究
    r=client.post(f"/merged-runs/{run['id']}/rerun",headers=analyst)
    assert r.status_code==200 and r.json()['checksum']==run['checksum'] and r.json()['id']!=run['id']
    # 审计留痕包含发布、排队与重跑
    actions=[a['action'] for a in client.get('/audits',headers=analyst).json()]
    assert 'calibration.publish' in actions and 'merged.queue' in actions and 'merged.rerun' in actions

def test_merged_run_validation_errors(client,users,db):
    analyst=login(client,'analyst@demo.local')
    client.post('/calibrations',json={'note':'v1','entries':[entry('M1','M0',1,1,0,100)]},headers=analyst)
    s=make_study(db,'批A',[1,2,3])
    # 未知批次
    assert client.post('/merged-runs',json={'name':'合并核算','target_instrument':'M0','batches':[{'study_id':999,'instrument':'M1'}]},headers=analyst).status_code==404
    # 非法校准条目被 422 拒绝
    r=client.post('/calibrations',json={'note':'bad','entries':[entry('M1','M0',1,0,10,0)]},headers=analyst)
    assert r.status_code==422
