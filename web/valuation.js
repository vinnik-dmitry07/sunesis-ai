let valuationScratch, valuationOriginal, valuationScenarioCache, reverseCache;

function terminalRoicProposal(){return {id:'scenario-terminal-roic',cell:'Input sheet!B49',label:'Terminal return on invested capital',value:0.15,type:'percentage_decimal',unit:'percentage_decimal',kind:'assumption',rationale:'Explicit terminal ROIC chosen for this scenario. A historical return does not establish a perpetual return.',sourceIds:[]};}
function valuationExtraProposals(){
  if(!data)return [];
  const p=data.proposals.find(x=>x.cell==='Input sheet!B48');
  const enabled=p&&(state.statuses[p.id]==='edited'?state.edits[p.id]:p.value);
  return enabled==='Yes'?[terminalRoicProposal()]:[];
}
function valuationPayload(){return typeof BUNDLED_VALUATION==='undefined'?null:BUNDLED_VALUATION;}
function initValuationBook(){
  const v=valuationPayload();if(!v)return;
  for(const item of v.books??[]){
    if(!item.cells)continue;
    for(const [id,c] of Object.entries(item.cells)){
      if(book.cells[id])throw new Error(`Valuation sheet collides with original cell ${id}`);
      book.cells[id]=c;
    }
    const names=new Set(Object.values(item.cells).map(c=>c.sheet));
    for(const name of names)if(!book.sheets.some(s=>s.name===name))book.sheets.push({name});
  }
}
function ensureValuationEngines(){
  if(!valuationScratch){valuationScratch=new WorkbookEngine(book);valuationOriginal=new WorkbookEngine(book);}
}
function scenarioOverrides(s){return {...(s.overrides??s.inputs?.overrides??{})};}
function originalValuationOverrides(){return {...(valuationPayload()?.original?.overrides??valuationPayload()?.measurement?.proposals?.filter(p=>p.operation!=='retain_formula').reduce((o,p)=>(o[p.cell]=p.value,o),{})??{})};}
function valuationGuard(e){
  const old=caseError(e);if(old)return old;
  if(e.value('Input sheet!B48')==='Yes'){
    const r=e.value('Input sheet!B49'),g=e.value('Valuation output!M2');
    if(!(r>0))return 'Active terminal ROIC must be positive.';
    if(g/r<0||g/r>1)return 'Terminal reinvestment must be between 0% and 100% for this stable-growth case.';
  }
  return null;
}
function calculateValuationSnapshot(s){
  ensureValuationEngines();const overrides=scenarioOverrides(s);valuationScratch.reset(overrides);
  try{const problem=valuationGuard(valuationScratch);if(problem)return {...s,status:'blocked',reason:problem,value:null};
    const value=valuationScratch.value('Valuation output!B33'),operatingValue=valuationScratch.value('Valuation output!B24');
    return {...s,status:'ready',value,operatingValue,terminalShare:valuationScratch.value('Valuation output!B19')/valuationScratch.value('Valuation output!B21')};
  }catch(error){return {...s,status:'blocked',reason:error.message,value:null};}
}
function savedValuationScenarios(){
  if(!valuationScenarioCache)valuationScenarioCache=(valuationPayload()?.scenarios??[]).map(calculateValuationSnapshot);
  return valuationScenarioCache;
}
function footballField(){
  const v=valuationPayload();if(!v)return null;
  const scenarios=savedValuationScenarios();let current=null;
  if(currentCase==='research'&&complete())try{const error=valuationGuard(engine);current=error?{status:'blocked',reason:error}:{status:'ready',value:engine.value('Valuation output!B33'),terminalShare:engine.value('Valuation output!B19')/engine.value('Valuation output!B21')};}catch(error){current={status:'blocked',reason:error.message};}
  const points=scenarios.filter(s=>s.id!=='original'&&s.status==='ready').map(s=>({id:s.id,label:s.label,value:s.value}));
  return {reference:v.reference,original:scenarios.find(s=>s.id==='original'),current,scenarios,rows:[{id:'dcf',label:'DCF scenarios',kind:'dcf',rangeType:'Saved analyst assumptions',points},...(v.methods??[]).filter(m=>m.kind!=='eva').map(m=>({...m,points:(m.scenarios??[]).filter(s=>Number.isFinite(s.value)&&s.status!=='blocked'&&s.status!=='infeasible').map(s=>({id:s.id,label:s.label,value:s.value}))}))]};
}
function dollars(value){return Number.isFinite(value)?'$'+fmt(value):'Unavailable';}
function workbookDownload(){return valuationPayload()?.checks?.workbookCurrent?'<button class="button dark" data-download-workbook="1">Download saved scenario workbook ↓</button>':'<span class="valuation-footnote">The formula workbook needs rebuilding for this revision.</span>';}
function downloadValuationWorkbook(){
  const v=valuationPayload();if(!v?.checks?.workbookCurrent||!v.workbookBase64)return;
  const bytes=Uint8Array.from(atob(v.workbookBase64),character=>character.charCodeAt(0));
  const url=URL.createObjectURL(new Blob([bytes],{type:'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'}));
  const a=document.createElement('a');a.href=url;a.download='wd40_valuation.xlsx';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
}
function rangeLabels(low,high,x,y){
  const compact=high!==low&&x(high.value)-x(low.value)<74;
  if(compact)return `<text x="${(x(low.value)+x(high.value))/2}" y="${y+23}" text-anchor="middle" font-size="9" fill="#68775e">$${fmt(low.value,0)}–${fmt(high.value,0)}</text>`;
  return `<text x="${x(low.value)}" y="${y+23}" text-anchor="middle" font-size="9" fill="#68775e">${esc(dollars(low.value))}</text>${high!==low?`<text x="${x(high.value)}" y="${y+23}" text-anchor="middle" font-size="9" fill="#68775e">${esc(dollars(high.value))}</text>`:''}`;
}
function renderValuation(){
  const v=valuationPayload(),target=$('valuation-content');if(!v||!target)return;
  if(currentCase!=='research'){target.innerHTML='<p class="valuation-empty">The valuation comparisons use the WD-40 FY2025 case. Select WD-40 to inspect them.</p>';$('reverse-content').innerHTML='';$('diligence-content').innerHTML='';return;}
  const field=footballField(),original=field.original,base=field.scenarios.find(s=>s.id==='base');
  const reference=v.reference.price;
  const numbers=field.rows.flatMap(r=>r.points.map(p=>p.value)).concat([reference,original?.value,field.current?.value]).filter(Number.isFinite);
  const max=Math.max(100,...numbers)*1.12,min=Math.min(0,...numbers),width=780,left=205,right=720,top=39,rowHeight=48,height=top+field.rows.length*rowHeight+40;
  const x=value=>left+(value-min)/(max-min)*(right-left),marketX=x(reference);
  const ticks=Array.from({length:6},(_,i)=>min+(max-min)*i/5);
  const rows=field.rows.map((r,i)=>{const y=top+i*rowHeight,ps=[...r.points].sort((a,b)=>a.value-b.value);let graphic='';
    if(ps.length){const low=ps[0],high=ps.at(-1),middle=ps.find(p=>p.id==='base')??ps[Math.floor(ps.length/2)];graphic=`<line x1="${x(low.value)}" x2="${x(high.value)}" y1="${y}" y2="${y}" stroke="${r.kind==='lbo'?'#859b65':'#516f52'}" stroke-width="12" stroke-linecap="round"/><line x1="${x(middle.value)}" x2="${x(middle.value)}" y1="${y-10}" y2="${y+10}" stroke="#253d30" stroke-width="2"/>${rangeLabels(low,high,x,y)}`;}
    else graphic=`<text x="${left}" y="${y+4}" font-size="10" fill="#8a8f80">${esc(['missing_data','unavailable'].includes(r.status)?'Historical inputs unavailable':r.status??'No supported range')}</text>`;
    if(r.id==='dcf'&&field.current?.status==='ready')graphic+=`<circle cx="${x(field.current.value)}" cy="${y}" r="5" fill="#8c6b3e" stroke="#fffefa" stroke-width="2"/>`;
    return `<g data-method="${esc(r.id)}" role="button" tabindex="0" aria-label="Inspect ${esc(r.label)}"><rect x="0" y="${y-17}" width="${width}" height="45" fill="transparent"/><text x="4" y="${y+3}" font-size="11" fill="#29332c">${esc(r.label)}</text>${graphic}</g>`;}).join('');
  target.innerHTML=`<p class="valuation-context"><strong>${dollars(reference)} historical reference · ${esc(v.reference.priceAsOf)}.</strong> FY2025 results and later filings are used retrospectively. Scenario ranges represent chosen assumptions.</p><div class="valuation-summary"><div><span>ORIGINAL 70 INPUTS</span><strong>${dollars(original?.value)}</strong><small>${original?.terminalShare!=null?pct(original.terminalShare)+' terminal value':''}</small></div><div><span>SAVED BASE SCENARIO</span><strong>${dollars(base?.value)}</strong><small>${base?.terminalShare!=null?pct(base.terminalShare)+' terminal value':''}</small></div><div><span>CURRENT REVIEWED DCF</span><strong>${field.current?.status==='ready'?dollars(field.current.value):field.current?.status==='blocked'?'Blocked':'Review pending'}</strong><small>${field.current?.status==='ready'?pct(field.current.terminalShare)+' terminal value':field.current?.reason??'Accept or edit all current inputs.'}</small></div></div><div class="valuation-chart"><svg viewBox="0 0 ${width} ${height}" role="group" aria-label="WD-40 valuation ranges with historical share price">${ticks.map(t=>`<line x1="${x(t)}" x2="${x(t)}" y1="18" y2="${height-27}" stroke="#e4e8dc"/><text x="${x(t)}" y="${height-9}" text-anchor="middle" font-size="9" fill="#818b77">$${fmt(t,0)}</text>`).join('')}<line x1="${marketX}" x2="${marketX}" y1="15" y2="${height-27}" stroke="#8c6b3e" stroke-width="1.5" stroke-dasharray="4 3"/><text x="${marketX}" y="9" text-anchor="middle" font-size="9" fill="#8c6b3e">${dollars(reference)} reference</text>${rows}</svg></div><div class="valuation-legend"><span>Saved range and middle case</span><span class="market-key">Historical price</span><span class="current-key">Current reviewed DCF</span></div><div class="table-scroll"><table class="data-table valuation-table"><thead><tr><th>DCF snapshot</th><th>Value / share</th><th>Terminal share</th><th></th></tr></thead><tbody>${field.scenarios.map(s=>`<tr><td>${esc(s.label)}</td><td>${s.status==='ready'?dollars(s.value):'Blocked'}</td><td>${s.status==='ready'?pct(s.terminalShare):'—'}</td><td><button class="button quiet" data-scenario="${esc(s.id)}">Inspect</button></td></tr>`).join('')}</tbody></table></div><p class="valuation-footnote">Saved scenarios retain their own input snapshots. Applying one previews every replacement and records a single review change. EVA uses the same economics as DCF. Acquisition and financing ranges have different assumptions; they are not averaged.</p><div class="valuation-actions"><button class="button quiet" data-method="sensitivities">Inspect measured sensitivities</button><button class="button quiet" data-method="research">Check operating and WACC evidence</button>${workbookDownload()}</div><p class="valuation-footnote">${esc(v.checks?.excelStatus??'Independent native Excel recalculation has not been performed.')}</p>`;
  renderReverseDcf();renderDiligenceQuestions();
}
function reverseDcf(overrides,price){
  ensureValuationEngines();valuationScratch.reset(overrides);const error=valuationGuard(valuationScratch);if(error)return {status:'blocked',reason:error};
  const initial=valuationScratch.value('Cost of capital worksheet!B12'),terminal=valuationScratch.value('Input sheet!B46'),growth=valuationScratch.value('Valuation output!M2');
  const lower=Math.max(-initial+.0001,growth-terminal+.0001),upper=.2;
  const residual=shift=>{valuationScratch.reset({...overrides,'Cost of capital worksheet!B12':initial+shift,'Input sheet!B46':terminal+shift});return valuationScratch.value('Valuation output!B33')-price;};
  let lo=lower,hi=upper,fl=residual(lo),fh=residual(hi);if(fl*fh>0)return {status:'no_solution',bounds:[lower,upper],residuals:[fl,fh]};
  let middle=0,r=0,iterations=0;for(;iterations<60;iterations++){middle=(lo+hi)/2;r=residual(middle);if(Math.abs(r)<=.000001)break;if(fl*r<=0)hi=middle;else{lo=middle;fl=r;}}
  return {status:'solved',shift:middle,waccInitial:initial+middle,waccTerminal:terminal+middle,residual:r,iterations:iterations+1,bounds:[lower,upper],price};
}
function renderReverseDcf(){
  const v=valuationPayload(),target=$('reverse-content');if(!v||!target||currentCase!=='research')return;
  const current=complete(),inputs=current?{...engine.overrides}:originalValuationOverrides(),key=JSON.stringify([inputs,v.reference.price]);
  if(reverseCache?.key!==key){try{reverseCache={key,result:reverseDcf(inputs,v.reference.price)};}catch(error){reverseCache={key,result:{status:'blocked',reason:error.message}};}}
  const r=reverseCache.result;
  const text=r.status==='solved'?`A parallel shift of <strong>${fmt(r.shift*100,2)} percentage points</strong> gives WACC <strong>${pct(r.waccInitial)} → ${pct(r.waccTerminal)}</strong> at ${dollars(v.reference.price)}. Remaining price residual: $${fmt(r.residual,6)}.`:r.status==='no_solution'?'No solution in the specified feasible WACC-shift range.':esc(r.reason);
  target.innerHTML=`<div class="reverse-summary">${text}</div><p class="valuation-footnote">${current?'Current reviewed operating assumptions':'Original 70-input operating assumptions'} held fixed. This solves a conditional discount-rate path; it does not identify the market’s actual forecast. The mathematical search range may include rates unsupported by the CAPM evidence.</p>${(v.reverseGrids??[]).map(grid=>`<details class="reverse-grid"><summary>${esc(grid.label)} · saved original operating basis</summary><div class="table-scroll"><table class="data-table"><thead><tr><th>${esc(grid.rowLabel)} / ${esc(grid.columnLabel)}</th>${grid.columns.map(c=>`<th>${pct(c)}</th>`).join('')}</tr></thead><tbody>${grid.rows.map(row=>`<tr><td>${pct(row.input)}</td>${row.values.map(n=>`<td class="${n>=v.reference.price?'meets-price':''}">${Number.isFinite(n)?dollars(n):'Blocked'}</td>`).join('')}</tr>`).join('')}</tbody></table></div><p class="valuation-footnote">Highlighted cells meet or exceed the historical reference. Each grid changes only the two named drivers.</p></details>`).join('')}`;
}
function scenarioTransaction(s){
  const overrides=scenarioOverrides(s),statuses={...state.statuses},edits={...state.edits};
  const definitions=[...data.proposals,terminalRoicProposal()],active=overrides['Input sheet!B48']==='Yes';
  for(const p of definitions){
    if(p.cell==='Input sheet!B49'&&!active){delete statuses[p.id];delete edits[p.id];continue;}
    if(Object.hasOwn(overrides,p.cell)){statuses[p.id]=overrides[p.cell]===p.value?'accepted':'edited';if(statuses[p.id]==='edited')edits[p.id]=overrides[p.cell];else delete edits[p.id];}
    else {statuses[p.id]=p.operation==='retain_formula'?'formula':'accepted';delete edits[p.id];}
  }
  const target={};for(const p of definitions){if(statuses[p.id]==='accepted')target[p.cell]=p.value;if(statuses[p.id]==='edited')target[p.cell]=edits[p.id];}
  ensureValuationEngines();valuationScratch.reset(target);const problem=valuationGuard(valuationScratch);if(problem)return {error:problem};
  const changes=[];for(const p of definitions){
    const beforeStatus=status(p),afterStatus=statuses[p.id]??'inactive';
    if(p.cell==='Input sheet!B49'&&!active&&beforeStatus==='proposed')continue;
    const before=beforeStatus==='edited'?state.edits[p.id]:beforeStatus==='formula'&&complete()?engine.safe(p.cell).value:p.value;
    const after=afterStatus==='inactive'?'Inactive':valuationScratch.value(p.cell);
    const restore=afterStatus==='formula'&&['edited','accepted'].includes(beforeStatus);
    if(before!==after||restore)changes.push({p,before,after,restore,afterStatus});
  }
  const value=valuationScratch.value('Valuation output!B33');
  if(Math.abs(value-s.value)>1e-8)return {error:'This snapshot contains an input outside the supported review transaction.'};
  return {statuses,edits,changes,value};
}
function scenarioDetails(id){
  const s=savedValuationScenarios().find(x=>x.id===id);if(!s)return;const target=scenarioTransaction(s);
  dialog(s.label+' scenario',`<div class="question-answer">${esc(s.note??'Saved input snapshot.')}<p style="margin-top:12px">Value per share: <strong>${dollars(s.value)}</strong>${s.terminalShare!=null?' · Terminal value: '+pct(s.terminalShare):''}</p></div><div class="scenario-diff table-scroll"><table class="data-table"><thead><tr><th>Input</th><th>Current / proposed</th><th>Saved scenario</th></tr></thead><tbody>${(target.changes??[]).map(({p,before,after,restore,afterStatus})=>`<tr><td><button class="text-button" data-cell="${esc(p.cell)}">${esc(inputLabel(p.cell))}</button></td><td>${displayValue(p,before)}</td><td>${afterStatus==='inactive'?'Inactive':displayValue(p,after)}${restore?'<br><small>Restore original formula</small>':''}</td></tr>`).join('')||'<tr><td colspan="3">The saved scenario matches current values.</td></tr>'}</tbody></table></div>${target.error?`<p class="error-note">${esc(target.error)}</p>`:`<button class="button dark" data-apply-scenario="${esc(id)}">Apply this complete snapshot to review</button>`}<p class="valuation-footnote">This reviews the complete input set, replaces the differences shown and restores any listed formulas. One undo restores the previous review.</p>`,'SAVED ANALYST SCENARIO');
}
function applyValuationScenario(id){
  const s=savedValuationScenarios().find(x=>x.id===id);if(!s)return {error:'Unknown scenario.'};
  const target=scenarioTransaction(s);if(target.error){announce(target.error);return {error:target.error};}
  pushHistory();state.statuses=target.statuses;state.edits=target.edits;
  addAudit(`Applied ${s.label} scenario`,'Complete saved snapshot applied atomically. '+s.note);
  rebuild();save();if($('detail-dialog').open)closeDialog();renderAll();announce(s.label+' scenario applied. Undo restores the complete previous review.');return {value:engine.value('Valuation output!B33'),revision:state.revision};
}
function valuationSources(ids=[]){
  const v=valuationPayload();const sources=[...(data.sources??[]),...(v.sources??[]),...(v.questions?.sources??[])];
  return ids.map(id=>sources.find(s=>s.id===id)).filter(Boolean);
}
function sourceLinks(ids){return valuationSources(ids).map(s=>`<p class="valuation-footnote"><a href="${esc(s.url??s.downloadUrl??'#')}" target="_blank" rel="noopener">${esc(s.title??s.name??s.id)} ↗</a>${s.asOf?' · '+esc(s.asOf):''}</p>`).join('');}
function researchDetails(){
  const v=valuationPayload(),research=v.research??{},op=research.operatingFacts??{},cap=research.capitalCostEvidence??{},ref=v.reference;
  const common=ref.commonSharesOutstanding,marketCap=common*ref.price,ev=marketCap+ref.debt-ref.cash;
  const metrics=[['Reported revenue',fmt(op.revenue)+' USD m'],['Reported EBIT',fmt(op.reportedEbit)+' USD m'],['Reported EBIT margin',pct(op.reportedEbitMargin)],['R&D-adjusted EBIT',fmt(op.rdCapitalizedEbit)+' USD m'],['R&D-adjusted EBIT margin',pct(op.rdCapitalizedEbitMargin)],['Issuer adjusted EBITDA',fmt(op.issuerAdjustedEbitda)+' USD m'],['Operating EBITDA proxy used in buyer models',fmt(op.operatingEbitdaFromEbitPlusCashFlowDa)+' USD m'],['10-year Treasury par yield / 2025-08-29',pct(cap.treasury10y?.value)],['Published mature-market ERP estimate / July 2025',pct(cap.matureMarketErpHistorical?.value)],['Published US ERP estimate / July 2025',pct(cap.usErpHistorical?.value)]];
  const regional=savedValuationScenarios().filter(s=>s.segmentBuild);
  const ids=[...(op.sourceIds??[]),...(cap.treasury10y?.sourceIds??[]),...(cap.matureMarketErpHistorical?.sourceIds??[]),ref.shareSourceId,ref.priceSourceId];
  dialog('Operating and WACC evidence',`<div class="table-scroll"><table class="data-table"><tbody>${metrics.map(([name,value])=>`<tr><td>${esc(name)}</td><td>${esc(value)}</td></tr>`).join('')}</tbody></table></div><p class="question-answer">The original margin capitalizes R&D: reported EBIT plus $8.7m current R&D, less $6.43m three-year amortization. The company’s 25% long-term target refers to adjusted EBITDA.</p><p class="scenario-notes">The initial October 2025 FY2026 outlook guides to 5–9% growth on its pro forma and currency basis. The 6–9% outlook belongs to the July 2026 revision and is excluded from these historical inputs.</p><div class="detail-block" style="margin-top:15px"><h3>Common shares and the DCF dilution convention</h3><p>${fmt(common,6)}m common shares at FY2025 year-end imply ${fmt(marketCap)} USD m capitalization at the historical reference. Adding ${fmt(ref.debt)} USD m borrowings and subtracting ${fmt(ref.cash)} USD m cash gives ${fmt(ev)} USD m enterprise value, or ${fmt(ev/op.reportedEbit)}× reported EBIT. This combines the historical reference with period-end financials retrospectively.</p><p>The DCF uses ${fmt(ref.valuationShareProxy??ref.valuationShareCount,6)}m shares including its explicit award-dilution proxy.</p></div><p class="question-answer">WACC is still an analyst assumption. Available Treasury and ERP observations do not establish a complete capital-cost estimate.</p>${(cap.missing??[]).map(note=>`<p class="scenario-notes">${esc(note)}</p>`).join('')}<div class="table-scroll" style="margin-top:15px"><table class="data-table"><thead><tr><th>Region / FY2025 USD m</th>${regional.map(s=>`<th>${esc(s.label)} growth</th>`).join('')}</tr></thead><tbody>${(op.regions??[]).map(r=>`<tr><td>${esc(r.label)} / ${fmt(r.revenue)}</td>${regional.map(s=>`<td>${pct(s.segmentBuild.regionGrowthAssumptions[r.id])}</td>`).join('')}</tr>`).join('')}</tbody></table></div><p class="valuation-footnote">Regional growth rates are analyst assumptions. Their aggregate first-year growth and years-2–5 CAGR feed the Ginzu scenarios. The compression preserves years 1 and 5, with annual revenue residuals disclosed in the workbook.</p>${sourceLinks([...new Set(ids.filter(Boolean))])}`,'SOURCE BASIS');
}
function methodDetails(id){
  const v=valuationPayload();if(id==='dcf'){dialog('DCF scenario assumptions',`<p class="scenario-notes">Frozen analyst snapshots are calculated with the original Ginzu formulas. Their values are conditional on their own growth, margins, reinvestment and capital costs.</p>${savedValuationScenarios().map(s=>`<button class="result-row" data-scenario="${esc(s.id)}"><div><strong>${esc(s.label)}</strong><small>${esc(s.note)}</small></div><span>${dollars(s.value)} ↗</span></button>`).join('')}`,'VALUATION METHOD');return;}
  if(id==='sensitivities'){dialog('Measured changes to original DCF',`<div class="table-scroll"><table class="data-table"><thead><tr><th>Diagnostic change</th><th>Value / share</th><th>Change</th></tr></thead><tbody>${v.measurement.sensitivities.map(s=>`<tr><td>${esc(s.label)}</td><td>${dollars(s.value)}</td><td>${s.delta>=0?'+':''}${dollars(s.delta)}</td></tr>`).join('')}</tbody></table></div><p class="valuation-footnote">These are separate conditional experiments. Their effects are not additive. Original baseline: ${dollars(v.measurement.original.value)}.</p>`,'ORIGINAL ENGINE MEASUREMENTS');return;}
  if(id==='research'){researchDetails();return;}
  const m=(v.methods??[]).find(x=>x.id===id);if(!m)return;
  dialog(m.label,`<p class="scenario-notes">${esc(m.rangeType??m.kind)} · ${esc(m.status.replaceAll('_',' '))}</p>${(m.scenarios??[]).map(s=>`<div class="detail-block" style="margin-top:12px"><h3>${esc(s.label)} · ${dollars(s.value)}</h3><p>${esc(s.note??'')}</p>${Object.entries(s.assumptions??{}).map(([key,value])=>`<p>${esc(key.replace(/([A-Z])/g,' $1'))}: ${esc(typeof value==='number'?short(value):value)}</p>`).join('')}${s.status&&s.status!=='ready'?`<p>${esc(s.status)}</p>`:''}</div>`).join('')}${(m.limitations??[]).map(t=>`<p class="valuation-footnote">${esc(t)}</p>`).join('')}${sourceLinks(m.sourceIds??[])}`,'VALUATION METHOD');
}
function renderDiligenceQuestions(){
  const q=valuationPayload()?.questions,target=$('diligence-content');if(!q||!target)return;
  target.innerHTML=(q.parents??[]).map(parent=>`<details class="question-group"><summary>${esc(parent.question??parent.label)}</summary><p>${esc(parent.description??'')}</p>${(q.questions??[]).filter(leaf=>leaf.parentId===parent.id).map(leaf=>`<button class="question-leaf" data-question="${esc(leaf.id)}"><strong>${esc(leaf.question)}</strong><small>${esc(leaf.category)} · ${esc(leaf.benchmark?.name??leaf.benchmark?.dataset??'Derived task')} ${esc(leaf.benchmark?.recordId??'')} · ${esc((leaf.status??'').replaceAll('_',' '))}</small></button>`).join('')}</details>`).join('');
}
function questionDetails(id){
  const q=valuationPayload()?.questions?.questions?.find(x=>x.id===id);if(!q)return;
  const cells=q.cellIds??[],benchmark=q.benchmark??{};
  const cellsHtml=cells.map(cell=>{let value='Review pending';if(complete()){const r=engine.safe(cell);value=r.error??short(r.value);}else{const p=proposalFor(cell);if(p)value=displayValue(p,status(p)==='edited'?state.edits[p.id]:p.value);}return `<button class="result-row" data-cell="${esc(cell)}"><div><strong>${esc(inputLabel(cell))}</strong><small>${esc(cell)}</small></div><span>${value} ↗</span></button>`;}).join('');
  const answer=typeof q.answer==='string'?q.answer:JSON.stringify(q.answer??'No answer established.');
  dialog(q.question,`<span class="valuation-tag">${esc(q.category)}</span><span class="valuation-tag">${esc(q.status)}</span><div class="question-answer">${esc(answer)}</div><p class="scenario-notes">${esc(q.answerBasis??valuationPayload()?.questions?.answerBasis??'Historical answers describe the original proposal snapshot. Current linked cells below reflect the review state.')} ${esc(q.note??'')}</p>${cellsHtml}${sourceLinks(q.sourceIds??[])}${q.resolution?`<div class="detail-block" style="margin-top:16px"><h3>Resolution rule</h3><p>${esc(typeof q.resolution==='string'?q.resolution:JSON.stringify(q.resolution))}</p></div>`:''}<details class="question-lineage"><summary>Benchmark lineage and WD-40 adaptation</summary><p>${esc(benchmark.name??benchmark.dataset)} · ${esc(benchmark.recordId)} · ${esc(benchmark.version??'')}</p><p>${esc(benchmark.originalQuestion??benchmark.originalText??'')}</p><p>${esc(benchmark.adaptationNote??'Adapted for WD-40. This is not a score on the source benchmark.')}</p></details>`,'DILIGENCE QUESTION');
}
function bindValuation(){
  document.addEventListener('click',event=>{const node=event.target.closest('[data-method],[data-scenario],[data-apply-scenario],[data-question],[data-download-workbook]');if(!node)return;if(node.dataset.downloadWorkbook)downloadValuationWorkbook();else if(node.dataset.method)methodDetails(node.dataset.method);else if(node.dataset.scenario)scenarioDetails(node.dataset.scenario);else if(node.dataset.applyScenario)applyValuationScenario(node.dataset.applyScenario);else if(node.dataset.question)questionDetails(node.dataset.question);});
  document.addEventListener('keydown',event=>{if((event.key==='Enter'||event.key===' ')&&event.target.matches('g[data-method]')){event.preventDefault();methodDetails(event.target.dataset.method);}});
  Object.assign(window.sunesis,{valuation:valuationPayload(),footballField,applyScenario:applyValuationScenario,scenarioDetails,questionDetails,reverseDcf,WorkbookEngine});
}
