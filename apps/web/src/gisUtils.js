/** Pure, testable GIS query and response helpers. */
export function buildParcelQuery(bounds,filters={}){
 const {west,south,east,north}=bounds;
 if(![west,south,east,north].every(Number.isFinite)||west< -180||east>180||south< -90||north>90||west>=east||south>=north)throw new Error('Invalid map bounds');
 const q=new URLSearchParams({west:String(west),south:String(south),east:String(east),north:String(north),limit:'500'});
 for(const key of ['village_code','external_id']){const value=(filters[key]||'').trim();if(value){if(value.length>100)throw new Error('Filter too long');q.set(key,value)}}
 return q;
}
export function parseParcelFeatures(data){
 if(data?.type!=='FeatureCollection'||!Array.isArray(data.features))throw new Error('Unexpected parcel data');
 if(data.features.some(f=>f?.type!=='Feature'||!f.geometry||!f.properties))throw new Error('Invalid parcel feature');
 return data;
}
