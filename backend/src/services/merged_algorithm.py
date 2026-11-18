import math
import numpy as np
from src.services.algorithm import quantile
from src.services.conversion import convert_sample

def calculate_merged(snapshot):
    """合并分布：把各批茶样含水率按冻结校准表换算到目标仪器后再汇总。

    只读取快照（冻结的校准表整版与观测），保证排队后发布的新版不影响本研究，
    重跑同一快照得到一致结果。换算及排除明细随结果留档，分布分母=纳入数。
    """
    target=snapshot['target_instrument']
    entries=snapshot['calibration_entries']
    B=int(snapshot.get('resamples',2000))
    if not 200<=B<=20000: raise ValueError('重采样次数必须是200到20000的整数')
    details,excluded,values=[],[],[]
    for batch in snapshot['batches']:
        instrument=batch['instrument']
        for obs in batch['observations']:
            raw=obs['moisture']
            base={'study_id':batch['study_id'],'batch':batch['study_name'],
                  'source_key':obs['source_key'],'instrument':instrument,'original':raw}
            if isinstance(raw,bool) or not isinstance(raw,(int,float)) or not math.isfinite(raw):
                excluded.append({**base,'reason':'invalid','detail':'含水率不是有限数值'});continue
            r=convert_sample(entries,instrument,target,raw)
            if r['ok']:
                values.append(r['value'])
                details.append({**base,'target_instrument':target,'converted':r['value'],
                                'path':r['instruments'],'step_count':r['step_count'],
                                'steps':[{k:s[k] for k in ('from_instrument','to_instrument','input','output')} for s in r['steps']]})
            else:
                excluded.append({**base,'reason':r['reason'],'detail':r['detail'],'candidates':r.get('candidates')})
    n=len(values)
    if n<3: raise ValueError(f'换算后仅纳入{n}份茶样，不足3份无法生成合并分布')
    if n>20000: raise ValueError('纳入样本超出上限')
    x=np.asarray(values,dtype=float)
    rng=np.random.default_rng(42)
    boot=[]
    for start in range(0,B,100):
        draws=rng.choice(x,size=(min(100,B-start),n),replace=True)
        boot.extend(np.median(draws,axis=1).tolist())
    lower,upper=quantile(boot,.025),quantile(boot,.975)
    q={label:quantile(x,p) for label,p in [('最小值',0),('P25',.25),('中位数',.5),('P75',.75),('最大值',1)]}
    unique=np.unique(x);ecdf=[[float(v),float(np.count_nonzero(x<=v)/n)] for v in unique]
    step=max(1,len(ecdf)//24)
    metrics={'总样本数':n+len(excluded),'纳入数':n,'排除数':len(excluded),'样本量':n,
             '均值':float(np.mean(x)),'样本标准差':float(np.std(x,ddof=1)),**q,
             '中位数95%区间':[lower,upper],'IQR':q['P75']-q['P25'],'重采样次数':B,'随机种子':42}
    return {'metrics':metrics,
            'interpretation':f"{len(snapshot['batches'])}批茶样统一换算至仪器 {target} 口径：共{n+len(excluded)}份，纳入{n}份（排除{len(excluded)}份），合并含水率(%)中位数为{q['中位数']:.3f}，95% percentile bootstrap置信区间为[{lower:.3f}, {upper:.3f}]。",
            'caveat':'本区间描述合并总体中位数估计的不确定性，不是单份茶样预测区间；换算沿用本研究冻结的整版校准表，校准本身的不确定性未纳入区间。排除样本单列留档，不计入分布分母。',
            'target_instrument':target,'calibration_version_id':snapshot['calibration_version_id'],
            'columns':['分位点','线性插值结果'],'rows':[[k,v] for k,v in q.items()],
            'table_title':'合并分布位置与离散程度（换算后口径）',
            'ecdf':ecdf,'chart':{'title':f'合并 ECDF · 统一换算至 {target}','points':ecdf[::step]},
            'conversion_details':details,'exclusions':excluded}
