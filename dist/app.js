import {TextDropdown} from './dropdown.js';
import {flatten,selectShows,range,todayNY} from './model.js';
const $=s=>document.querySelector(s);const state={mode:'now',query:'',venue:'',type:''};let data,shows=[];
function el(tag,cls,text){const n=document.createElement(tag);if(cls)n.className=cls;if(text)n.textContent=text;return n;}
function safeURL(value){if(!value)return null;try{const u=new URL(value,location.href);return ['http:','https:'].includes(u.protocol)?u.href:null;}catch{return null;}}
const dropdowns={};
for(const [id,label,all] of [['venue','Venue','All venues'],['type','Type','All types']])dropdowns[id]=new TextDropdown($('#'+id),label,all,value=>{state[id]=value;if(data)render();});
function render(){const results=selectShows(shows,{...state,today:data.demo?data.asOf:todayNY()});
for(const b of document.querySelectorAll('[data-mode]'))b.setAttribute('aria-pressed',String(b.dataset.mode===state.mode));$('#shows').replaceChildren();$('#status').textContent=(data.demo?'Demo listings · illustrative dates and stock images · ':'')+results.length+(state.query.trim()?' search results':' productions');
 for(const s of results){const a=el('a','show');a.href=safeURL(s.url)||'#';a.target='_blank';a.rel='noopener noreferrer';a.setAttribute('aria-label',s.title+' at '+s.venue+' (opens external site)');
 const img=el('img','thumb');img.alt=s.imageAlt||'';img.loading='lazy';img.width=300;img.height=200;img.src=safeURL(s.image)||'';img.onerror=()=>img.replaceWith(el('span','thumb image-missing','Image unavailable'));
 const prod=el('div','production');prod.append(el('h2','',s.title),el('div','credits',s.credits));if(s.description){const summary=el('p','summary',s.description);summary.title=s.description;prod.append(summary);}const venue=el('div','venue-cell');venue.append(el('div','venue',s.venue),el('div','neighborhood',s.neighborhood));const dates=el('div','date-cell');dates.append(el('div','dates',range(s)),el('div','tags',s.types.join(' · ')));const arrow=el('span','arrow','↗');arrow.setAttribute('aria-hidden','true');a.append(img,prod,venue,dates,arrow);$('#shows').append(a);}
 if(!results.length)$('#shows').append(el('p','empty','No productions found.'));
}
async function load(){try{const r=await fetch('./data/shows.json',{cache:'no-cache'});if(!r.ok)throw Error();data=await r.json();shows=flatten(data.productions);for(const [id,values] of [['venue',shows.map(s=>s.venue)],['type',shows.flatMap(s=>s.types)]]){dropdowns[id].setOptions([...new Set(values)].sort());}render();}catch{$('#status').textContent='Unable to load productions. Refresh the page to try again.';}}
$('#search').addEventListener('input',e=>{state.query=e.target.value;if(state.query.trim()){state.mode='all';state.venue=state.type='';dropdowns.venue.setValue('');dropdowns.type.setValue('');}if(data)render();});
for(const b of document.querySelectorAll('[data-mode]'))b.addEventListener('click',()=>{state.mode=b.dataset.mode;state.query='';$('#search').value='';if(data)render();});
$('#reset').addEventListener('click',()=>{$('#search').value='';Object.assign(state,{query:'',venue:'',type:'',mode:'now'});dropdowns.venue.setValue('');dropdowns.type.setValue('');if(data)render();});load();

// Reclassify an open tab after midnight or when returning to it.
let calendarDay=todayNY();
setInterval(()=>{const day=todayNY();if(day!==calendarDay){calendarDay=day;if(data)render();}},60000);
document.addEventListener('visibilitychange',()=>{if(!document.hidden&&data)render();});
