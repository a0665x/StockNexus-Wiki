// Only records returned by the frozen source gateway can be read or highlighted.
export const phases = {prepare:'資料準備',opening:'立論',rebuttal:'攻防',regroup:'隊內重整',deepen:'深化攻防',closing:'總答辯',judge:'評審裁決'};
export const bookFor = item => ['L1','L2'].includes(item.layer) ? 'wiki' : 'news';
export function index(packet) {
  return [
    ...packet.sources.map(s => ({id:s.id, book:'news', title:s.title || s.id})),
    ...packet.context.map((c,i) => ({id:'K'+(i+1), book:bookFor(c), title:c.title || c.statement.slice(0,160)}))
  ];
}
export function readPacket(packet, ids) {
  const catalog=index(packet);
  if (!Array.isArray(ids) || ids.length>8 || ids.some(id=>!catalog.some(item=>item.id===id))) {
    throw Error('查閱的索引超出本庭資料範圍');
  }
  const keys=new Set(ids), context=[];
  packet.context.forEach((item,i)=>{
    const id='K'+(i+1);
    if(keys.has(id)){
      context.push({...item,key:id});
      for(const ref of item.sources||[])keys.add(ref);
    }
  });
  return {context,sources:packet.sources.filter(s=>keys.has(s.id))};
}
export function decision(run) {
  const weights={pro:0,con:0,tie:0,abstain:0}, ballots=[];
  for(const [seat,p] of Object.entries(run.seats).filter(([key])=>key.startsWith('judge-'))){
    const reviews=run.turns.find(t=>t.seat===seat)?.reviews||[];
    const points={pro:0,con:0}, counts={pro:0,con:0};
    for(const review of reviews){
      const speech=run.turns.find(t=>t.claim?.id===review.claim);
      if(!speech)continue;
      const side=speech.seat.split('-')[0];
      counts[side]++;
      const quality=Object.values(review.scores).reduce((a,b)=>a+b,0);
      if(review.finding==='supported')points[side]+=1+quality/16;
      if(review.finding==='contradicted')points[side]-=1;
    }
    for(const side of ['pro','con'])if(counts[side])points[side]/=counts[side];
    let choice='abstain';
    if(counts.pro && counts.con && reviews.some(r=>r.finding==='supported')){
      choice=points.pro===points.con?'tie':points.pro>points.con?'pro':'con';
    }
    weights[choice]+=p.weight;
    ballots.push({seat,choice,points});
  }
  const total=Object.values(weights).reduce((a,b)=>a+b,0);
  const winner=['pro','con','tie'].find(s=>weights[s]>total/2)||'undecided';
  return {winner,weights,ballots,total};
}
export function instructions(stage,task) {
  if(task==='research')return '依據題目與來源目錄指定要實際調閱的資料，最多 8 筆。說明查閱目的、預判對方假設，將工作簡報交給同隊規劃員。回傳 {"ids":["E1","K1"],"note":"..."}，無可用資料時 ids 為空。';
  if(task==='brief')return '閱讀同隊簡報與調閱的材料。提出可公開檢驗的策略摘要、攻防路線與需要追查的問題。回傳 {"note":"..."}。';
  if(stage==='judge')return '獨立評審。逐一核對所有公開命題的原文、關聯與時序。可判定雙方均缺乏依據。回傳 {"reviews":[{"claim":"C1","finding":"supported|contradicted|insufficient|abstain","citations":[{"id":"E1","quote":"逐字原句"}],"scores":{"credibility":0,"logic":0,"rebuttal":0,"completeness":0},"reason":"..."}]}。每項分數 0–4。';
  const objective={opening:'由原始資料立論，提出一項可檢驗主張。',rebuttal:'針對對手上一個具體論點反擊，同時防守己方的假設。',deepen:'針對上一個反駁深化論證，檢驗替代解釋與失效條件。',closing:'總結可成立的路線，回應對方最強異議與仍未解決的問題。'}[stage];
  return objective+' 有 reply_target 時必須在 responds_to 指定該 ID 並具體說明如何回應。在攻防後希望總答辯員召集隊內重整才設 regroup 為 true。回傳 {"statement":"...","reason":"...","responds_to":null,"regroup":false,"citations":[{"id":"E1","quote":"逐字原句"}]}。';
}
