import { km } from "./mapMath";
import type { TrafficStroke } from "./routeTraffic";
/** Categorical-flow heuristic, not provider-measured travel time. Unknown roads keep baseline time. */
export function trafficEta(baseSeconds:number,strokes:TrafficStroke[],fraction:number){
  const lengths=strokes.map(s=>s.line.slice(1).reduce((n,p,i)=>n+km({lat:s.line[i][0],lon:s.line[i][1]},{lat:p[0],lon:p[1]}),0));
  const total=lengths.reduce((n,v)=>n+v,0),cut=total*Math.max(0,Math.min(1,fraction));let passed=0,covered=0,weighted=0;
  const multipliers:Record<number,number>={1:1,2:1.25,3:1.65,4:2.2};
  for(let i=0;i<strokes.length;i++){const remaining=Math.max(0,passed+lengths[i]-Math.max(cut,passed));passed+=lengths[i];const level=strokes[i].level;weighted+=remaining*(level===null?1:multipliers[level]??1);if(level!==null)covered+=remaining;}
  const baseline=baseSeconds*(1-Math.max(0,Math.min(1,fraction)));
  const seconds=total>0?baseSeconds*weighted/total:baseline;
  return {seconds,delaySeconds:Math.max(0,seconds-baseline),coverage:total>cut?covered/(total-cut):0};
}
