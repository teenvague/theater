export function todayNY(date = new Date()) { return new Intl.DateTimeFormat('en-CA',{timeZone:'America/New_York',year:'numeric',month:'2-digit',day:'2-digit'}).format(date); }
export function selectShows(shows, {mode='now',query='',venue='',type='',today=todayNY()}={}) {
 const soon=new Date(today+'T12:00:00Z'); soon.setUTCDate(soon.getUTCDate()+30); const limit=soon.toISOString().slice(0,10);
 return shows.filter(s=>s.status!=='closed' && (!s.closingDate||s.closingDate>=today))
 .filter(s=>mode==='all'||(mode==='now'?s.startDate<=today:s.startDate>today&&s.startDate<=limit))
 .filter(s=>(!venue||s.venue===venue)&&(!type||s.types.includes(type)))
 .filter(s=>[s.title,s.credits,s.venue,s.neighborhood,...s.types].join(' ').toLowerCase().includes(query.trim().toLowerCase()))
 .sort((a,b)=>(mode==='soon'?a.startDate.localeCompare(b.startDate):(a.closingDate||'9999').localeCompare(b.closingDate||'9999'))||b.startDate.localeCompare(a.startDate)||a.title.localeCompare(b.title));
}
export function flatten(productions){return productions.flatMap(p=>p.engagements.map(e=>({...p,...e,productionId:p.id})));}
export function range(s){const f=d=>new Intl.DateTimeFormat('en-US',{month:'short',day:'numeric',year:'numeric',timeZone:'UTC'}).format(new Date(d+'T12:00:00Z'));return f(s.startDate)+' – '+(s.closingDate?f(s.closingDate):'Open run');}
