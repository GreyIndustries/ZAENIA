export type AircraftRecord = { id:string;callsign:string;country:string;lat:number;lon:number;onGround:boolean;altitudeFt:number|null;speedKt:number|null;heading:number|null;climbFpm:number|null;squawk:string|null;positionAt?:string|null;lastContactAt?:string|null };
export type MotionPosition = {lat:number;lon:number;mode:"reported"|"estimated"|"stale"|"unknown";age:number|null};
const wrap=(lon:number)=>((lon+540)%360)-180;
const radians=Math.PI/180;
export function aircraftPosition(report:AircraftRecord,now:number,animate=true):MotionPosition|null {
  if(!Number.isFinite(report.lat)||!Number.isFinite(report.lon)||Math.abs(report.lat)>90||Math.abs(report.lon)>180)return null;
  const observed=report.positionAt?Date.parse(report.positionAt):NaN;
  if(!Number.isFinite(observed)||observed>now+5000)return {lat:report.lat,lon:report.lon,mode:"unknown",age:null};
  const age=Math.max(0,(now-observed)/1000);if(age>120)return null;
  let lat=report.lat,lon=report.lon,mode:MotionPosition["mode"]=age>60?"stale":"reported";
  const canMove=animate&&!report.onGround&&report.speedKt!==null&&Number.isFinite(report.speedKt)&&report.speedKt>0&&report.speedKt<=1000&&report.heading!==null&&Number.isFinite(report.heading)&&report.heading>=0&&report.heading<360;
  if(canMove){
    const distance=report.speedKt!*.514444*Math.min(age,45)/6371000,bearing=report.heading!*radians,a=lat*radians,b=lon*radians;
    const p=Math.asin(Math.max(-1,Math.min(1,Math.sin(a)*Math.cos(distance)+Math.cos(a)*Math.sin(distance)*Math.cos(bearing))));
    lon=wrap((b+Math.atan2(Math.sin(bearing)*Math.sin(distance)*Math.cos(a),Math.cos(distance)-Math.sin(a)*Math.sin(p)))/radians);lat=p/radians;
    if(age<=60)mode=age>0?"estimated":"reported";
  }
  return {lat,lon,mode,age};
}
export class AircraftMotion {
  private tracks=new Map<string,{report:AircraftRecord;from:MotionPosition|null;received:number}>();
  ingest(reports:AircraftRecord[],now:number){
    const ids=new Set<string>();
    for(const report of reports.slice(0,2000)){
      ids.add(report.id);if(!aircraftPosition(report,now,false))continue;
      const previous=this.tracks.get(report.id);
      if(previous && Date.parse(report.positionAt??"")<Date.parse(previous.report.positionAt??""))continue;
      if(previous&&previous.report.positionAt===report.positionAt&&previous.report.lat===report.lat&&previous.report.lon===report.lon){previous.report=report;continue;}
      const from=previous?this.position(report.id,now,true):null;
      this.tracks.set(report.id,{report,from,received:now});
    }
    for(const id of this.tracks.keys())if(!ids.has(id))this.tracks.delete(id);
  }
  position(id:string,now:number,animate:boolean):MotionPosition|null{
    const track=this.tracks.get(id);if(!track)return null;
    const point=aircraftPosition(track.report,now,animate);if(!point||!animate||!track.from||(point.mode!=="estimated"&&point.mode!=="reported")||track.report.onGround||track.from.mode==="stale"||track.from.mode==="unknown")return point;
    const t=Math.max(0,Math.min(1,(now-track.received)/1200)),smooth=t*t*(3-2*t);
    if(Math.abs(point.lat-track.from.lat)>1||Math.abs(wrap(point.lon-track.from.lon))>1)return point;
    return {...point,lat:track.from.lat+(point.lat-track.from.lat)*smooth,lon:wrap(track.from.lon+wrap(point.lon-track.from.lon)*smooth)};
  }
}
