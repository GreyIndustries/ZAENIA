import { indexRoute, measureProgress } from "./tripProgress";
import type { Fix, Progress } from "./tripProgress";
import { km, kmToLine } from "./mapMath";
import { checkedRoute } from "./mapRequests";
import type { MapRoute } from "./mapRequests";
export type TripStop = {lat:number;lon:number;label:string};
type Snapshot = { route:MapRoute|null; stops:TripStop[]; running:boolean; progress:Progress|null; fix:Fix|null; status:string; rerouting:boolean; autoReroute:boolean; wake:string };
const empty=():Snapshot=>({route:null,stops:[],running:false,progress:null,fix:null,status:"",rerouting:false,autoReroute:true,wake:"Screen wake lock not active"});
let watchEpoch=0;
let state=empty(),generation=0,watch:number|null=null,timer:ReturnType<typeof setInterval>|null=null,wake:WakeLockSentinel|null=null;
let requestRoute:((stops:TripStop[])=>Promise<MapRoute>)|null=null;
let nextStop=1,offCount=0,offSince=0,lastAttempt=-Infinity,lastPhysical:Fix|null=null;
const listeners=new Set<()=>void>();
export const tripSnapshot=()=>state;
export const subscribeTrip=(listener:()=>void)=>{listeners.add(listener);return()=>{listeners.delete(listener);};};
const publish=(patch:Partial<Snapshot>)=>{state={...state,...patch};for(const listener of listeners)listener();};
const release=()=>{watchEpoch++;if(watch!==null){navigator.geolocation.clearWatch(watch);watch=null;}if(timer){clearInterval(timer);timer=null;}if(wake){void wake.release();wake=null;}};
async function holdScreen(){
  const token=generation;
  if(!state.running || document.hidden)return;
  if(!navigator.wakeLock){publish({wake:"Screen wake lock unsupported; GPS may pause if this device sleeps"});return;}
  if(wake && !wake.released)return;
  try{const lock=await navigator.wakeLock.request("screen");if(token!==generation || !state.running){void lock.release();return;}wake=lock;publish({wake:"Keeping the screen awake during this trip"});lock.addEventListener("release",()=>{if(wake===lock){wake=null;publish({wake:"Wake lock released; background GPS is best effort"});}});}
  catch{if(token===generation)publish({wake:"Screen wake lock unavailable; keep the app visible for reliable tracking"});}
}
export function pauseTrip(status="Trip paused"){generation++;release();publish({running:false,rerouting:false,status,wake:"Screen wake lock not active"});}
export function stopTrip(){generation++;release();state=empty();for(const listener of listeners)listener();}
export function setAutoReroute(enabled:boolean){if(!enabled){generation++;publish({autoReroute:false,rerouting:false,status:"Automatic rerouting is off; current route retained"});}else publish({autoReroute:true});offCount=0;}
async function reroute(fix:Fix){
  if(!requestRoute || !state.route || state.rerouting || !state.autoReroute)return;
  const token=generation;lastAttempt=Date.now();offCount=0;
  const stops=[{lat:fix.lat,lon:fix.lon,label:"Your location"},...state.stops.slice(nextStop)];
  if(stops.length<2)return;
  publish({rerouting:true,status:"Off route — recalculating from your location…"});
  try{const route=checkedRoute(await requestRoute(stops),stops.length);if(route.order.some((value,i)=>value!==i))throw Error("Unexpected stop order");
    if(token!==generation || !state.running || !state.autoReroute)return;
    nextStop=1;lastPhysical=fix;publish({route,stops,progress:null,rerouting:false,status:"Route recalculated; unvisited stops preserved"});
  }catch{if(token===generation && state.running)publish({rerouting:false,status:"Reroute unavailable. Original route kept; will retry after the cooldown."});}
}
function onFix(value:GeolocationPosition){
  if(!state.running || !state.route)return;
  const fix={lat:value.coords.latitude,lon:value.coords.longitude,accuracy:value.coords.accuracy,timestamp:value.timestamp};
  const now=Date.now(), previous=state.progress;
  if(lastPhysical && fix.timestamp<=lastPhysical.timestamp)return;
  const result=measureProgress(indexRoute(state.route.line),fix,previous,now);
  if(!Number.isFinite(fix.accuracy) || fix.accuracy>80 || fix.accuracy<0 || !Number.isFinite(fix.lat) || !Number.isFinite(fix.lon) || Math.abs(fix.lat)>90 || Math.abs(fix.lon)>180 || now-fix.timestamp>15000 || fix.timestamp>now+5000){offCount=0;publish({status:result.status});return;}
  if(lastPhysical && km(fix,lastPhysical)*1000>Math.max(120,(fix.timestamp-lastPhysical.timestamp)/1000*70+fix.accuracy+lastPhysical.accuracy)){offCount=0;publish({status:"GPS jump rejected; waiting for a reliable position"});return;}
  lastPhysical=fix;
  const last=state.stops.length-1;
  if(nextStop<last && km(fix,state.stops[nextStop])*1000<=Math.max(35,fix.accuracy))nextStop++;
  let progress=result.progress;
  const missedStops=!!progress?.arrived && nextStop<last;
  if(progress?.arrived && nextStop<last)progress={...progress,arrived:false,fraction:Math.min(.999,progress.fraction)};
  publish({fix,progress,status:state.rerouting?state.status:missedStops?"An intermediate stop remains unvisited; checking the route":result.status});
  if(progress?.arrived){pauseTrip("Destination reached");return;}
  const offset=kmToLine(fix,state.route.line)*1000;
  if(offset>Math.max(80,fix.accuracy*2) || missedStops || result.status.startsWith("Off route")){
    if(offCount===0)offSince=now;offCount++;
    if(offCount>=3 && now-offSince>=8000 && now-lastAttempt>=30000)void reroute(fix);
  }else offCount=0;
}
export function beginTrip(route:MapRoute,stops:TripStop[],request:(stops:TripStop[])=>Promise<MapRoute>){
  if(state.running && state.route===route)return;
  const continuing=state.route===route && !state.progress?.arrived;
  generation++;release();requestRoute=request;offCount=0;
  if(!continuing){nextStop=1;lastPhysical=null;lastAttempt=-Infinity;state={...empty(),autoReroute:state.autoReroute};}
  publish({route,stops,running:true,status:"Waiting for GPS…"});
  if(!navigator.geolocation){pauseTrip("GPS isn't available on this device");return;}
  const epoch=watchEpoch;try{watch=navigator.geolocation.watchPosition(value=>{if(epoch===watchEpoch)onFix(value);},error=>{if(epoch!==watchEpoch)return;if(error.code===1)pauseTrip("Location permission denied. Tracking stopped.");else publish({status:"GPS unavailable; waiting for a new reading"});},{enableHighAccuracy:true,maximumAge:0,timeout:15000});}catch{pauseTrip("GPS could not start. Check this device location permission and secure connection.");return;}
  timer=setInterval(()=>{if(state.running && state.fix && Date.now()-state.fix.timestamp>15000)publish({status:"GPS signal is stale; progress paused"});},5000);
  void holdScreen();
}
if(typeof document!=="undefined")document.addEventListener("visibilitychange",()=>{if(state.running){if(document.hidden)publish({wake:"Background tracking is best effort; a locked or suspended phone may stop GPS"});else void holdScreen();}});
if(typeof window!=="undefined"){window.addEventListener("beforeunload",()=>stopTrip());window.addEventListener("zae:trip-session-end",()=>stopTrip());}
