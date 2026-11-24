import React,{useEffect,useState} from 'react';
import {API} from './gisApi.js';
const ENDPOINTS={preview:'/api/v1/scim/processing/preview',plan:'/api/v1/scim/jobs/plan'};
function resolveSchema(schema,defs,depth=0){
 if(!schema||depth>8)return {};
 if(schema.$ref)return resolveSchema(defs[schema.$ref.split('/').pop()],defs,depth+1);
 if(schema.allOf?.length===1)return resolveSchema(schema.allOf[0],defs,depth+1);
 return schema;
}
function buildTemplate(schema,defs,depth=0){
 const s=resolveSchema(schema,defs);
 if(depth>6)return null;
 if(s.enum)return s.enum[0]??null;
 if(s.default!==undefined)return s.default;
 if(s.type==='object'||s.properties){
  const obj={};for(const key of s.required||[])if(s.properties?.[key])obj[key]=buildTemplate(s.properties[key],defs,depth+1);return obj;
 }
 if(s.type==='array')return [];
 if(s.type==='number'||s.type==='integer')return s.minimum??0;
 if(s.type==='boolean')return false;
 if(s.format==='date-time')return '2026-11-09T00:00:00Z';
 return '';
}
function formatError(data,status){
 const detail=data?.detail;
 return Array.isArray(detail)?detail.map(x=>`${(x.loc||[]).join('.')}: ${x.msg}`).join('; '):typeof detail==='string'?detail:`Request failed (${status})`;
}
export default function SCIMJobPlanning({request}){
 const [spec,setSpec]=useState(null),[schemaError,setSchemaError]=useState('');
 const [payload,setPayload]=useState(''),[busy,setBusy]=useState(''),[error,setError]=useState('');
 const [preview,setPreview]=useState(null),[planned,setPlanned]=useState(null);
 useEffect(()=>{
  const controller=new AbortController();
  fetch(`${API}/openapi.json`,{signal:controller.signal}).then(r=>{if(!r.ok)throw Error(`OpenAPI ${r.status}`);return r.json()}).then(s=>{
   if(controller.signal.aborted)return;
   const request=s.paths?.[ENDPOINTS.plan]?.post?.requestBody?.content?.['application/json']?.schema;
   if(!request)throw Error('PlanRequest schema missing from backend OpenAPI');
   setSpec(s);setPayload(JSON.stringify(buildTemplate(request,s.components?.schemas||{}),null,2));
  }).catch(e=>{if(e.name!=='AbortError'&&!controller.signal.aborted)setSchemaError(e.message)});
  return()=>controller.abort();
 },[]);
 const planSchema=spec?.paths?.[ENDPOINTS.plan]?.post?.requestBody?.content?.['application/json']?.schema;
 const resolved=resolveSchema(planSchema,spec?.components?.schemas||{});
 const required=resolved.required||[];
 async function execute(mode){
  setError('');if(mode==='preview')setPreview(null);else setPlanned(null);
  if(!spec){setError('Backend request schema unavailable; operation disabled.');return;}
  let parsed;
  try{parsed=JSON.parse(payload);if(!parsed||Array.isArray(parsed)||typeof parsed!=='object')throw Error('Request must be a JSON object');
   for(const field of required)if(parsed[field]===undefined||parsed[field]===null||parsed[field]==='')throw Error(`Required field missing: ${field}`);
  }catch(e){setError(e.message);return;}
  setBusy(mode);
  try{
   const response=await request(ENDPOINTS[mode],{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(parsed)});
   const data=await response.json().catch(()=>null);
   if(!response.ok)throw Error(formatError(data,response.status));
   if(mode==='preview')setPreview(data);else setPlanned(data);
  }catch(e){setError(e.message)}finally{setBusy('')}
 }
 return <div className="scim-panel scim-modern-planning">
  <h3>Processing preview &amp; job planning</h3>
  <p className="scim-muted">Review the request generated from the backend schema before submitting.</p>
  <div className="scim-planning-guide">

  <article>
    <strong>1. Prepare request</strong>
    <p>Review all required fields in the request editor.</p>
  </article>

  <article>
    <strong>2. Preview processing</strong>
    <p>Inspect the processing preview without creating a job.</p>
  </article>

  <article>
    <strong>3. Plan job</strong>
    <p>Submit the request. This may create a persistent backend job.</p>
  </article>

</div>

{schemaError&&<p className="scim-error" role="alert">Cannot load PlanRequest: {schemaError}</p>}
  {!spec&&!schemaError&&<p className="scim-muted">Loading backend schema...</p>}
  {spec&&<>
   <p className="scim-muted">Required fields: {required.join(', ')||'None listed'}</p>
   <label className="scim-json-label" htmlFor="scim-plan-json">Job planning request (JSON)</label>
   <textarea id="scim-plan-json" className="scim-textarea scim-plan-editor" spellCheck={false} disabled={!!busy} value={payload} onChange={e=>setPayload(e.target.value)}/>
   <div className="scim-plan-actions">
    <button type="button" disabled={!!busy} onClick={()=>execute('preview')}>{busy==='preview'?'Previewing...':'Preview processing'}</button>
    <button type="button" className="scim-primary-plan" disabled={!!busy} onClick={()=>execute('plan')}>{busy==='plan'?'Planning...':'Plan job'}</button>
   </div>
  </>}
  {error&&<p className="scim-error" role="alert">{error}</p>}
  {preview!==null&&<div className="scim-results"><h3>Processing preview</h3><pre className="scim-json">{JSON.stringify(preview,null,2)}</pre></div>}
  {planned!==null&&<div className="scim-results" role="status"><h3>Job planning result</h3><pre className="scim-json">{JSON.stringify(planned,null,2)}</pre></div>}
 </div>;
}
