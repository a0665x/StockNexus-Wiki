/* Inclusive UTC dates, calendar-month shortcuts bounded by the server's 366-day limit. */
(function(root){
  const DAY=86400000,MAX_DAYS=366;
  const iso=date=>date.toISOString().slice(0,10);
  function quickRange(months,now=new Date()){
    if(![3,6,9,12].includes(Number(months)))throw new RangeError('Unsupported quick range');
    const end=new Date(iso(now)+'T00:00:00Z');
    const target=new Date(Date.UTC(end.getUTCFullYear(),end.getUTCMonth()-Number(months),1));
    const lastDay=new Date(Date.UTC(target.getUTCFullYear(),target.getUTCMonth()+1,0)).getUTCDate();
    target.setUTCDate(Math.min(end.getUTCDate(),lastDay));
    // Exclude the matching anniversary day, include today: at most 366 days even across leap years.
    const start=new Date(target.getTime()+DAY);
    return {start:iso(start),end:iso(end),days:Math.round((end-start)/DAY)+1};
  }
  function init($,now=()=>new Date()){
    let onChange=()=>{},mode='custom',months=3,custom={start:$('start').value,end:$('end').value};
    function bounds(){
      const today=iso(now()), start=$('start'), end=$('end');
      const last=end.value && end.value<today ? end.value : today;
      start.max=last;
      start.min=quickRange(12,new Date(last+'T00:00:00Z')).start;
      end.min=start.value;
      end.max=today;
      if(start.value){
        const anniversary=new Date(start.value+'T00:00:00Z');
        anniversary.setUTCFullYear(anniversary.getUTCFullYear()+1);
        const latest=iso(new Date(anniversary.getTime()-DAY));
        if(latest<today)end.max=latest;
      }
    }
    function refresh(){if(mode==='quick'){const range=quickRange(months,now());$('start').value=range.start;$('end').value=range.end;}bounds();$('dateRangeSummary').textContent=$('start').value+' → '+$('end').value+' UTC';onChange();}
    function paint(){const quick=mode==='quick';$('dateMode').classList.toggle('quick',quick);$('dateCustom').setAttribute('aria-pressed',String(!quick));$('dateQuick').setAttribute('aria-pressed',String(quick));$('quickDates').hidden=!quick;$('start').readOnly=quick;$('end').readOnly=quick;for(const m of [3,6,9,12])$('months-'+m).setAttribute('aria-pressed',String(m===months));refresh();}
    function setMode(next){if(next===mode){refresh();return;}if(mode==='custom')custom={start:$('start').value,end:$('end').value};mode=next;if(mode==='custom'){$('start').value=custom.start;$('end').value=custom.end;}paint();}
    $('dateCustom').onclick=()=>setMode('custom');$('dateQuick').onclick=()=>setMode('quick');
    for(const m of [3,6,9,12])$('months-'+m).onclick=()=>{months=m;paint();};
    for(const id of ['start','end'])for(const event of ['input','change'])$(id).addEventListener(event,()=>{if(mode==='custom')custom={start:$('start').value,end:$('end').value};refresh();});
    paint();
    return {refresh,state:()=>({mode,months,custom:{...custom}}),onChange(fn){onChange=fn;},restore(saved){
      if(!saved||!['custom','quick'].includes(saved.mode)||![3,6,9,12].includes(saved.months)||!saved.custom||!['start','end'].every(k=>typeof saved.custom[k]==='string'&&(!saved.custom[k]||/^\d{4}-\d{2}-\d{2}$/.test(saved.custom[k]))))return;
      mode=saved.mode;months=saved.months;custom={...saved.custom};$('start').value=custom.start;$('end').value=custom.end;paint();
    },setCustom(){mode='custom';custom={start:$('start').value,end:$('end').value};paint();},mode:()=>mode};
  }
  const api={quickRange,init,MAX_DAYS};root.AtlasDates=api;if(typeof module!=='undefined'&&module.exports)module.exports=api;
})(globalThis);
