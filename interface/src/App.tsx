import * as Menu from "@radix-ui/react-dropdown-menu";
import { Check, ChevronsUpDown, Clapperboard, Home, ListVideo, Maximize2, Settings2, TriangleAlert, Users } from "lucide-react";
import { Component, useEffect, useRef, type ReactNode } from "react";
import { Accueil } from "./ecrans/Accueil";
import { Episode } from "./ecrans/Episode";
import { Episodes } from "./ecrans/Episodes";
import { File } from "./ecrans/File";
import { Personnages } from "./ecrans/Personnages";
import { Systeme } from "./ecrans/Systeme";
import { aller, carteOccupee, useAdresse } from "./outils";
import { useStudio } from "./studio";
import { arreterEcoute, cx, Vide } from "./ui";

const ECRANS = [
  { id: "", nom: "Accueil", icone: Home },
  { id: "episodes", nom: "Épisodes", icone: Clapperboard },
  { id: "personnages", nom: "Personnages", icone: Users },
  { id: "file", nom: "Fabrication", icone: ListVideo },
  { id: "systeme", nom: "Système", icone: Settings2 },
];

export function App() {
  const adresse = useAdresse();
  const ecran = adresse[0] ?? "";
  const zone = useRef<HTMLElement>(null);

  useEffect(() => {
    zone.current?.scrollTo({ top: 0 });
    arreterEcoute();
  }, [adresse.join("/")]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    const touche = (e: KeyboardEvent) => {
      if (e.ctrlKey && !e.altKey && /^(Digit|Numpad)[1-5]$/.test(e.code)) {
        e.preventDefault(); // e.code : la touche, quel que soit le clavier (« & » ou « é » sur un clavier français)
        aller(ECRANS[Number(e.code.slice(-1)) - 1].id);
      } else if (e.key === "F11") {
        e.preventDefault();
        window.pywebview?.api.plein_ecran();
      } else if (e.altKey && e.key === "ArrowLeft") {
        history.back();
      }
    };
    const menu = (e: MouseEvent) => {
      if (!(e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement)) e.preventDefault();
    };
    // fenêtre cachée (croix : elle reste chargée près de l'horloge) : plus aucun son
    const silence = () => {
      arreterEcoute();
      document.querySelectorAll("video").forEach((v) => v.pause());
    };
    const visibilite = () => document.hidden && silence();
    window.fabriqueCachee = silence;
    window.addEventListener("keydown", touche);
    window.addEventListener("contextmenu", menu);
    document.addEventListener("visibilitychange", visibilite);
    return () => {
      window.removeEventListener("keydown", touche);
      window.removeEventListener("contextmenu", menu);
      document.removeEventListener("visibilitychange", visibilite);
    };
  }, []);

  let contenu: ReactNode;
  if (ecran === "episode" && adresse[1] && adresse[2]) contenu = <Episode session={adresse[1]} code={adresse[2]} onglet={adresse[3]} depart={Number(adresse[4]) || 0} />;
  else if (ecran === "episodes") contenu = <Episodes />;
  else if (ecran === "personnages") contenu = <Personnages />;
  else if (ecran === "file") contenu = <File />;
  else if (ecran === "systeme") contenu = <Systeme />;
  else contenu = <Accueil />;

  const actif = ecran === "episode" ? "episodes" : ecran;
  return (
    <div className="flex h-full">
      <Barre actif={actif} />
      <main ref={zone} className="relative min-w-0 flex-1 overflow-y-auto">
        <div key={adresse.slice(0, 3).join("/")} className="animate-entree mx-auto w-full max-w-[1680px] px-10 pt-9 pb-16 2xl:px-14">
          <Secours>{contenu}</Secours>
        </div>
      </main>
    </div>
  );
}

/** Un écran qui plante n'emporte pas toute la fenêtre : un message, et le reste de l'application marche. */
class Secours extends Component<{ children: ReactNode }, { panne: boolean }> {
  state = { panne: false };
  static getDerivedStateFromError() {
    return { panne: true };
  }
  componentDidCatch(e: unknown) {
    console.error(e);
  }
  render() {
    if (!this.state.panne) return this.props.children;
    return (
      <Vide icone={<TriangleAlert className="size-5" />} titre="Cet écran n'a pas pu s'afficher" texte="Le reste de Fabrique fonctionne. Revenez à l'accueil, puis réessayez.">
        <a href="#/" className="mt-2 text-[14px] font-medium text-ambre hover:text-ambre-vif">
          Retour à l'accueil
        </a>
      </Vide>
    );
  }
}

function Barre({ actif }: { actif: string }) {
  const { machine } = useStudio();
  const prise = machine?.carte_prise;
  return (
    <nav className="flex w-[248px] shrink-0 flex-col border-r border-ligne bg-panneau">
      <div className="flex items-center gap-3 px-5 pt-5 pb-4">
        <img src="/icone.png" alt="" className="size-8 rounded-[9px]" draggable={false} />
        <div className="text-[17px] font-semibold tracking-[-0.01em]">Fabrique</div>
      </div>
      <ChoixSession />
      <div className="mt-3 flex flex-col gap-0.5 px-3">
        {ECRANS.map((e, i) => {
          const Icone = e.icone;
          const ici = actif === e.id;
          return (
            <a
              key={e.id}
              href={`#/${e.id}`}
              className={cx(
                "group flex h-10 items-center gap-3 rounded-[10px] px-3 text-[14px] font-medium transition-colors",
                ici ? "bg-survol text-texte" : "text-doux hover:bg-carte-2 hover:text-texte",
              )}
            >
              <Icone className={cx("size-[18px]", ici ? "text-ambre" : "text-pale group-hover:text-doux")} strokeWidth={1.9} />
              <span className="flex-1">{e.nom}</span>
              <kbd className="hidden font-sans text-[11px] text-pale group-hover:inline">Ctrl {i + 1}</kbd>
            </a>
          );
        })}
      </div>
      <div className="mt-auto flex flex-col gap-3 p-4">
        <a href="#/file" className="rounded-[12px] border border-ligne bg-carte px-3.5 py-3 transition-colors hover:border-ligne-forte">
          <div className="flex items-center gap-2 text-[13px] font-medium">
            <span className={cx("size-2 rounded-full", prise ? "bg-ambre shadow-[0_0_10px] shadow-ambre/70" : "bg-vert")} />
            {prise ? "Carte graphique occupée" : "Carte graphique libre"}
          </div>
          <div className="mt-1 text-[12px] leading-snug text-pale">{carteOccupee(prise ?? "")}</div>
        </a>
        <button
          onClick={() => window.pywebview?.api.plein_ecran()}
          className="flex items-center gap-2 px-1 text-[12px] text-pale transition-colors hover:text-doux"
        >
          <Maximize2 className="size-3.5" /> Plein écran <kbd className="ml-auto font-sans">F11</kbd>
        </button>
      </div>
    </nav>
  );
}

function ChoixSession() {
  const { sessions, session, choisir } = useStudio();
  return (
    <Menu.Root>
      <Menu.Trigger className="mx-3 flex min-h-12 items-center py-2 gap-3 rounded-[12px] border border-ligne bg-carte px-3 text-left outline-none transition-colors hover:border-ligne-forte data-[state=open]:border-ligne-forte">
        <div className="grid size-7 place-items-center rounded-lg bg-ambre-sombre text-[13px] font-semibold text-ambre-vif">{session?.nom.slice(0, 1) ?? "·"}</div>
        <div className="min-w-0 flex-1">
          <div className="text-[11px] text-pale">Série</div>
          <div className="line-clamp-2 text-[13px] leading-tight font-medium">{session?.nom ?? "…"}</div>
        </div>
        <ChevronsUpDown className="size-4 text-pale" />
      </Menu.Trigger>
      <Menu.Portal>
        <Menu.Content
          sideOffset={6}
          align="start"
          className="animate-entree z-50 w-[222px] rounded-[12px] border border-ligne-forte bg-carte-2 p-1.5 shadow-haut"
        >
          {sessions.map((s) => (
            <Menu.Item
              key={s.id}
              onSelect={() => {
                choisir(s.id);
                aller("episodes");
              }}
              className="flex h-9 cursor-default items-center gap-2.5 rounded-lg px-2.5 text-[13px] outline-none data-[highlighted]:bg-survol"
            >
              <span className="flex-1 truncate">{s.essais ? "Essais" : s.nom}</span>
              {s.id === session?.id && <Check className="size-4 text-ambre" />}
            </Menu.Item>
          ))}
        </Menu.Content>
      </Menu.Portal>
    </Menu.Root>
  );
}
