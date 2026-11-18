import {store,load} from '../stores/research.js';
import {mergedRuns} from '../api/research.js';
import {esc,fmt} from '../utils/format.js';
import {table} from '../components/common/table.js';
import {status} from '../components/common/status.js';
const REASONS={'no-path':'无可用路径','divergent':'最短路径分歧','invalid':'数值非法'};
export async function render(id){
 if(!id)return `<h1>合并研究</h1><p>从「校准合并」页发起或选择一次合并研究，查看合并分布与换算依据。</p>`;
 const r=await mergedRuns.get(id);store.mergedId=r.id;
 const writable=localStorage.getItem('research-role')!=='viewer';
 const res=r.result;
 return `<div class="eyebrow">MERGED DISTRIBUTION · RUN ${r.id}</div><h1>${esc(r.name)} ${status(r.status)}</h1>
 <div class="checksum">INPUT SHA256 ${r.checksum}</div>
 <p>目标仪器 ${esc(r.target_instrument)} · 冻结校准表 v${r.calibration_version_id} · ${esc(r.created_at)}</p>
 ${r.status==='failed'?`<div class="error">计算失败：${esc(r.error)}。请核对校准表覆盖区间与批次仪器标注，然后重跑或新建研究。</div>`:res?`
 <section class="result-intro"><strong>${esc(res.interpretation)}</strong><p>${esc(res.caveat)}</p></section>
 <h2>核心数值</h2>${table(['业务指标','计算值'],Object.entries(res.metrics).map(([k,v])=>[k,fmt(v)]))}
 <p class="method-note">纳入 ${res.metrics['纳入数']} 份 = 分布分母（样本量 ${res.metrics['样本量']}）；排除 ${res.metrics['排除数']} 份单列于下，不进入分母。</p>
 <h2>${esc(res.table_title)}</h2>${table(res.columns,res.rows)}
 ${res.chart?`<h2>${esc(res.chart.title)}</h2><div class="chart">${res.chart.points.map(([x,y])=>`<div class="chart-row"><span>${esc(fmt(x))}</span><i style="width:${Math.max(1,Math.min(100,Number(y)*100))}%"></i><b>${esc(fmt(y))}</b></div>`).join('')}</div>`:''}
 <h2>换算明细 <small>${res.conversion_details.length} 条纳入，随分布留档</small></h2>
 ${table(['批次','源记录','实测仪器','原值','换算值','换算路径','步数'],res.conversion_details.map(d=>[d.batch,d.source_key,d.instrument,fmt(d.original),fmt(d.converted),d.path.join(' → '),d.step_count]))}
 <h2>排除明细 <small>${res.exclusions.length} 条，不计入分布</small></h2>
 ${table(['批次','源记录','实测仪器','原值','排除原因','说明'],res.exclusions.map(d=>[d.batch,d.source_key,d.instrument,fmt(d.original),REASONS[d.reason]||d.reason,d.detail]))}
 `:'<p class="method-note">任务正在队列中。此页每2秒更新，结果写入数据库后展示。</p>'}
 <div class="toolbar">${writable&&r.status!=='queued'&&r.status!=='running'?`<button id="rerun" class="secondary">按冻结输入与校准表重跑 →</button>`:''}<a class="button secondary" href="#calibration">返回校准合并 →</a></div>
 <details><summary>本次冻结的参数、快照与整版校准表</summary><pre>${esc(JSON.stringify({parameters:r.parameters,snapshot:r.snapshot},null,2))}</pre></details>`;
}
export function bind(){const b=document.getElementById('rerun');if(b)b.onclick=async()=>{try{const r=await mergedRuns.rerun(store.mergedId);await load();location.hash='merged/'+r.id;}catch(e){document.getElementById('notice').textContent=e.message;}};}
