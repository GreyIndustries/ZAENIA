import {useEffect,useRef,useState} from "react";
import {AircraftMotion} from "./aircraftMotion";
import type {AircraftRecord} from "./aircraftMotion";
import {project} from "./mapMath";
export function AircraftLayer({reports,enabled,animate,view,left,top,width,height,onSelect}:{reports:AircraftRecord[];enabled:boolean;animate:boolean;view:{z:number};left:number;top:number;width:number;height:number;onSelect:(report:AircraftRecord)=>void}){
  const motion=useRef(new AircraftMotion());const [now,setNow]=useState(Date.now());const [reduced,setReduced]=useState(()=>window.matchMedia("(prefers-reduced-motion: reduce)").matches);
  useEffect(()=>{motion.current.ingest(reports,Date.now());setNow(Date.now());},[reports]);
  useEffect(()=>{const media=window.matchMedia("(prefers-reduced-motion: reduce)");const change=()=>setReduced(media.matches);media.addEventListener("change",change);return()=>media.removeEventListener("change",change);},[]);
  useEffect(()=>{
    if(!enabled)return;let id=0,last=0,active=true;
    const frame=(time:number)=>{if(!active)return;if(!document.hidden&&time-last>=(animate&&!reduced?50:1000)){last=time;setNow(Date.now());}id=requestAnimationFrame(frame);};
    id=requestAnimationFrame(frame);return()=>{active=false;cancelAnimationFrame(id);};
  },[enabled,animate,reduced]);
  if(!enabled)return null;
  return <>{reports.slice(0,2000).map(report=>{const point=motion.current.position(report.id,now,animate&&!reduced);if(!point)return null;const p=project(point.lat,point.lon,view.z);const x=p.x-left,y=p.y-top;if(x< -40||y< -40||x>width+40||y>height+40)return null;
    const quality=point.mode==="unknown"?"timestamp unavailable":point.mode==="estimated"?"estimated position":point.mode==="stale"?"stale position":"reported position";
    const detail=`${quality}${point.age!==null?` · report ${Math.floor(point.age)} seconds old`:""}`;
    return <button key={report.id} type="button" className={`zmap__mark zmap__mark--plane zmap__plane--${point.mode}${report.onGround?" zmap__mark--ground":""}`} style={{left:x,top:y}} aria-label={`Flight ${report.callsign||report.id}: ${detail}`} title={detail} onClick={()=>onSelect(report)}>
      <svg viewBox="0 0 24 24" style={{transform:`rotate(${report.heading??0}deg)`}}><path d="M12 2c.8 0 1.3.9 1.3 2v5.2l7.7 4.6v2l-7.7-2.3v4.6l2.2 1.6V21L12 20l-3.5 1v-1.3l2.2-1.6v-4.6L3 15.8v-2l7.7-4.6V4c0-1.1.5-2 1.3-2Z"/></svg>
      {view.z>=10&&<span>{report.callsign||report.id} · {point.mode==="estimated"?"est.":point.mode==="stale"?"stale":point.mode==="unknown"?"time unknown":"reported"}</span>}
    </button>;
  })}</>;
}
