// La seule porte vers le noyau : son API locale (fabrique\noyau\api.py). Le jeton de la fenêtre est un cookie posé à l'entrée ;
// une écriture porte en plus l'en-tête X-Fabrique. Noyau relancé (401) : la fenêtre rouvre l'entrée sur l'écran courant.
import { useCallback, useEffect, useRef, useState } from "react";

declare global {
  interface Window {
    pywebview?: { api: { entrer(vers: string): void; ouvrir(adresse: string): Promise<boolean>; plein_ecran(): void } };
    fabriqueCachee?: () => void; // appelée par la fenêtre quand elle se cache
  }
}

export class ErreurApi extends Error {
  constructor(
    public statut: number,
    message: string,
  ) {
    super(message);
  }
}

let reentree = false;

async function reponse<T>(r: Response): Promise<T> {
  if (r.status === 401) {
    if (!reentree && window.pywebview) {
      reentree = true;
      window.pywebview.api.entrer(location.pathname + location.hash);
    }
    throw new ErreurApi(401, "Reconnexion à Fabrique…");
  }
  if (!r.ok) {
    let texte = "Fabrique n'a pas pu répondre.";
    try {
      const j = await r.json();
      if (typeof j.detail === "string") texte = j.detail;
      else if (typeof j.message === "string") texte = j.message;
    } catch {
      /* réponse sans corps lisible : le texte général suffit */
    }
    throw new ErreurApi(r.status, texte);
  }
  return r.json() as Promise<T>;
}

const INJOIGNABLE = "Fabrique ne répond pas pour l'instant : nouvel essai dans un instant.";

async function appel(chemin: string, options: RequestInit): Promise<Response> {
  try {
    return await fetch(`/api${chemin}`, { credentials: "same-origin", ...options });
  } catch {
    throw new ErreurApi(0, INJOIGNABLE); // noyau en train de redémarrer (garde, mise à jour)
  }
}

export async function lire<T>(chemin: string): Promise<T> {
  return reponse<T>(await appel(chemin, {}));
}

export async function agir<T = { message: string }>(chemin: string, corps?: unknown): Promise<T> {
  return reponse<T>(
    await appel(chemin, {
      method: "POST",
      headers: { "X-Fabrique": "fenetre", "Content-Type": "application/json" },
      body: corps === undefined ? undefined : JSON.stringify(corps),
    }),
  );
}

/** Une image (réduite à `largeur`), un son ou une vidéo des sessions ou des rendus de Bramble Studio. */
export const fichier = (chemin: string, largeur?: number) =>
  `/api/fichier?chemin=${encodeURIComponent(chemin)}${largeur ? `&largeur=${largeur}` : ""}`;

const memoire = new Map<string, unknown>(); // ce qui a déjà été lu : l'écran s'affiche tout de suite, puis se met à jour

/** Lit `chemin` (null : rien), garde la dernière réponse en mémoire et relit toutes les `intervalle` ms si demandé. */
export function useLire<T>(chemin: string | null, intervalle = 0) {
  const [donnees, setDonnees] = useState<T | undefined>(() => (chemin ? (memoire.get(chemin) as T | undefined) : undefined));
  const [erreur, setErreur] = useState<string>("");
  const courant = useRef(chemin);
  courant.current = chemin;
  const reessai = useRef<ReturnType<typeof setTimeout>>(undefined);

  const relire = useCallback(async () => {
    if (!chemin) return;
    clearTimeout(reessai.current);
    try {
      const d = await lire<T>(chemin);
      memoire.set(chemin, d);
      if (courant.current === chemin) {
        setDonnees(d);
        setErreur("");
      }
    } catch (e) {
      if (courant.current !== chemin) return;
      setErreur(e instanceof Error ? e.message : String(e));
      if (!intervalle) reessai.current = setTimeout(relire, 5000); // sans relecture régulière : un nouvel essai, jusqu'à ce qu'il réponde
    }
  }, [chemin, intervalle]);

  useEffect(() => {
    setDonnees(chemin ? (memoire.get(chemin) as T | undefined) : undefined);
    setErreur("");
    relire();
    const t = intervalle ? setInterval(relire, intervalle) : undefined;
    return () => {
      clearInterval(t);
      clearTimeout(reessai.current);
    };
  }, [chemin, intervalle, relire]);

  return { donnees, erreur, relire };
}

// --- ce que répond le noyau (fabrique\noyau\schemas.py) ---

export interface Session {
  id: string;
  nom: string;
  essais: boolean;
  pause: boolean;
  archivee: string;
  videos: number;
  a_faire: number;
  prochain: string;
}

export interface Script {
  code: string;
  titre: string;
  statut: string;
  date_prevue: string;
  versions: number;
  validee: boolean;
  vignette: number;
  personnages: string[];
}

export interface Scene {
  id: number;
  narration?: string;
  image?: string;
  motion?: string;
  bramble?: string;
  camera?: string;
}

export interface Plan {
  n: number;
  image: string;
  scenes: number[];
  bramble: boolean;
}

export interface ScriptDetail {
  code: string;
  titre: string;
  statut: string;
  date_prevue: string;
  contenu: {
    title?: string;
    theme?: string;
    description?: string;
    language?: string;
    cast?: Record<string, string>;
    thumbnail_scene?: number;
    scenes?: Scene[];
  };
  plans: Plan[];
  traductions: string[];
}

export interface RendusBramble {
  images: Record<string, string>;
  videos: { langue: string; chemin: string }[];
  langues: string[];
  voix: Record<string, string>;
  durees: Record<string, number>;
}

export interface Comparaison {
  dossier: string;
  titre: string;
  date: string;
  duree: number;
  plans: { debut: number; duree: number }[];
  bramble: string;
  fabrique: string;
}

export interface Animatique {
  etat: "absente" | "en_cours" | "faite" | "erreur";
  message: string;
  fait: number;
  tout: number;
  autre: boolean;
  video: string;
  date: string;
  fin: number;
  plans: { n: number; debut: number; duree: number }[];
  notes: { id: string; t: number; texte: string; langue: string; date: string }[];
}

export interface Reference {
  id: number;
  chemin: string;
  vue: string;
  validee: boolean;
}

export interface Personnage {
  id: number;
  nom: string;
  role: string;
  statut: string;
  description: string;
  references: Reference[];
  voix: { langue: string; chemin: string }[];
}

export interface Univers {
  personnages: Personnage[];
  lieux: { id: number; nom: string; description: string }[];
  langues: { code: string; nom: string }[];
  style: string;
}

export interface ElementCalendrier {
  session: string;
  session_nom: string;
  code: string;
  titre: string;
  date: string;
  statut: string;
  statut_nom: string;
  pret_vers: string;
}

export interface TacheFile {
  id: number;
  titre: string;
  session: string;
  etat: string;
  raison: string;
  alertes: string[];
  progression: string;
  reste_s: number | null;
  pret_vers: string;
  banc: number;
}

export interface Machine {
  carte: string;
  disque_go: number;
  carte_prise: string;
}

export interface Etat {
  version: string;
  mode: string;
  alertes: string[];
  sauvegarde: { etat?: string; fin?: string; fichier?: string };
}

export interface Versions {
  installee: string;
  proposee: string | null;
  nouveautes: string[];
  raison: string;
}

export interface Sauvegardes {
  dossier: string;
  liste: { nom: string; date: string; taille_mo: number }[];
  derniere: { etat?: string; fin?: string; fichier?: string; message?: string };
}

export interface Cle {
  nom: string;
  titre: string;
  ok: boolean;
}
