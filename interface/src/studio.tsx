// Ce que tous les écrans partagent : la session choisie, ses personnages (portraits), l'état de la carte graphique.
import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { useLire, type Machine, type Personnage, type Session, type Univers } from "./api";

interface Studio {
  sessions: Session[];
  session?: Session;
  choisir(id: string): void;
  univers?: Univers;
  personnages: Personnage[]; // un seul par nom, à la casse près
  portraits: Record<string, string>; // nom (et nom en minuscules) -> image de son portrait
  distribution: string[];
  machine?: Machine;
}

const Contexte = createContext<Studio>({ sessions: [], choisir: () => {}, personnages: [], portraits: {}, distribution: [] });
export const useStudio = () => useContext(Contexte);

export function FournisseurStudio({ children }: { children: ReactNode }) {
  const { donnees: sessions = [] } = useLire<Session[]>("/sessions", 30000);
  const [choisie, setChoisie] = useState(() => localStorage.getItem("session") ?? "");
  const actives = sessions.filter((s) => !s.archivee);
  const session = actives.find((s) => s.id === choisie) ?? actives.find((s) => !s.essais) ?? actives[0];
  const { donnees: univers } = useLire<Univers>(session ? `/sessions/${session.id}/univers` : null);
  const { donnees: machine } = useLire<Machine>("/machine", 10000);

  useEffect(() => {
    if (session) localStorage.setItem("session", session.id);
  }, [session]);

  const valeur = useMemo<Studio>(() => {
    const parNom = new Map<string, Personnage>();
    for (const p of univers?.personnages ?? []) {
      const cle = p.nom.toLowerCase();
      const autre = parNom.get(cle);
      if (!autre) parNom.set(cle, p);
      else {
        const [principal, second] = p.description.length > autre.description.length ? [p, autre] : [autre, p];
        parNom.set(cle, { ...principal, references: principal.references.length ? principal.references : second.references, voix: principal.voix.length ? principal.voix : second.voix });
      }
    }
    const personnages = [...parNom.values()];
    const portraits: Record<string, string> = {};
    for (const p of personnages) if (p.references[0]) portraits[p.nom] = portraits[p.nom.toLowerCase()] = p.references[0].chemin;
    return { sessions: actives, session, choisir: setChoisie, univers, personnages, portraits, distribution: personnages.map((p) => p.nom), machine };
  }, [sessions, session, univers, machine]); // eslint-disable-line react-hooks/exhaustive-deps

  return <Contexte.Provider value={valeur}>{children}</Contexte.Provider>;
}
