import { createContext, useContext, type ReactNode } from "react";
/** A window's own controls (layout, minimise, maximise, close), drawn at the right end of preview 05's top row. */
export const WindowControls = createContext<ReactNode>(null);
export const useWindowControls = () => useContext(WindowControls);
