
/**
 * GAINT AgriNexa AI — API boundary
 *
 * Security:
 * - Access tokens remain in application memory.
 * - Never persist access tokens in localStorage or sessionStorage.
 * - Authentication cookies are managed by the browser.
 * - Do not expose tokens, passwords or server internals in errors.
 */

import {buildParcelQuery,parseParcelFeatures} from './gisUtils.js';

// Browser traffic is deliberately same-origin. Vite selects the backend
// target server-side with VITE_PROXY_TARGET during local UAT.
export const API='';

const AUTH_TIMEOUT_MESSAGE='Authentication request timed out. Please try again.';
const NETWORK_ERROR_MESSAGE='Cannot reach the authentication service. Check the API connection.';

function apiUrl(path){
 return API+path;
}

function loginFailureMessage(status){
 if(status===400)return 'Invalid sign-in request (HTTP 400).';
 if(status===401)return 'Incorrect email or password.';
 if(status===403)return 'This account is not authorized to sign in (HTTP 403).';
 if(status===404)return 'The authentication endpoint was not found (HTTP 404).';
 if(status===429)return 'Too many sign-in attempts. Please try again later.';
 if(status===503)return 'Authentication service unavailable (HTTP 503). This is a server configuration or availability issue, not an invalid-password response.';
 if(status>=500)return `Authentication service error (HTTP ${status}). Please try again later.`;
 return `Sign-in request was rejected (HTTP ${status}).`;
}

async function authFetch(url,options={},fetchImpl=fetch){
 try{
  return await fetchImpl(apiUrl(url),options);
 }catch(error){
  if(error?.name==='AbortError')throw error;
  if(error?.name==='TimeoutError')throw new Error(AUTH_TIMEOUT_MESSAGE);
  throw new Error(NETWORK_ERROR_MESSAGE);
 }
}

async function readJson(response,message){
 try{
  return await response.json();
 }catch{
  throw new Error(message);
 }
}

function validateTokenResponse(data,message){
 if(!data||typeof data.access_token!=='string'||!data.access_token.trim()){
  throw new Error(message);
 }
 return data;
}

export async function loginOperator(email,password,signal,fetchImpl=fetch){
 const response=await authFetch('/api/v1/auth/login',{
  method:'POST',
  headers:{'Content-Type':'application/json'},
  body:JSON.stringify({email,password}),
  credentials:'same-origin',
  signal
 },fetchImpl);

 if(!response.ok){
  throw new Error(loginFailureMessage(response.status));
 }

 const data=await readJson(
  response,
  'Authentication service returned an invalid response.'
 );

 return validateTokenResponse(
  data,
  'Authentication service returned an invalid sign-in response.'
 );
}

export async function registerFarmer(email,password,signal){
 const response=await authFetch('/api/v1/auth/register/farmer',{
  method:'POST',
  headers:{'Content-Type':'application/json'},
  body:JSON.stringify({email,password}),
  credentials:'same-origin',
  signal
 });

 const data=await response.json().catch(()=>null);

 if(!response.ok){
  const detail=data?.detail;
  const message=Array.isArray(detail)
   ?detail.map(item=>item.msg||'Invalid field').join('; ')
   :typeof detail==='string'
    ?detail
    :`Registration failed (HTTP ${response.status}).`;
  throw new Error(message);
 }

 if(data?.role!=='farmer'||typeof data.id!=='string'){
  throw new Error('Invalid farmer registration response.');
 }

 return data;
}

export async function verifyOperator(token,signal){
 if(typeof token!=='string'||!token.trim()){
  const error=new Error('Authentication required. Please sign in.');
  error.authFailure=true;
  throw error;
 }

 const response=await authFetch('/api/v1/auth/me',{
  method:'GET',
  headers:{Authorization:'Bearer '+token},
  signal
 });

 if(response.status===401||response.status===403){
  const error=new Error('Session expired or account access changed.');
  error.authFailure=true;
  throw error;
 }

 if(!response.ok){
  throw new Error(`Unable to verify your session (HTTP ${response.status}).`);
 }

 return readJson(response,'Invalid session verification response.');
}

export async function loadParcels(token,bounds,signal,filters={}){
 if(typeof token!=='string'||!token.trim()){
  const error=new Error('Authentication required. Please sign in.');
  error.authFailure=true;
  throw error;
 }

 const query=buildParcelQuery(bounds,filters);

 const response=await authFetch(
  '/api/v1/gis/parcels/geojson?'+query,
  {
   method:'GET',
   headers:{Authorization:'Bearer '+token},
   signal
  }
 );

 if(response.status===401||response.status===403){
  const error=new Error('Session expired or map access denied.');
  error.authFailure=true;
  throw error;
 }

 if(!response.ok){
  throw new Error(`Unable to load parcel boundaries (HTTP ${response.status}).`);
 }

 const data=await readJson(response,'Invalid parcel boundary response.');
 return parseParcelFeatures(data);
}

export async function refreshOperator(signal){
 const response=await authFetch('/api/v1/auth/refresh',{
  method:'POST',
  credentials:'same-origin',
  signal
 });

 // No valid refresh session is available.
 if(response.status===401)return null;

 if(response.status===404){
  throw new Error('Session refresh endpoint is unavailable (HTTP 404).');
 }

 if(response.status===503){
  throw new Error('Authentication service unavailable (HTTP 503). Please try again.');
 }

 if(!response.ok){
  throw new Error(`Unable to restore your session (HTTP ${response.status}).`);
 }

 const data=await readJson(
  response,
  'Invalid session restoration response.'
 );

 return validateTokenResponse(
  data,
  'Invalid session restoration response.'
 );
}

/**
 * Request server-side logout.
 *
 * 2xx: Server confirmed logout.
 * 401: No valid authenticated session remains.
 * Other errors: Logout is not confirmed.
 *
 * The calling component must clear in-memory credentials
 * according to its session-security policy.
 */
export async function logoutOperator(){
 const response=await authFetch('/api/v1/auth/logout',{
  method:'POST',
  credentials:'same-origin'
 });

 if(response.ok){
  return {success:true,alreadySignedOut:false};
 }

 if(response.status===401){
  return {success:true,alreadySignedOut:true};
 }

 if(response.status===404){
  throw new Error(
   'Logout endpoint was not found (HTTP 404). Check the backend route.'
  );
 }

 if(response.status===405){
  throw new Error(
   'Logout endpoint does not support POST (HTTP 405).'
  );
 }

 if(response.status===503){
  throw new Error(
   'Authentication service unavailable (HTTP 503). Sign-out could not be confirmed.'
  );
 }

 throw new Error(
  `Server logout failed (HTTP ${response.status}). Please retry.`
 );
}
