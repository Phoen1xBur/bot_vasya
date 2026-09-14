import { create } from "zustand";

interface AppState {
  theme: "dark" | "light";
  muted: boolean;
  setTheme: (t: "dark" | "light") => void;
  toggleMute: () => void;
}

export const useAppStore = create<AppState>((set, get) => ({
  theme: "dark",
  muted: false,
  setTheme: (t) => set({ theme: t }),
  toggleMute: () => {
    const next = !get().muted;
    set({ muted: next });
  },
}));
