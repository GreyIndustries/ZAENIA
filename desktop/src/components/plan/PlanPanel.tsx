import { useState } from "react";
import type { TaskRecord } from "../../core/taskModel";
import { CalendarPanel } from "../calendar/CalendarPanel";
import { TasksDashboard } from "../tasks/TasksDashboard";
import { RemindersPanel } from "../status/StatusExtras";
import "./PlanPanel.css";

type View = "both" | "calendar" | "tasks" | "reminders";
const VIEW_KEY = "zaenia.planView";
const VIEWS: { id: View; label: string }[] = [{ id: "both", label: "Both" }, { id: "calendar", label: "Calendar" }, { id: "tasks", label: "Tasks" }, { id: "reminders", label: "Reminders" }];

function readView(): View {
  try { const saved = localStorage.getItem(VIEW_KEY); return saved === "calendar" || saved === "tasks" || saved === "reminders" ? saved : "both"; }
  catch { return "both"; }
}

/**
 * Tasks & Calendar in one tab: the month and the selected day on one side,
 * the task list on the other (stacked in a narrow window). Tasks with a
 * deadline also show on their day in the calendar.
 */
export function PlanPanel({ remote, tasksVersion = 0, calendarVersion = 0 }: { remote: boolean; tasksVersion?: number; calendarVersion?: number }) {
  const [view, setView] = useState<View>(readView);
  const [tasks, setTasks] = useState<TaskRecord[]>([]);
  const choose = (next: View) => { setView(next); try { localStorage.setItem(VIEW_KEY, next); } catch { /* optional */ } };
  return <div className="plan-panel" data-view={view}>
    <div className="plan-panel__switch" role="radiogroup" aria-label="Show">
      {VIEWS.map(item => <button key={item.id} type="button" role="radio" aria-checked={view === item.id}
        className={view === item.id ? "plan-panel__view plan-panel__view--on" : "plan-panel__view"} onClick={() => choose(item.id)}>{item.label}</button>)}
    </div>
    <div className="plan-panel__cols">
      {/* Both stay mounted (one hidden by CSS), so task deadlines still show on the calendar. */}
      <section className="plan-panel__col plan-panel__col--calendar" aria-label="Calendar" hidden={view === "tasks" || view === "reminders"}>
        <CalendarPanel refreshVersion={calendarVersion} tasks={tasks}/>
      </section>
      <section className="plan-panel__col plan-panel__col--tasks" aria-label="Tasks" hidden={view === "calendar" || view === "reminders"}>
        <TasksDashboard remote={remote} refreshVersion={tasksVersion} onTasks={setTasks}/>
      </section>
      {view === "reminders" && <section className="plan-panel__col" aria-label="Reminders"><RemindersPanel/></section>}
    </div>
  </div>;
}
