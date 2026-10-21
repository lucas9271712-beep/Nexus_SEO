'use strict';
let report=null;
const el=id=>document.getElementById(id);
const clean=s=>String(s??'');
function node(tag,text){const n=document.createElement(tag);n.textContent=clean(text);return n;}
function show(){
 if(!report)return;
 el('score').textContent=report.score;el('pages').textContent=report.pages_crawled;
 el('high').textContent=report.issues.high;el('other').textContent=report.issues.medium+report.issues.low;
 el('robots').textContent=report.resources['robots.txt'].available?'HTTP 200':'CHECK';
 el('sitemap').textContent=report.resources['sitemap.xml'].available?'HTTP 200':'CHECK';
 el('site').textContent=report.site;el('site').href=report.site;
 el('date').textContent=new Date(report.generated_at).toLocaleString();
 el('coverage').textContent=`${report.pages_crawled} of maximum ${report.page_limit} pages`;
 const rows=el('rows');rows.replaceChildren();
 const term=el('search').value.toLowerCase();
 const filtered=report.pages.filter(p=>(p.url+' '+p.title).toLowerCase().includes(term));
 for(const p of filtered){const tr=document.createElement('tr');const td=document.createElement('td');const a=node('a',p.url);a.href=p.url;a.target='_blank';a.rel='noopener noreferrer';td.append(a);tr.append(td,node('td',p.status),node('td',p.issues.length),node('td',p.title||'Missing title'));rows.append(tr);}
 if(!filtered.length){const tr=document.createElement('tr');const td=node('td','No matching pages');td.colSpan=4;tr.append(td);rows.append(tr);}
 const actions=el('actions');actions.replaceChildren();const findings=report.pages.flatMap(p=>p.issues.map(i=>({...i,url:p.url})));findings.sort((a,b)=>({high:0,medium:1,low:2}[a.severity]-{high:0,medium:1,low:2}[b.severity]));
 if(!findings.length)actions.append(node('p','No issues detected within current audit coverage.'));
 for(const issue of findings.slice(0,7)){const div=document.createElement('div');div.className='action';div.append(node('strong',issue.severity.toUpperCase()+' · '+issue.message),node('div',issue.url));actions.append(div);}
}
async function load(){try{const response=await fetch('data/report.json?ts='+Date.now(),{cache:'no-store'});if(!response.ok)throw Error('Report unavailable (HTTP '+response.status+'). Run the audit workflow first.');report=await response.json();el('error').hidden=true;show();}catch(err){el('error').textContent=err.message;el('error').hidden=false;el('rows').replaceChildren(node('tr','Report not available yet.'));}}
el('search').addEventListener('input',show);el('refresh').addEventListener('click',load);load();
