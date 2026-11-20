import React,{useCallback,useEffect,useState} from 'react';
import {MapContainer,TileLayer,GeoJSON,useMapEvents} from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import {loadParcels} from './gisApi.js';
import {useAuth} from './AuthContext.jsx';
const EMPTY={type:'FeatureCollection',features:[]};
function Viewport({onBounds}){const map=useMapEvents({moveend:()=>onBounds(map.getBounds()),zoomend:()=>onBounds(map.getBounds())});useEffect(()=>onBounds(map.getBounds()),[map,onBounds]);return null;}
export default function ParcelMap(){
 const {session,logout}=useAuth(); const token=session?.token||'';
 const [villageFilter,setVillageFilter]=useState(''),[parcelFilter,setParcelFilter]=useState(''),[appliedFilters,setAppliedFilters]=useState({});
 const [bounds,setBounds]=useState(null),[data,setData]=useState(EMPTY),[selected,setSelected]=useState(null),[error,setError]=useState(''),[loading,setLoading]=useState(false);
 const onBounds=useCallback(b=>setBounds({west:b.getWest(),south:b.getSouth(),east:b.getEast(),north:b.getNorth()}),[]);
 useEffect(()=>{if(!token){setData(EMPTY);setSelected(null);return;}if(!bounds)return;const controller=new AbortController();let active=true;async function run(){setLoading(true);setError('');try{const features=await loadParcels(token,bounds,controller.signal,appliedFilters);if(active){setData(features);setSelected(null)}}catch(e){if(active&&e.name!=='AbortError'){if(e.authFailure)logout(e.message);else{setError(e.message);setData(EMPTY)}}}finally{if(active)setLoading(false)}}run();return()=>{active=false;controller.abort()}},[token,bounds,logout,appliedFilters]);
 return <section className="gis-panel"><div className="gis-head"><div><h2>Parcel GIS map</h2><p>Secured PostGIS boundaries · viewport search</p></div></div>
 {error?<p className="gis-error" role="alert">{error}</p>:null}
 <form className="gis-login" onSubmit={e=>{e.preventDefault();setAppliedFilters({village_code:villageFilter.trim(),external_id:parcelFilter.trim()})}}><label>Filter map parcels</label><input aria-label="Village code" maxLength={100} placeholder="Village code" value={villageFilter} onChange={e=>setVillageFilter(e.target.value)}/><input aria-label="Parcel ID" maxLength={100} placeholder="Parcel ID" value={parcelFilter} onChange={e=>setParcelFilter(e.target.value)}/><button type="submit" disabled={!token}>Apply filters</button><button type="button" disabled={!token} onClick={()=>{setVillageFilter('');setParcelFilter('');setAppliedFilters({})}}>Clear</button></form>
 <div className="gis-layout"><div className="gis-map"><MapContainer center={[17.385,78.4867]} zoom={10} scrollWheelZoom style={{height:'100%',width:'100%'}}><TileLayer attribution='&copy; OpenStreetMap contributors' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"/><Viewport onBounds={onBounds}/>{token&&data.features.map(f=><GeoJSON key={f.id+JSON.stringify(f.geometry)} data={f} style={{color:selected?.id===f.id?'#f59e0b':'#1c8a58',weight:2,fillOpacity:.2}} eventHandlers={{click:()=>setSelected(f)}}/>)}</MapContainer></div><aside className="gis-details"><h3>Parcel details</h3><p aria-live="polite">{loading?'Loading map parcels…':token?data.features.length+' parcels in viewport':'Sign in to load parcel boundaries'}</p>{selected?<dl><dt>Parcel</dt><dd>{selected.properties?.external_id}</dd><dt>Village</dt><dd>{selected.properties?.village_code}</dd><dt>Record ID</dt><dd>{selected.id}</dd></dl>:<p>Select a boundary to inspect its details.</p>}</aside></div></section>;
}
