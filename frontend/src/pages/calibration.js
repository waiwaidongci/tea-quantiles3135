import {store,load} from '../stores/research.js';
import {calibrations,mergedRuns} from '../api/research.js';
import {table} from '../components/common/table.js';
import {status} from '../components/common/status.js';
import {bindForm} from '../hooks/forms.js';
import {esc} from '../utils/format.js';
const RULE='每步换算须落在该校准条目适用区间内，同一路径不重复经过仪器；可用路径取步数最少，并列按仪器编号序列取首条；最短路径结果相差超过 0.01 个百分点或无可用路径的茶样单列排除，不计入分布分母。';
export function render(){
 const writable=localStorage.getItem('research-role')!=='viewer';
 return `<div class="eyebrow">04 / CALIBRATION &amp; MERGE</div><h1>仪器校准与合并分布</h1>
 <p class="lead">不同仪器测的含水率直接混算会偏：先按线性校准表把多批茶样换算到指定仪器，再生成合并分布。</p>
 <div class="method-note">${RULE}</div>
 ${writable?`<h2>发布校准表</h2><form id="cal-form" class="worksheet"><label>版本说明<input name="note" placeholder="如 2026-11 复校" maxlength="500"></label><div id="entries"></div><div class="toolbar"><button type="button" class="secondary" id="add-entry">+ 增加校准条目</button><button type="submit">发布新版校准表 →</button></div><p>条目形式 y = 斜率·x + 截距，x 为源仪器读数，仅在其适用区间内可用。发布后整版冻结，排队中的研究继续沿用其冻结版本。</p></form>`:'<p class="method-note">观察员可查看校准表与换算依据；发布校准表与发起研究需分析师或负责人。</p>'}
 <h2>校准表版本 <small>换算依据留档，新版不影响已排队研究</small></h2>
 ${store.calibrations.length?store.calibrations.map(v=>`<details class="version"><summary>v${v.id} · ${esc(v.note||'未命名')} · ${v.entry_count}条 · ${esc(v.author)} · ${esc(v.created_at)} · SHA256 ${v.checksum.slice(0,12)}</summary><div data-version="${v.id}">展开读取条目…</div></details>`).join(''):'<p>尚无校准表，请先发布。</p>'}
 ${writable?`<h2>发起合并研究</h2><form id="merged-form" class="worksheet"><label>研究名称<input name="name" required minlength="2" value="多批含水率合并 · 核算"></label><div class="inline-form"><label>目标仪器（指定口径）<input name="target_instrument" required placeholder="如 M0" maxlength="40"></label><label>重采样次数 (200–20000)<input name="resamples" type="number" value="2000" min="200" max="20000" required></label></div><h3>选择批次并标注实测仪器</h3>${store.studies.map(s=>`<label class="batch-row"><input type="checkbox" name="study_${s.id}"> ${esc(s.name)} · ${s.row_count}条 → 仪器 <input name="inst_${s.id}" placeholder="如 M1" maxlength="40"></label>`).join('')}<p>提交时冻结所选观测与当前最新整版校准表，生成 SHA256。后台 worker 独立执行。</p><button type="submit">冻结输入与校准表并排队 →</button></form>`:''}
 <h2>合并研究记录</h2>
 ${table(['编号 / 研究','状态','目标仪器','校准表版本','留档 SHA256'],store.mergedRuns.map(r=>[{html:`<a href="#merged/${r.id}">#${r.id} ${esc(r.name)}</a>`},{html:status(r.status)},r.target_instrument,'v'+r.calibration_version_id,r.checksum.slice(0,12)]))}`;
}
function entryRow(){const d=document.createElement('div');d.className='inline-form entry-row';d.innerHTML=`<label>从<input data-f required placeholder="M1" maxlength="40"></label><label>到<input data-t required placeholder="M0" maxlength="40"></label><label>斜率<input data-a type="number" step="any" required></label><label>截距<input data-b type="number" step="any" required></label><label>区间下限<input data-lo type="number" step="any" required></label><label>区间上限<input data-hi type="number" step="any" required></label><button type="button" class="text" data-rm>移除</button>`;d.querySelector('[data-rm]').onclick=()=>d.remove();return d;}
export function bind(refresh){
 const entries=document.getElementById('entries');
 if(entries){entries.appendChild(entryRow());document.getElementById('add-entry').onclick=()=>entries.appendChild(entryRow());}
 bindForm('cal-form',async data=>{
  const list=[...document.querySelectorAll('.entry-row')].map(r=>({from_instrument:r.querySelector('[data-f]').value.trim(),to_instrument:r.querySelector('[data-t]').value.trim(),slope:+r.querySelector('[data-a]').value,intercept:+r.querySelector('[data-b]').value,lo:+r.querySelector('[data-lo]').value,hi:+r.querySelector('[data-hi]').value}));
  if(!list.length)throw new Error('至少一条校准条目');
  await calibrations.create({note:data.note,entries:list});await load();refresh();
 });
 bindForm('merged-form',async data=>{
  const batches=store.studies.filter(s=>data['study_'+s.id]).map(s=>({study_id:s.id,instrument:(data['inst_'+s.id]||'').trim()}));
  if(!batches.length)throw new Error('至少选择一个批次');
  if(batches.some(b=>!b.instrument))throw new Error('每个选中批次都要填写实测仪器');
  const r=await mergedRuns.create({name:data.name,target_instrument:data.target_instrument.trim(),resamples:+data.resamples,batches});
  await load();location.hash='merged/'+r.id;
 });
 document.querySelectorAll('[data-version]').forEach(el=>{const box=el.closest('details');box.ontoggle=async()=>{if(box.open&&!el.dataset.done){try{const v=await calibrations.get(el.dataset.version);el.dataset.done=1;el.innerHTML=table(['从','到','斜率','截距','适用区间'],v.entries.map(e=>[e.from_instrument,e.to_instrument,e.slope,e.intercept,`[${e.lo}, ${e.hi}]`]))}catch(e){el.textContent=e.message;}}};});
}
