"""仪器间线性校准换算：路径搜索与样本换算。

校准条目：y = slope * x + intercept，仅当该步输入值 x 落在 [lo, hi] 闭区间内才可用。
路径规则：每步须落在该步适用区间内；同一路径不重复经过仪器（简单路径）。
选路规则：可用路径中取步数最少；并列时按仪器编号序列字典序取首条；
若全部最短路径的换算结果相差超过 0.01 个百分点，该样本单列排除。
"""
EPS=1e-9          # 区间端点浮点容差，端点视为落在区间内
TOLERANCE=0.01    # 最短路径结果允许的最大分歧（百分点），严格超过才排除

def _in_interval(value,lo,hi):
    return lo-EPS<=value<=hi+EPS

def _step_record(entry,input_value,output_value):
    return {'from_instrument':entry['from_instrument'],'to_instrument':entry['to_instrument'],
            'slope':entry['slope'],'intercept':entry['intercept'],'lo':entry['lo'],'hi':entry['hi'],
            'input':input_value,'output':output_value}

def enumerate_paths(entries,source,target,value):
    """从 source 到 target 的全部可用简单路径（不重复经过仪器）。

    每走一步先验证当前值落在该条目适用区间内，再按线性式换算。
    source==target 时返回零步路径，原值不变。
    """
    value=float(value)
    if source==target:
        return [{'instruments':[source],'steps':[],'value':value}]
    adj={}
    for entry in entries:
        adj.setdefault(entry['from_instrument'],[]).append(entry)
    found=[]
    def dfs(current,current_value,instruments,steps):
        for entry in adj.get(current,[]):
            nxt=entry['to_instrument']
            if nxt in instruments:  # 同一路径不重复经过仪器
                continue
            if not _in_interval(current_value,entry['lo'],entry['hi']):
                continue
            converted=entry['slope']*current_value+entry['intercept']
            next_instruments=instruments+[nxt]
            next_steps=steps+[_step_record(entry,current_value,converted)]
            if nxt==target:
                found.append({'instruments':next_instruments,'steps':next_steps,'value':converted})
            else:
                dfs(nxt,converted,next_instruments,next_steps)
    dfs(source,value,[source],[])
    return found

def convert_sample(entries,source,target,value):
    """换算单个样本。

    返回 {'ok':True,...} 含换算值与路径留档；或 {'ok':False,'reason':...}：
    reason='no-path' 无可用路径；reason='divergent' 最短路径结果相差超过 0.01 个百分点。
    """
    value=float(value)
    paths=enumerate_paths(entries,source,target,value)
    if not paths:
        return {'ok':False,'reason':'no-path',
                'detail':f'仪器 {source} → {target} 无可用换算路径（未定义校准或逐步换算值落在适用区间外）'}
    fewest=min(len(p['steps']) for p in paths)
    shortest=[p for p in paths if len(p['steps'])==fewest]
    shortest.sort(key=lambda p:p['instruments'])  # 并列按仪器编号序列字典序
    results=[p['value'] for p in shortest]
    spread=max(results)-min(results)
    # round(...,9) 消除二进制浮点尾差，使 0.01 边界按十进制直觉判定：严格超过才排除
    if round(spread,9)>TOLERANCE:
        return {'ok':False,'reason':'divergent',
                'detail':f'{len(shortest)} 条最短路径（{fewest}步）换算结果相差 {spread:.6f} 个百分点，超过 0.01',
                'candidates':[{'instruments':p['instruments'],'value':p['value']} for p in shortest]}
    chosen=shortest[0]
    return {'ok':True,'value':chosen['value'],'instruments':chosen['instruments'],
            'steps':chosen['steps'],'step_count':fewest,'tied_paths':len(shortest)}
