import os,sys,tempfile
from pathlib import Path
TMP=Path(tempfile.mkdtemp(prefix='tea-calib-test-'))
os.environ['DATABASE_URL']='sqlite:///'+str(TMP/'test.db')
os.environ['REDIS_URL']='redis://localhost:6379/15'
os.environ['JWT_SECRET']='test-secret'
os.environ['SEED_DEMO']='false'
os.environ['ARTIFACTS_DIR']=str(TMP/'artifacts')
sys.path.insert(0,str(Path(__file__).parents[1]))
import pytest
from src.config.database import Base,engine,Session

class FakeRedis:
    """拦截队列推送，测试无需真实 Redis。"""
    pushed=[]
    @classmethod
    def from_url(cls,url): return cls()
    def rpush(self,queue,value): FakeRedis.pushed.append((queue,value));return 1
    def incr(self,key): return 1
    def expire(self,key,seconds): return True

@pytest.fixture(autouse=True)
def fake_redis(monkeypatch):
    FakeRedis.pushed=[]
    monkeypatch.setattr('src.services.merged.Redis',FakeRedis)
    monkeypatch.setattr('src.services.runs.Redis',FakeRedis)
    yield FakeRedis

@pytest.fixture()
def db():
    Base.metadata.create_all(engine)
    with Session() as session:
        yield session
    Base.metadata.drop_all(engine)

@pytest.fixture()
def user(db):
    from src.models.user import User
    from src.utils.security import hash_password
    u=User(email='analyst@demo.local',role='analyst',password_hash=hash_password('Research2026!'))
    db.add(u);db.commit();return u

def make_study(db,name,moistures):
    from src.models.study import Study
    from src.models.observation import Observation
    s=Study(name=name,source_filename='t.csv',description='')
    db.add(s);db.flush()
    for i,m in enumerate(moistures):
        db.add(Observation(study_id=s.id,source_key=f'{name}-{i+1:03}',values={'moisture':m,'extract':30.0}))
    db.commit();return s

def entry(f,t,slope,intercept,lo,hi):
    return {'from_instrument':f,'to_instrument':t,'slope':slope,'intercept':intercept,'lo':lo,'hi':hi}
