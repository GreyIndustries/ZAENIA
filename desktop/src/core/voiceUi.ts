import { PAGE_CATALOG, flattenPages } from "./pageCatalog";
import type { PageActivity } from "./pageActivity";
import type { SnapCount } from "./windowLayout";

export type PageRoute = { app: string; path: string[]; label: string };
export type UiCommand = { kind: "navigate"; route: PageRoute } | { kind: "ambiguous"; labels: string[] }
  | { kind: "arrange"; count: SnapCount; apps?: string[] } | { kind: "undo-arrange" }
  | { kind: "pages" | "next" | "previous" | "recent" | "resume" | "voice-help" | "launcher" | "clear-recent" }
  | { kind: "workspace"; id: string } | { kind: "press"; label: string } | { kind: "field"; label: string; value: string }
  | { kind: "toggle"; label: string; on: boolean }
  | { kind: "back" | "forward" | "restore-size" } | { kind: "focus-pane"; direction: "next" | "previous" | "left" | "right" | "up" | "down" }
  | { kind: "open-tab"; route: PageRoute } | { kind: "split-pages"; routes: [PageRoute, PageRoute] } | { kind: "tabs" | "close-tab" | "reopen-tab" };
const clean = (value: string) => value.toLowerCase().replace(/[’']/g, "").replace(/&/g, " and ").replace(/[^a-z0-9 ]/g, " ").replace(/\s+/g, " ").trim();
const names: Record<string, string[]> = { overview: ["core","dashboard","home"],tasks:["life","calendar","tasks"],system:["settings","preferences"],codedoctor:["code doctor","code doctor and files","code"],research:["research"],notes:["notes"],workbench:["workbench"],music:["music"],arena:["arena"],assistant:["assistant"],status:["status"],security:["security"],remote:["pc remote","remote"] };
export function parseUiCommand(input: string, currentApp = ""): UiCommand | null {
  const text = clean(input).replace(/^(?:(?:hey )?(?:zae|zaenia|zay) |please )+/, "");
  if (!text || text.length > 500) return null;
  if (/^(?:undo|revert|restore)(?: the| my)? (?:window )?(?:arrangement|snap layout|split layout)$/.test(text)) return {kind:"undo-arrange"};
  // Screen history and pane focus (Claude 2026-11-11). Whole-utterance matches only.
  if (/^(?:go |take me )?back(?: (?:a|one) (?:page|screen)| to the (?:previous|last) (?:page|screen))?$|^(?:previous|last) screen$/.test(text)) return {kind:"back"};
  if (/^(?:go )?forward(?: (?:a|one) (?:page|screen))?$|^next screen$/.test(text)) return {kind:"forward"};
  if (/^(?:restore|return to|go back to)(?: the| its| my| this)? (?:normal |previous |original )?(?:window )?(?:size|layout position|pane size|split)$|^(?:exit|leave) full ?screen$|^un ?maximi[sz]e(?: it| this| the window| this window)?$/.test(text)) return {kind:"restore-size"};
  const pane = /^(?:(?:focus|switch to|go to|select|move to)(?: the)? )?(next|previous|left|right|top|bottom|upper|lower) (?:pane|window|panel)$/.exec(text);
  if (pane) return {kind:"focus-pane",direction:(({top:"up",upper:"up",bottom:"down",lower:"down"} as Record<string,"up"|"down">)[pane[1]] ?? pane[1]) as "next"|"previous"|"left"|"right"|"up"|"down"};
  const split = /^(?:(?:split|arrange|tile|snap)(?: (?:the|my|these|open|app|screen|windows|workspace|into|in|a|the))*|use(?: a)?) (two|three|four|2|3|4)(?: (?:app |window )?(?:windows?|panes?|columns?|layout|way split|screen))*$/.exec(text);
  if (split) return {kind:"arrange",count:({two:2,three:3,four:4}[split[1]] ?? Number(split[1])) as SnapCount};
  const named = /^(?:put|arrange|tile|snap|split) (.+?) (?:side by side|in (?:two|three|four|2|3|4)(?: windows?| panes?| columns?)?)$/.exec(text);
  if (named) {
    const found = Object.entries(names).map(([id,aliases])=>({id,index:Math.min(...aliases.map(name=>named[1].search(new RegExp(`\\b${name}\\b`))).filter(index=>index>=0))})).filter(item=>Number.isFinite(item.index)).sort((a,b)=>a.index-b.index).map(item=>item.id).filter(id=>id!=="overview"&&id!=="remote");
    const apps=[...new Set(found.map(id=>["status","security"].includes(id)?"system":id))];
    if(apps.length>=2&&apps.length<=4)return {kind:"arrange",count:apps.length as SnapCount,apps};
  }
  // Screen tabs (Claude 2026-11-11): "show tabs", "close this tab", "open suggestions in a new tab", "split build requests and suggestions".
  if (/^(?:show|open|list)(?: (?:my|the|all|open))* tabs(?: manager)?$|^(?:open )?(?:the )?tab manager$/.test(text))return {kind:"tabs"};
  if (/^close(?: (?:this|the|current))? tab$/.test(text))return {kind:"close-tab"};
  if (/^(?:reopen|restore|undo close)(?: (?:the|my|last))* (?:closed )?tab$/.test(text))return {kind:"reopen-tab"};
  const inTab = /^(?:open|show|put) (.+?) in (?:a )?new tab$/.exec(text);
  if (inTab) { const found = matchPages(inTab[1].replace(/^(?:the|my) /,"").replace(/ (?:page|tab|screen)$/,""), currentApp); return found.length === 1 ? {kind:"open-tab",route:found[0]} : found.length ? {kind:"ambiguous",labels:found.map(route=>route.label).slice(0,6)} : null; }
  const pair = /^(?:split|show|put) (.+?) (?:and|with) (.+?)(?: side by side| in (?:two|2) (?:panes|tabs))?$/.exec(text);
  if (pair) {
    const first = matchPages(pair[1].replace(/^(?:the|my) /,""), currentApp), second = matchPages(pair[2].replace(/^(?:the|my) /,""), currentApp);
    if (first.length === 1 && second.length === 1) return {kind:"split-pages",routes:[first[0], second[0]]};
  }
  if (/^(?:show|open)(?: the)? (?:app launcher|apps|all apps|core launcher)$/.test(text))return {kind:"launcher"};
  if (/^(?:show|open)(?: the)? (?:pages|page directory|all pages)$/.test(text))return {kind:"pages"};
  if (/^(?:go to |open |show )?(?:the )?next page$/.test(text))return {kind:"next"};
  if (/^(?:go to |open |show )?(?:the )?(?:previous|last) page$/.test(text))return {kind:"previous"};
  if (/^(?:what (?:was|have) i (?:recently )?(?:been )?(?:working on|doing)(?: here| on this page)?|read (?:my )?recent (?:page )?work|show recent work)$/.test(text))return {kind:"recent"};
  if (/^(?:resume|continue)(?: my| the)? (?:last|recent|previous) (?:work|activity)$|^pick up where i left off$/.test(text))return {kind:"resume"};
  if (/^(?:show|list|read)(?: my| the)? (?:voice commands|available actions)$|^what can i (?:say|do) (?:here|on this page)$/.test(text))return {kind:"voice-help"};
  if (/^(?:clear|forget)(?: my| the)? recent page work$/.test(text))return {kind:"clear-recent"};
  const workspace=/^(?:open|show)(?: the)? (life|health|know|create|build|settings) workspace$/.exec(text);
  if(workspace)return {kind:"workspace",id:({life:"plan",settings:"system"} as Record<string,string>)[workspace[1]]??workspace[1]};
  const press=/^(?:press|click|tap)(?: the)? (.+?)(?: button)?$/.exec(text);if(press)return {kind:"press",label:press[1]};
  const field=/^(?:set|fill)(?: the)? (.+?)(?: field)? (?:to|with) (.+)$/i.exec(input.trim().replace(/^(?:(?:zae|zaenia|zay|please)[, ]+)+/i,""));
  if(field)return {kind:"field",label:field[1],value:field[2]};
  const toggle=/^(?:turn|switch) (on|off) (.+)$/.exec(text);if(toggle)return {kind:"toggle",label:toggle[2],on:toggle[1]==="on"};
  const opening=/^(?:open|show|go to|take me to|switch to|bring up|pull up) (.+)$/.exec(text);if(!opening)return null;
  const wanted=opening[1].replace(/^(?:the|my) /,"").replace(/ (?:page|tab|screen)$/,"");
  const choices=matchPages(wanted,currentApp);
  if(choices.length===1)return {kind:"navigate",route:choices[0]};
  return choices.length?{kind:"ambiguous",labels:choices.map(route=>route.label).slice(0,6)}:null;
}
const SHORTCUTS: Record<string,PageRoute>={
  "recipes":{app:"tasks",path:["fitness","food","cookbook"],label:"LIFE / Fitness & Health / Food / Cookbook"},
  "meal planner":{app:"tasks",path:["fitness","food","planner"],label:"LIFE / Fitness & Health / Food / Weekly meal planner"},
  "training plans":{app:"tasks",path:["fitness","training","plans"],label:"LIFE / Fitness & Health / Training / Plans & targets"},
  "blueprints":{app:"workbench",path:["blueprint"],label:"Workbench / Blueprint"},
  "route":{app:"tasks",path:["map","directions"],label:"LIFE / GODSPEED / Directions"},
};
type Indexed={route:PageRoute;names:string[];words:string};
let index: Indexed[]|null=null;
/** Every catalogue page with the spoken/typed names that reach it (built once). */
function pageIndex(): Indexed[] {
  if(index)return index;
  index=[];
  for(const app of PAGE_CATALOG){
    const aliases=names[app.id]??[clean(app.label)];
    index.push({route:{app:app.id,path:[],label:app.label},names:aliases,words:aliases.join(" ")});
    for(const page of flattenPages(app)){
      const full=clean(page.label.replace(/\//g," ")),last=clean(page.label.split(" / ").slice(-1)[0]!);
      const labels=[full,last,...aliases.flatMap(alias=>[`${alias} ${full}`,`${alias} ${last}`])];
      if(app.id==="tasks"&&page.path[0]==="fitness")labels.push(`fitness ${last}`,`fitness and health ${last}`);
      if(app.id==="tasks"&&page.path[0]==="map")labels.push(`godspeed ${last}`,`map ${last}`);
      // Spoken names usually drop articles: "research library" for "The Library" (Claude 2026-11-11).
      const spoken=[...new Set([...labels,...labels.map(item=>item.replace(/\bthe /g,""))])];
      index.push({route:{app:app.id,path:page.path,label:`${app.label} / ${page.label}`},names:spoken,words:spoken.join(" ")});
    }
  }
  return index;
}
/**
 * Pages whose name matches exactly: the one rule used by voice ("open cookbook") and by typed search's best match,
 * so both resolve to the same page. Prefers an app itself, then a single match inside the current app.
 */
export function matchPages(input: string, currentApp = ""): PageRoute[] {
  const wanted=clean(input).replace(/^(?:the|my) /,"").replace(/ (?:page|tab|screen)$/,"");
  if(!wanted)return [];
  if(SHORTCUTS[wanted])return [SHORTCUTS[wanted]];
  const bare=wanted.replace(/\bthe /g,"");
  const unique=pageIndex().filter(item=>item.names.includes(wanted)||item.names.includes(bare)).map(item=>item.route);
  const direct=unique.find(route=>route.path.length===0);if(direct)return [direct];
  const local=unique.filter(route=>route.app===currentApp);
  return local.length===1?local:unique;
}
/** Typed search over every page: exact matches first (same as voice), then prefix, word-start and substring matches. */
export function searchPages(input: string, limit = 12): PageRoute[] {
  const query=clean(input);if(!query)return [];
  const exact=matchPages(query);
  const words=query.split(" ");
  const scored=pageIndex().map(item=>{
    const label=clean(item.route.label.split(" / ").slice(-1)[0]!);
    const all=words.every(word=>item.words.includes(word));
    const score=label===query?0:label.startsWith(query)?1:new RegExp(`\\b${query.replace(/[.*+?^${}()|[\]\\]/g,"\\$&")}`).test(label)?2:label.includes(query)?3:all?4:9;
    return {route:item.route,score:score+item.route.path.length*.01};
  }).filter(item=>item.score<9).sort((a,b)=>a.score-b.score).map(item=>item.route);
  return [...new Map([...exact,...scored].map(route=>[`${route.app}/${route.path.join("/")}`,route])).values()].slice(0,limit);
}
export function routeSteps(route: PageRoute): {page:string;tab:string;key:string}[] {
  const [first,second,third]=route.path;const steps:{page:string;tab:string;key:string}[]=[];
  const add=(page:string,tab:string,key=`zaenia.pageTab.${page}`)=>{if(tab)steps.push({page,tab,key});};
  if(route.app==="tasks"){
    add("life",first);
    if(first==="plan")add("plan",second,"zaenia.plan.tab");
    if(first==="map")add("godspeed",second,"zaenia.pageTab.godspeed");
    if(first==="fitness"){
      add("fitness",second,"zaenia.fitness.section");
      if(second==="food")add("fitness-food",third,"zaenia.fitness.food");
      if(second==="training")add("fitness-training",third,"zaenia.fitness.training");
    }
  }else if(route.app==="status"||route.app==="security"){
    add("settingshub",route.app);add(route.app,first);
  }else if(route.app==="system"){add("settingshub","settings");add("settings",first);}
  else if(route.app==="research")add("research",first,"zaenia.researchTab");
  else if(route.app==="music")add("music",first,"zaenia.music.tab");
  else {add(route.app,first);if(route.app==="assistant"&&first==="tools"&&second){const child=PAGE_CATALOG.find(app=>app.id==="assistant")!.pages.find(page=>page.id==="tools")!.children!.find(page=>page.id===second);if(child)add("assistant-tools",child.label);}}
  return steps;
}
export function routeForActivity(activity: PageActivity): PageRoute | null {
  const {navigator,page}=activity;
  const app = ["life","plan","fitness","fitness-food","fitness-training","godspeed"].includes(navigator)?"tasks":navigator==="assistant-tools"?"assistant":navigator==="settings"?"system":navigator;
  const path=navigator==="life"?[page]:navigator==="plan"?["plan",page]:navigator==="godspeed"?["map",page]:navigator==="fitness"?["fitness",page]
    :navigator==="fitness-food"?["fitness","food",page]:navigator==="fitness-training"?["fitness","training",page]
    :navigator==="assistant-tools"?["tools",page.toLowerCase()]:[page];
  const spec=PAGE_CATALOG.find(item=>item.id===app);if(!spec)return null;
  const found=flattenPages(spec).find(item=>item.id===path.join("/"));return found?{app,path,label:`${spec.label} / ${found.label}`}:null;
}

const forbidden = /\b(?:approve|authorize|confirm|install|delete|remove|archive|send|publish|deploy|commit|push|merge|unlock|password|passkey|token|secret|api key|credential|payment|purchase|reset|disable security)\b/i;
function visible(element: HTMLElement) { return !element.closest("[hidden],[inert]") && element.getClientRects().length>0 && getComputedStyle(element).visibility!=="hidden"; }
function label(element: HTMLElement) {
  const labelled=element.getAttribute("aria-labelledby")?.split(/\s+/).map(id=>document.getElementById(id)?.textContent??"").join(" ");
  const associated=(element as HTMLInputElement).labels;
  return element.getAttribute("aria-label")||labelled||(associated?[...associated].map(node=>node.textContent).join(" "):"")||element.getAttribute("placeholder")||element.textContent||"";
}
export function voiceControls(scope: ParentNode) {
  return [...scope.querySelectorAll<HTMLElement>("button,summary,input:not([type=hidden]),textarea,select")].filter(visible).filter(node=>!node.matches(":disabled")&&node.getAttribute("aria-disabled")!=="true");
}
export function executeUiControl(command: Extract<UiCommand,{kind:"press"|"field"|"toggle"}>,scope:ParentNode): string {
  if(forbidden.test(command.label))return "That control uses its existing protected confirmation. Open that flow and complete its required authentication.";
  const controls=voiceControls(scope).filter(node=>command.kind==="press"?["BUTTON","SUMMARY"].includes(node.tagName):command.kind==="toggle"?node instanceof HTMLInputElement&&["checkbox","radio"].includes(node.type):node.matches("input,textarea,select"));
  const exact=controls.filter(node=>clean(label(node))===clean(command.label));
  const matches=exact.length?exact:controls.filter(node=>clean(label(node)).startsWith(clean(command.label)+" "));
  if(matches.length!==1)return matches.length?`More than one ${command.label} control is visible. Say its full label, sir.`:`I couldn't find an available ${command.label} control on this page, sir.`;
  const target=matches[0];
  if(forbidden.test(label(target))||target.getAttribute("type")==="password"||target.getAttribute("type")==="file"||target.closest(".faceid-approve,.near-code,.calm"))return "That control needs its existing protected or device-specific interaction.";
  target.scrollIntoView({block:"nearest",inline:"nearest"});
  if(command.kind==="press"){target.click();return `Pressed ${command.label}, sir.`;}
  if(command.kind==="toggle"){
    const input=target as HTMLInputElement;if(input.checked!==command.on)input.click();return `${command.label} is ${input.checked?"on":"off"}, sir.`;
  }
  if(target instanceof HTMLSelectElement){
    const option=[...target.options].find(item=>clean(item.label)===clean(command.value)&&!item.disabled);if(!option)return "That option isn't available in this field, sir.";
    target.value=option.value;target.dispatchEvent(new Event("change",{bubbles:true}));
  }else{
    const input=target as HTMLInputElement;
    if(["button","submit","reset","checkbox","radio","file","password"].includes(input.type))return "That field needs its own control.";
    const prototype=target instanceof HTMLTextAreaElement?HTMLTextAreaElement.prototype:HTMLInputElement.prototype;
    Object.getOwnPropertyDescriptor(prototype,"value")!.set!.call(target,command.value);
    target.dispatchEvent(new Event("input",{bubbles:true}));target.dispatchEvent(new Event("change",{bubbles:true}));
  }
  return `Filled ${command.label}, sir. It has not been submitted.`;
}
