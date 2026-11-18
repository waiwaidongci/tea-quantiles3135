"""回归：原有批次分布研究链路（录入→排队→计算→复核）不受校准功能影响。"""
from src.models.run import Run
from src.schemas.run import RunInput
from src.schemas.review import ReviewInput
from src.services import runs
from src.services.algorithm import calculate
from tests.conftest import make_study

def test_distribution_run_flow_unchanged(db,user):
    s=make_study(db,'批A',[5.1,5.2,5.3,5.4,5.5])
    run=runs.create(db,RunInput(study_id=s.id,name='常规分布核算',parameters={'field':'moisture','resamples':200}),user)
    assert run['status']=='queued' and len(run['snapshot'])==5
    result=calculate(run['snapshot'],run['parameters'])
    assert result['metrics']['样本量']==5 and '中位数95%区间' in result['metrics']
    row=db.get(Run,run['id']);row.result=result;row.status='completed';db.commit()
    review=runs.approve(db,run['id'],ReviewInput(note='复核通过，区间口径正确'),user)
    assert review['run_id']==run['id']
    detail=runs.get(db,run['id'])
    assert detail['review'] and detail['result']['metrics']['样本量']==5
