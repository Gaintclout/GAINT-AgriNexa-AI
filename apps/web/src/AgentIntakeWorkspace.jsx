import React,{useEffect,useState} from 'react';
import {useAuth} from './AuthContext.jsx';

async function parseResponse(response){
  const data=await response.json().catch(()=>null);
  if(!response.ok){
    const detail=data?.detail;
    throw new Error(typeof detail==='string'?detail:`Request failed (${response.status})`);
  }
  return data;
}

export default function AgentIntakeWorkspace(){
  const {session,request}=useAuth();
  const [parcels,setParcels]=useState([]);
  const [parcelId,setParcelId]=useState('');
  const [cropName,setCropName]=useState('');
  const [season,setSeason]=useState('');
  const [loading,setLoading]=useState(true);
  const [error,setError]=useState('');
  const [availability,setAvailability]=useState(null);
  const [profileResult,setProfileResult]=useState(null);
  const [processing,setProcessing]=useState(false);

  useEffect(()=>{
    if(!session)return;
    const controller=new AbortController();
    setLoading(true);
    setError('');
    Promise.all([
      request('/api/v1/parcels?limit=100&offset=0',{signal:controller.signal}).then(parseResponse),
      request('/api/v1/agents/intake-profile/availability',{signal:controller.signal}).then(parseResponse)
    ])
      .then(([data,status])=>{
        if(!controller.signal.aborted){
          setParcels(Array.isArray(data)?data:[]);
          setAvailability(status);
        }
      })
      .catch(e=>{
        if(e.name!=='AbortError')setError(e.message);
      })
      .finally(()=>{
        if(!controller.signal.aborted)setLoading(false);
      });
    return()=>controller.abort();
  },[session,request]);

  async function generateProfile(){
    if(!parcelId||availability?.available!==true||processing)return;
    setProcessing(true);
    setError('');
    setProfileResult(null);
    try{
      const response=await request(
        '/api/v1/agents/intake-profile/preview',
        {
          method:'POST',
          headers:{'Content-Type':'application/json'},
          body:JSON.stringify({
            parcel_id:parcelId,
            crop_name:cropName.trim()||null,
            season:season.trim()||null
          })
        }
      );
      const result=await parseResponse(response);
      setProfileResult(result);
    }catch(e){
      setError(e.message||'Profile processing unavailable');
    }finally{
      setProcessing(false);
    }
  }

  return(
    <section className="agents-panel">
      <div className="agent-workspace-header">
        <div>
          <h2>Intake and Profile</h2>
          <p>Prepare parcel information for governed agricultural intelligence.</p>
        </div>
        <span className="agent-status">Preview preparation</span>
      </div>

      {error&&<p className="gis-error" role="alert">{error}</p>}

      <div className="agent-intake-fields">
        <label>
          Parcel
          <select value={parcelId}
            onChange={e=>setParcelId(e.target.value)}
            disabled={loading}>
            <option value="">Select parcel</option>
            {parcels.map(parcel=>(
              <option key={parcel.id} value={parcel.id}>
                {parcel.external_id||parcel.id}
              </option>
            ))}
          </select>
        </label>

        <label>
          Crop name
          <input value={cropName} maxLength={120}
            onChange={e=>setCropName(e.target.value)}
            placeholder="Enter crop name"/>
        </label>

        <label>
          Season
          <input value={season} maxLength={80}
            onChange={e=>setSeason(e.target.value)}
            placeholder="Enter season"/>
        </label>
      </div>

      <button
        type="button"
        disabled={!parcelId||availability?.available!==true||processing}
        onClick={generateProfile}
        className="agent-generate-button"
      >
        {processing?'Processing...':'Generate profile'}
      </button>

      {profileResult&&(
        <div className="agent-profile-result" role="region"
          aria-label="Generated intake profile">
          <h3>Intake/Profile result</h3>
          <dl>
            <dt>Parcel</dt>
            <dd>{profileResult.intake?.parcel_id||parcelId}</dd>
            <dt>Village</dt>
            <dd>{profileResult.village_code||'Unavailable'}</dd>
            <dt>Area (hectares)</dt>
            <dd>{profileResult.area_hectares||'Unavailable'}</dd>
            <dt>Source</dt>
            <dd>{profileResult.data_source||'Unavailable'}</dd>
          </dl>
          <p>Profile processing does not constitute a crop diagnosis.</p>
        </div>
      )}

      <div className="agent-preview-state" role="status">
        {loading?'Loading authorized parcels...':
          availability?.available===false
            ?availability.reason
            :availability?.available===true
              ?'Intake/Profile API is available.'
              :parcelId
                ?'Parcel selected. Availability could not be verified.'
                :'Select a parcel to prepare an intake profile.'}
      </div>
    </section>
  );
}
