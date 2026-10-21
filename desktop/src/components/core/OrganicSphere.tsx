import { useEffect, useRef } from "react";
type Props={motion:boolean;processing:boolean;startupProgress:number};
type V={x:number;y:number;z:number};
type Nerve={p:V[];blue:boolean;w:number;z:number};
const TAU=Math.PI*2, SIZE=1000, R=438;
const gold=[255,164,55],ice=[135,201,255];
const rgba=(c:number[],a:number)=>`rgba(${c[0]},${c[1]},${c[2]},${a})`;
const project=(p:V)=>({x:500+p.x*R,y:500-p.y*R});
const mix=(a:V,b:V,t:number):V=>({x:a.x+(b.x-a.x)*t,y:a.y+(b.y-a.y)*t,z:a.z+(b.z-a.z)*t});
function norm(p:V,r=1):V{const d=Math.hypot(p.x,p.y,p.z)||1;return{x:p.x*r/d,y:p.y*r/d,z:p.z*r/d};}
function seeded(){let s=741903;return()=>{s=(Math.imul(1664525,s)+1013904223)>>>0;return s/4294967296;};}

/** Deterministic 3D anatomy projected to a high resolution light field. No images. */
function anatomy(){
 const random=seeded(),nodes:V[]=[],nerves:Nerve[]=[],dust:V[]=[];
 for(let i=0;i<340;i++){const z=2*random()-1,a=random()*TAU,q=Math.sqrt(1-z*z),r=.977+.015*Math.sin(i*2.3)+random()*.022;nodes.push({x:q*Math.cos(a)*r,y:q*Math.sin(a)*r,z:z*r});}
 const edges=new Set<string>();
 const surface=(a:V,b:V,blue:boolean,w:number)=>{
  const axis=norm({x:a.y*b.z-a.z*b.y,y:a.z*b.x-a.x*b.z,z:a.x*b.y-a.y*b.x});
  const wave=.015+random()*.042,phase=random()*TAU;
  const p=Array.from({length:22},(_,k)=>{const t=k/21,v=norm(mix(a,b,t),.986),j=Math.sin(Math.PI*t)*wave*(Math.sin(t*9+phase)+.4*Math.sin(t*23+phase));return{x:v.x+axis.x*j,y:v.y+axis.y*j,z:v.z+axis.z*j};});
  nerves.push({p,blue,w,z:p.reduce((v,p)=>v+p.z,0)/p.length});
 };
 nodes.forEach((a,i)=>{
  const near=nodes.map((b,j)=>({j,d:Math.hypot(a.x-b.x,a.y-b.y,a.z-b.z)})).filter(v=>v.j!==i).sort((a,b)=>a.d-b.d);
  near.slice(0,3+(i%3===0?1:0)).forEach(({j})=>{const key=`${Math.min(i,j)}:${Math.max(i,j)}`;if(edges.has(key))return;edges.add(key);surface(a,nodes[j],random()<.19,.4+Math.pow(random(),2)*2.5);});
 });
 // Main axons wind out from the nucleus; dendrites fork to the surface graph.
 for(let i=0;i<40;i++){
  const a=i/40*TAU+(random()-.5)*.16,bend=(random()-.5)*.6,endZ=.15+random()*.3;
  const p=Array.from({length:40},(_,k)=>{const t=k/39,theta=a+bend*Math.sin(t*Math.PI)+.035*Math.sin(t*14+i),r=.025+.93*t;return{x:Math.cos(theta)*r,y:Math.sin(theta)*r,z:.76*(1-t)+endZ*t};});
  nerves.push({p,blue:i%7===0,w:1.1+random()*2.2,z:.5});
  for(let j=0;j<3;j++){
   const start=p[14+j*7],target=nodes.filter(v=>v.z>0).sort((a,b)=>Math.hypot(a.x-start.x,a.y-start.y)-Math.hypot(b.x-start.x,b.y-start.y))[2+j];
   const branch=Array.from({length:18},(_,k)=>{const t=k/17,v=mix(start,target,t),w=Math.sin(t*Math.PI)*.06;return{x:v.x-Math.sin(a)*w,y:v.y+Math.cos(a)*w,z:v.z};});
   nerves.push({p:branch,blue:i%8===0,w:.55+random()*.8,z:.55});
  }
 }
 for(let i=0;i<310;i++){const a=random()*TAU,r=.98+random()*.24;dust.push({x:Math.cos(a)*r,y:Math.sin(a)*r,z:random()});}
 nerves.sort((a,b)=>a.z-b.z);return{nodes,nerves,dust};
}
type Model=ReturnType<typeof anatomy>;
function path(ctx:CanvasRenderingContext2D,p:V[]){ctx.beginPath();p.forEach((v,i)=>{const q=project(v);if(i===0)ctx.moveTo(q.x,q.y);else ctx.lineTo(q.x,q.y);});}
function glow(ctx:CanvasRenderingContext2D,x:number,y:number,r:number,c:number[],a:number){
 const g=ctx.createRadialGradient(x,y,0,x,y,r);g.addColorStop(0,rgba(c,a));g.addColorStop(.12,rgba(c,a*.7));g.addColorStop(.4,rgba(c,a*.16));g.addColorStop(1,rgba(c,0));ctx.fillStyle=g;ctx.fillRect(x-r,y-r,r*2,r*2);
}
function drawAnatomy(canvas:HTMLCanvasElement,m:Model){
 const ctx=canvas.getContext('2d');if(!ctx)return;
 ctx.setTransform(canvas.width/SIZE,0,0,canvas.height/SIZE,0,0);ctx.clearRect(0,0,SIZE,SIZE);ctx.lineCap='round';ctx.lineJoin='round';
 const shell=ctx.createRadialGradient(470,465,20,500,500,R);shell.addColorStop(0,'rgba(135,63,18,.17)');shell.addColorStop(.6,'rgba(59,25,12,.18)');shell.addColorStop(.94,'rgba(103,69,37,.24)');shell.addColorStop(1,'rgba(151,139,121,.12)');
 ctx.fillStyle=shell;ctx.beginPath();ctx.arc(500,500,R,0,TAU);ctx.fill();ctx.globalCompositeOperation='lighter';
 for(const n of m.nerves){
  const f=(n.z+1)/2,c=n.blue?ice:gold,intensity=.12+f*.6;path(ctx,n.p);
  ctx.lineWidth=n.w*7;ctx.strokeStyle=rgba(c,intensity*.035);ctx.stroke();ctx.lineWidth=n.w*3;ctx.strokeStyle=rgba(c,intensity*.11);ctx.stroke();ctx.lineWidth=n.w;ctx.strokeStyle=rgba(c,intensity*.8);ctx.stroke();
  if(n.w>1.5){ctx.lineWidth=n.w*.28;ctx.strokeStyle=rgba(n.blue?[211,235,255]:[255,228,190],intensity*.68);ctx.stroke();}
 }
 m.nerves.forEach((n,i)=>{if(i%3||n.z<-.3)return;for(let k=5;k<n.p.length;k+=5){const p=project(n.p[k]);glow(ctx,p.x,p.y,5,n.blue?ice:gold,.18);}});
 m.nodes.forEach((v,i)=>{const p=project(v),f=(v.z+1)*.5,c=i%7===0?ice:gold,r=4+f*6+(i%9===0?4:0);
  glow(ctx,p.x,p.y,r*2,c,.09+f*.22);ctx.fillStyle=rgba(i%7===0?[201,232,255]:[255,230,197],.16+f*.65);ctx.beginPath();ctx.arc(p.x,p.y,.65+f*1.25,0,TAU);ctx.fill();
  if(i%9===0&&v.z>0){ctx.strokeStyle=rgba(c,.22);ctx.lineWidth=.7;ctx.beginPath();ctx.moveTo(p.x-7,p.y);ctx.lineTo(p.x+7,p.y);ctx.moveTo(p.x,p.y-7);ctx.lineTo(p.x,p.y+7);ctx.stroke();}
 });
 // A broken silver and amber contour replaces the previous opaque ball.
 for(let i=0;i<110;i++){const a=i/110*TAU,b=a+.025+(i%4)*.009;ctx.strokeStyle=i%4===0?'rgba(255,228,192,.68)':'rgba(191,212,225,.2)';ctx.lineWidth=i%4===0?2.2:.9;ctx.beginPath();ctx.arc(500,500,R+Math.sin(i*1.7)*2,a,b);ctx.stroke();}
 m.dust.forEach((v,i)=>{const p=project(v);glow(ctx,p.x,p.y,i%13===0?5:2.5,gold,i%13===0?.36:.17);});
 glow(ctx,510,494,210,gold,.23);glow(ctx,510,494,91,[255,192,88],.60);
 for(let i=0;i<28;i++){const a=i/28*TAU,l=23+(i*29%85);ctx.strokeStyle='rgba(255,215,143,.42)';ctx.lineWidth=.55+(i%4)*.3;ctx.beginPath();ctx.moveTo(510,494);ctx.quadraticCurveTo(510+Math.cos(a+.22)*l*.6,494+Math.sin(a+.22)*l*.6,510+Math.cos(a)*l,494+Math.sin(a)*l);ctx.stroke();}
 for(let i=0;i<9;i++){ctx.strokeStyle=`rgba(255,225,169,${.1+i*.045})`;ctx.lineWidth=.8;ctx.beginPath();ctx.ellipse(510,494,13+i*2.8,22+i*3.8,.1+i*.31,0,TAU);ctx.stroke();}
 glow(ctx,510,494,43,[255,218,143],.95);glow(ctx,510,494,20,[255,246,218],1);glow(ctx,510,494,7,[255,255,251],1);ctx.globalCompositeOperation='source-over';
}

/** Cached anatomical layers and discrete impulses, with no scale/breath animation. */
export function OrganicSphere({motion,processing,startupProgress}:Props){
 const ref=useRef<HTMLCanvasElement>(null),current=useRef({motion,processing,startupProgress});current.current={motion,processing,startupProgress};
 useEffect(()=>{
  const canvas=ref.current;if(!canvas)return;const ctx=canvas.getContext('2d');if(!ctx)return;
  const m=anatomy(),layer=document.createElement('canvas'),media=window.matchMedia('(prefers-reduced-motion: reduce)');
  let width=0,height=0,frame=0,previous=0,time=0,running=true,lastBoot=-1;
  const resize=()=>{const b=canvas.getBoundingClientRect();if(!b.width||!b.height)return;const dpr=Math.min(window.devicePixelRatio||1,2);width=Math.round(b.width*dpr);height=Math.round(b.height*dpr);canvas.width=width;canvas.height=height;layer.width=width;layer.height=height;drawAnatomy(layer,m);lastBoot=-1;};
  const observer=new ResizeObserver(resize);observer.observe(canvas);resize();
  const draw=(stamp:number)=>{
   if(!running)return;frame=requestAnimationFrame(draw);if(stamp-previous<(!document.hasFocus()&&!current.current.processing?90:32))return;
   const p=current.current,active=p.motion&&!media.matches&&!document.hidden,delta=Math.min((stamp-previous)/1000,.1);previous=stamp;
   const boot=Math.max(0,Math.min(1,p.startupProgress/100));if(!active&&lastBoot===boot)return;lastBoot=boot;if(active)time+=delta*(p.processing?1.65:1);
   ctx.setTransform(1,0,0,1,0,0);ctx.clearRect(0,0,width,height);ctx.globalAlpha=.08+boot*.92;ctx.drawImage(layer,0,0);ctx.globalAlpha=1;if(!active||boot<.35)return;
   ctx.setTransform(width/SIZE,0,0,height/SIZE,0,0);ctx.globalCompositeOperation='lighter';
   for(let i=0;i<48;i++){const n=m.nerves[(i*43)%m.nerves.length],cycle=(time*.19+i*.618)%2.4;if(cycle>1)continue;const t=cycle*(n.p.length-1),index=Math.floor(t),q=project(mix(n.p[index],n.p[Math.min(index+1,n.p.length-1)],t-index)),a=Math.sin(cycle*Math.PI)*(.4+Math.max(0,n.z)*.6)*boot;glow(ctx,q.x,q.y,11,n.blue?ice:gold,a*.38);glow(ctx,q.x,q.y,3,[255,238,206],a*.8);}
   ctx.globalCompositeOperation='source-over';
  };
  frame=requestAnimationFrame(draw);return()=>{running=false;cancelAnimationFrame(frame);observer.disconnect();};
 },[]);
 return <canvas ref={ref} style={{width:'100%',height:'100%',display:'block'}} aria-hidden="true"/>;
}
