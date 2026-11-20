
import React,{useCallback,useEffect,useState} from 'react';
import ParcelMap from './ParcelMap.jsx';
import {useAuth} from './AuthContext.jsx';
import {ownershipLabel,validateOwnerSelection} from './ownershipUtils.js';

const EMPTY={external_id:'',village_code:'',area_hectares:''};
const PAGE_SIZE=50;

async function parseResponse(response){
 const data=await response.json().catch(()=>null);
 if(!response.ok){
  const detail=data?.detail;
  const message=Array.isArray(detail)
   ?detail.map(x=>x.msg||'Invalid field').join('; ')
   :typeof detail==='string'?detail:`Request failed (${response.status})`;
  throw new Error(message);
 }
 return data;
}

export default function ParcelRegistry(){
 const {session,request}=useAuth();
 const [parcels,setParcels]=useState([]);
 const [villages,setVillages]=useState([]);
 const [farmers,setFarmers]=useState([]);
 const [ownerDrafts,setOwnerDrafts]=useState({});
 const [ownerBusy,setOwnerBusy]=useState('');
 const [form,setForm]=useState(EMPTY);
 const [search,setSearch]=useState('');
 const [appliedSearch,setAppliedSearch]=useState('');
 const [page,setPage]=useState(0);
 const [hasMore,setHasMore]=useState(false);
 const [selected,setSelected]=useState(null);
 const [loading,setLoading]=useState(true);
 const [saving,setSaving]=useState(false);
 const [error,setError]=useState('');
 const [success,setSuccess]=useState('');
 const [formError,setFormError]=useState('');

 const refresh=useCallback(async(signal,targetPage=page,searchTerm=appliedSearch)=>{
  if(!session)return;
  const query=new URLSearchParams({limit:String(PAGE_SIZE+1),offset:String(targetPage*PAGE_SIZE)});
  if(searchTerm)query.set('search',searchTerm);
  const parcelData=await request(`/api/v1/parcels?${query}`,{signal}).then(parseResponse);
  const villageData=session.principal.role==='farmer'?[]:await request('/api/v1/villages',{signal}).then(parseResponse);
  const farmerData=['admin','gis_operator'].includes(session.principal.role)?await request('/api/v1/users/farmers',{signal}).then(parseResponse):[];
  const pageItems=Array.isArray(parcelData)?parcelData:[];
  setParcels(pageItems.slice(0,PAGE_SIZE));
  setHasMore(pageItems.length>PAGE_SIZE);
  setVillages(Array.isArray(villageData)?villageData:[]);
  setFarmers(Array.isArray(farmerData)?farmerData:[]);
  setOwnerDrafts(Object.fromEntries(pageItems.slice(0,PAGE_SIZE).map(parcel=>[parcel.id,parcel.farmer_id||''])));
 },[session,request,page,appliedSearch]);

 useEffect(()=>{
  const controller=new AbortController();
  setLoading(true);
  setError('');
  refresh(controller.signal)
   .catch(e=>{if(e.name!=='AbortError')setError(e.message)})
   .finally(()=>{if(!controller.signal.aborted)setLoading(false)});
  return()=>controller.abort();
 },[refresh]);

 async function createParcel(e){
  e.preventDefault();
  setFormError('');
  setSuccess('');
  const external_id=form.external_id.trim();
  const village_code=form.village_code.trim();
  const area=Number(form.area_hectares);

  if(!external_id||!village_code||!form.area_hectares.trim()||
   !Number.isFinite(area)||area<=0){
   setFormError('Enter a parcel ID, village and valid area greater than zero.');
   return;
  }

  setSaving(true);
  try{
   const created=await request('/api/v1/parcels',{
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({
     external_id,
     village_code,
     area_hectares:area
    })
   }).then(parseResponse);
   setForm(EMPTY);
   setSelected(created);
   setSuccess('Parcel registered successfully.');
   setPage(0);
   setSearch('');
   setAppliedSearch('');
   try{await refresh(undefined,0,'')}catch(e){setError('Parcel saved, but the list could not be refreshed: '+e.message)}
  }catch(e){
   setFormError(e.message);
  }finally{
   setSaving(false);
  }
 }

 async function viewParcel(id){
  setError('');
  try{
   const parcel=await request('/api/v1/parcels/'+encodeURIComponent(id)).then(parseResponse);
   setSelected(parcel);
  }catch(e){
   setError(e.message);
  }
 }
 async function assignOwner(parcel){
  const farmer_id=ownerDrafts[parcel.id]||null;
  const problem=validateOwnerSelection(farmer_id,farmers);if(problem){setError(problem);return;}
  const label=ownershipLabel(farmer_id,farmers);
  if(!window.confirm(`Change ownership of ${parcel.external_id} to ${label}?`))return;
  setOwnerBusy(parcel.id);setError('');setSuccess('');
  try{const updated=await request('/api/v1/parcels/'+encodeURIComponent(parcel.id)+'/owner',{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({farmer_id})}).then(parseResponse);setParcels(items=>items.map(item=>item.id===updated.id?updated:item));setSuccess(`Ownership updated for ${parcel.external_id}.`);}
  catch(e){setError(e.message)}finally{setOwnerBusy('')}
 }

 if(!session)return <div className="registry"><section className="registry-card"><h2>Parcel Registry</h2><p>Sign in above to access parcels allowed for your role.</p></section></div>;
 const canEdit=['admin','gis_operator'].includes(session.principal.role);
 return <div className="registry">
  <div className="registry-heading">
   <div>
    <h2>Parcel Registry</h2>
    <p>{canEdit?'Manage agricultural parcels and village records.':session.principal.role==='farmer'?'View parcels assigned to your account.':'View parcels permitted for your role.'}</p>
   </div>
   <button type="button" onClick={()=>{
    setError('');
    setLoading(true);
    refresh().catch(e=>setError(e.message)).finally(()=>setLoading(false));
   }}>Refresh</button>
  </div>

  {error&&<p className="gis-error" role="alert">{error}</p>}

  <div className="registry-grid">
   {canEdit&&<section className="registry-card">
    <h3>Register Parcel</h3>
    <form onSubmit={createParcel} className="registry-form">
     <label htmlFor="parcel-id">Parcel ID</label>
     <input id="parcel-id" maxLength={100} required
      placeholder="Enter parcel reference"
      value={form.external_id}
      onChange={e=>setForm({...form,external_id:e.target.value})}/>

     <label htmlFor="parcel-village">Village</label>
     <select id="parcel-village" required disabled={!villages.length}
      value={form.village_code}
      onChange={e=>setForm({...form,village_code:e.target.value})}>
      <option value="">{villages.length?'Select village':'No villages available'}</option>
      {villages.map(v=><option key={v.code} value={v.code}>
       {v.name} ({v.code})
      </option>)}
     </select>

     <label htmlFor="parcel-area">Area (hectares)</label>
     <input id="parcel-area" type="number" min="0.000001" step="any"
      required placeholder="Enter area"
      value={form.area_hectares}
      onChange={e=>setForm({...form,area_hectares:e.target.value})}/>

     <button type="submit" disabled={saving}>
      {saving?'Saving...':'Register Parcel'}
     </button>
     {formError&&<p className="gis-error" role="alert">{formError}</p>}
     {success&&<p className="registry-success" role="status">{success}</p>}
    </form>
   </section>}

   <section className="registry-card">
    <h3>Parcel Records</h3>
    <form className="registry-search-form" onSubmit={event=>{event.preventDefault();setPage(0);setAppliedSearch(search.trim())}}>
     <input className="registry-search"
      placeholder="Search parcel ID, village or record ID"
      aria-label="Search parcels"
      maxLength={100}
      value={search} onChange={e=>setSearch(e.target.value)}/>
     <button type="submit" disabled={loading}>Search</button>
     <button type="button" className="registry-clear" disabled={loading&&!appliedSearch} onClick={()=>{setSearch('');setPage(0);setAppliedSearch('')}}>Clear</button>
    </form>
    <div className="registry-table-wrap">
     <table className="registry-table">
      <thead><tr>
       <th>Parcel ID</th><th>Village</th><th>Area (ha)</th><th>Owner</th><th>Action</th>
      </tr></thead>
      <tbody>
       {parcels.map(p=><tr key={p.id}>
        <td>{p.external_id}</td>
        <td>{p.village_code}</td>
        <td>{p.area_hectares}</td>
        <td>{canEdit?<><select aria-label={`Owner for ${p.external_id}`} value={ownerDrafts[p.id]??p.farmer_id??''} onChange={e=>setOwnerDrafts(values=>({...values,[p.id]:e.target.value}))}><option value="">Unassigned</option>{farmers.map(f=><option key={f.id} value={f.id}>{f.email}</option>)}</select><button type="button" disabled={ownerBusy===p.id||(ownerDrafts[p.id]??'')===(p.farmer_id??'')} onClick={()=>assignOwner(p)}>{ownerBusy===p.id?'Saving...':'Assign'}</button></>:p.farmer_id?'Assigned to you':'Unassigned'}</td>
        <td><button type="button" onClick={()=>viewParcel(p.id)}>View</button></td>
       </tr>)}
       {!loading&&!parcels.length&&<tr>
        <td colSpan={5}>No matching parcels found.</td>
       </tr>}
      </tbody>
     </table>
    </div>
    {loading&&<p>Loading parcels...</p>}
    <div className="registry-pagination"><span>Page {page+1} · {parcels.length} record{parcels.length===1?'':'s'}{hasMore?' · More results available':''}</span><div><button type="button" disabled={page===0||loading} onClick={()=>setPage(value=>Math.max(0,value-1))}>Previous</button><button type="button" disabled={!hasMore||loading} onClick={()=>setPage(value=>value+1)}>Next</button></div></div>
   </section>
  </div>

  {selected&&<section className="registry-card registry-selected">
   <div className="registry-heading">
    <h3>Parcel Details</h3>
    <button type="button" onClick={()=>setSelected(null)}>Close</button>
   </div>
   <dl>
    <dt>Record ID</dt><dd>{selected.id}</dd>
    <dt>Parcel ID</dt><dd>{selected.external_id}</dd>
    <dt>Village</dt><dd>{selected.village_code}</dd>
    <dt>Area</dt><dd>{selected.area_hectares} hectares</dd>
    <dt>Farmer owner</dt><dd>{ownershipLabel(selected.farmer_id,farmers)}</dd>
    <dt>Created</dt><dd>{selected.created_at||'Unavailable'}</dd>
   </dl>
  </section>}

  <ParcelMap/>
 </div>;
}
