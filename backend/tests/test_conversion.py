"""换算核心：区间失效、简单路径、最少步数、字典序并列、最短路径分歧。"""
from src.services.conversion import convert_sample,enumerate_paths
from tests.conftest import entry

def test_direct_within_interval():
    r=convert_sample([entry('M1','M0',2,1,0,10)],'M1','M0',3)
    assert r['ok'] and r['value']==7 and r['instruments']==['M1','M0'] and r['step_count']==1

def test_same_instrument_zero_steps():
    r=convert_sample([entry('M1','M0',2,1,0,10)],'M0','M0',4.5)
    assert r['ok'] and r['value']==4.5 and r['step_count']==0 and r['instruments']==['M0']

def test_interval_boundary_inclusive():
    e=[entry('M1','M0',1,0,0,10)]
    assert convert_sample(e,'M1','M0',0)['ok']
    assert convert_sample(e,'M1','M0',10)['ok']

def test_interval_invalidated_direct():
    # 区间失效：读数落在唯一条目适用区间外 → 无可用路径，单列排除
    r=convert_sample([entry('M1','M0',1,0,0,10)],'M1','M0',10.5)
    assert not r['ok'] and r['reason']=='no-path'

def test_interval_invalidated_mid_path():
    # 区间失效：第一步可行，但换算后的中间值落在第二步区间外 → 整条路径不可用
    entries=[entry('M1','M2',1,0,0,10),entry('M2','M0',1,0,0,5)]
    assert not convert_sample(entries,'M1','M0',8)['ok']
    r=convert_sample(entries,'M1','M0',4)
    assert r['ok'] and r['value']==4 and r['instruments']==['M1','M2','M0']

def test_no_repeated_instruments():
    # 含环图 M2↔M3：路径不得重复经过仪器，且搜索必须终止
    entries=[entry('M1','M2',1,0,0,10),entry('M2','M3',1,0,0,10),
             entry('M3','M2',1,0,0,10),entry('M3','M1',1,0,0,10)]
    paths=enumerate_paths(entries,'M1','M3',5)
    assert len(paths)==1 and paths[0]['instruments']==['M1','M2','M3']
    for p in paths:
        assert len(p['instruments'])==len(set(p['instruments']))

def test_fewest_steps_wins():
    # 一步直达与两步链都可用时，选步数最少的一条
    entries=[entry('M1','M0',1,0.5,0,10),
             entry('M1','M2',1,0,0,10),entry('M2','M0',1,0,0,10)]
    r=convert_sample(entries,'M1','M0',3)
    assert r['ok'] and r['step_count']==1 and r['value']==3.5 and r['instruments']==['M1','M0']

def test_tie_break_by_instrument_sequence():
    # 并列最短：结果一致时按仪器编号序列字典序取首条（经 A 而非经 B）
    entries=[entry('M1','B',1,0,0,10),entry('B','M0',1,0.002,0,10),
             entry('M1','A',1,0,0,10),entry('A','M0',1,0.001,0,10)]
    r=convert_sample(entries,'M1','M0',3)
    assert r['ok'] and r['instruments']==['M1','A','M0'] and r['tied_paths']==2
    assert abs(r['value']-3.001)<1e-9

def test_divergence_within_tolerance_included():
    # 最短路径结果相差恰好 0.01（未超过）→ 不排除，取字典序首条
    entries=[entry('M1','A',1,0,0,10),entry('A','M0',1,0,0,10),
             entry('M1','B',1,0,0,10),entry('B','M0',1,0.01,0,10)]
    r=convert_sample(entries,'M1','M0',3)
    assert r['ok'] and r['instruments']==['M1','A','M0']

def test_divergence_over_tolerance_excluded():
    # 最短路径分歧：两条并列最短路径结果相差 0.05 > 0.01 → 单列排除并留档候选
    entries=[entry('M1','A',1,0,0,10),entry('A','M0',1,0,0,10),
             entry('M1','B',1,0,0,10),entry('B','M0',1,0.05,0,10)]
    r=convert_sample(entries,'M1','M0',3)
    assert not r['ok'] and r['reason']=='divergent'
    assert len(r['candidates'])==2 and '0.05' in r['detail']

def test_divergence_only_checked_among_shortest():
    # 更长的路径即使结果不同也不参与分歧判定
    entries=[entry('M1','M0',1,0,0,10),
             entry('M1','A',1,0,0,10),entry('A','M0',1,5,0,10)]
    r=convert_sample(entries,'M1','M0',3)
    assert r['ok'] and r['step_count']==1 and r['value']==3

def test_no_path_undefined_instrument():
    r=convert_sample([entry('M1','M0',1,0,0,10)],'M9','M0',3)
    assert not r['ok'] and r['reason']=='no-path'
