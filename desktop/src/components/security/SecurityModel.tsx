import { useMemo, useRef } from "react";
import { css } from "../tools/se3d/engine";
import { SE3DCanvas } from "../tools/se3d/SE3DCanvas";
import { LEVEL_COLOR } from "../tools/se3d/levels";
import { stackScene } from "../tools/se3d/stack";
import { alertCount, groupAreas, LEVEL_WORD, trailSpeed, type AreaLite, type GroupId, type Level, type Signals } from "./securityGroups";

/**
 * The security model as the 3D "SE Stack" (Grey's pick (D), 2026-11-04): the four groups of defenses are the slabs of a
 * tower, coloured by how strong each is right now, with the gate on top and signals climbing the pillars. The numbers are
 * the Security tab's own live readings; nothing here can change a setting.
 */
export function SecurityModel({ areas, score, level, signals }: { areas: AreaLite[]; score: number; level: Level; signals?: Signals }) {
  const latest = useRef({ areas, score, level, signals });
  latest.current = { areas, score, level, signals };

  const ORDER: GroupId[] = ["access", "secrets", "identity", "watch"];   // bottom of the tower first

  const scene = useMemo(() => stackScene({
    layers: () => {
      const groups = groupAreas(latest.current.areas);
      return ORDER.map(id => groups.find(g => g.id === id)!).map(group => ({
        name: group.name, sub: LEVEL_WORD[group.level], level: group.level,
        tip: { key: `sec:${group.id}:${group.areas.map(area => area.level).join("")}`, title: group.name, color: css(LEVEL_COLOR[group.level]), sub: LEVEL_WORD[group.level],
          lines: group.areas.length ? group.areas.map(area => `${area.title}: ${LEVEL_WORD[area.level]}`) : ["Nothing measured yet"], note: group.blurb },
      }));
    },
    gate: () => {
      const { score: points, level: overall } = latest.current;
      return { name: "Security gate", word: `${points} / 100`, score: points, level: overall,
        tip: { key: `sec:gate:${points}:${overall}`, title: "Security gate", color: "#fff2cf", sub: `${points} / 100 · ${LEVEL_WORD[overall]}`,
          lines: ["Every action passes here. The passkey and the permission rules sit outside the SE and cannot be changed by it."], note: "measured live on this PC" } };
    },
    trail: () => { const alerts = alertCount(latest.current.signals); return { speed: trailSpeed(alerts), alert: alerts > 0 }; },
  }), []);

  return <SE3DCanvas scene={scene} label="The security model as a 3D tower: four slabs for the groups of defenses, the security gate on top"
    hint="Drag to turn · hover a slab for what is inside"/>;
}
