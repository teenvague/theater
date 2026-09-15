import {TextDropdown} from './dropdown.js?v=20260915-focus';
import {flatten,selectShows,range,todayNY} from './model.js';
const $=s=>document.querySelector(s);const state={mode:'now',query:'',venue:''};let data,shows=[];
function el(tag,cls,text){const n=document.createElement(tag);if(cls)n.className=cls;if(text)n.textContent=text;return n;}
function safeURL(value){if(!value)return null;try{const u=new URL(value,location.href);return ['http:','https:'].includes(u.protocol)?u.href:null;}catch{return null;}}
const dropdowns={};
function fitDescriptions(){
 if(!window.matchMedia('(min-width:801px)').matches)return;
 for(const row of document.querySelectorAll('.show')){
  const summary=row.querySelector('.summary');if(!summary)continue;
  const available=row.querySelector('.thumb').getBoundingClientRect().height-row.querySelector('.production-heading').getBoundingClientRect().height-6;
  const lineHeight=parseFloat(getComputedStyle(summary).lineHeight);
  summary.style.setProperty('--summary-lines',Math.max(2,Math.floor(available/lineHeight)));
 }
}
new ResizeObserver(fitDescriptions).observe($('#shows'));
document.fonts.ready.then(fitDescriptions);
for(const [id,label,all] of [['venue','Venue','All venues']])dropdowns[id]=new TextDropdown($('#'+id),label,all,value=>{state[id]=value;if(data)render();});
function render(){const results=selectShows(shows,{...state,today:data.demo?data.asOf:todayNY()});
for(const b of document.querySelectorAll('[data-mode]'))b.setAttribute('aria-pressed',String(b.dataset.mode===state.mode));$('#shows').replaceChildren();$('#status').textContent=(data.demo?'Demo listings · illustrative dates and stock images · ':'')+results.length+(state.query.trim()?' search results':' productions');
 for(const s of results){const a=el('a','show');a.href=safeURL(s.url)||'#';a.target='_blank';a.rel='noopener noreferrer';a.setAttribute('aria-label',s.title+' at '+s.venue+' (opens external site)');
 const img=el('img','thumb');img.alt=s.imageAlt||'';img.loading='lazy';img.width=300;img.height=300;img.src=safeURL(s.image)||'';img.onerror=()=>img.replaceWith(el('span','thumb image-missing','Image unavailable'));
 const prod=el('div','production');const heading=el('div','production-heading');heading.append(el('h2','',s.title),el('div','credits',s.credits));prod.append(heading);if(s.description){const summary=el('p','summary',s.description);summary.title=s.description;prod.append(summary);}const venue=el('div','venue-cell');venue.append(el('div','venue',s.venue),el('div','neighborhood',s.neighborhood));const dates=el('div','date-cell');dates.append(el('div','dates',range(s)),el('div','tags',s.types.join(' · ')));const arrow=el('span','arrow','↗');arrow.setAttribute('aria-hidden','true');a.append(img,prod,venue,dates,arrow);$('#shows').append(a);}
 if(!results.length)$('#shows').append(el('p','empty','No productions found.'));
 fitDescriptions();
}
async function load(){try{const r=await fetch('./data/shows.json',{cache:'no-cache'});if(!r.ok)throw Error();data=await r.json();shows=flatten(data.productions);for(const [id,values] of [['venue',shows.map(s=>s.venue)]]){dropdowns[id].setOptions([...new Set(values)].sort());}render();}catch{$('#status').textContent='Unable to load productions. Refresh the page to try again.';}}
$('#search').addEventListener('input',e=>{state.query=e.target.value;if(state.query.trim()){state.mode='all';state.venue='';dropdowns.venue.setValue('');}if(data)render();});
for(const b of document.querySelectorAll('[data-mode]'))b.addEventListener('click',()=>{state.mode=b.dataset.mode;state.query='';$('#search').value='';if(data)render();});
$('#reset').addEventListener('click',()=>{$('#search').value='';Object.assign(state,{query:'',venue:'',mode:'now'});dropdowns.venue.setValue('');if(data)render();});load();

// Reclassify an open tab after midnight or when returning to it.
let calendarDay=todayNY();
setInterval(()=>{const day=todayNY();if(day!==calendarDay){calendarDay=day;if(data)render();}},60000);
document.addEventListener('visibilitychange',()=>{if(!document.hidden&&data)render();});
