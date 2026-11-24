import * as Dialogue from "@radix-ui/react-dialog";
import { ArchiveRestore, CircleCheck, Cpu, Download, HardDrive, KeyRound, ShieldCheck, Smartphone, Sparkles } from "lucide-react";
import { useState, type ReactNode } from "react";
import { agir, useLire, type Cle, type Etat, type Sauvegardes, type Versions } from "../api";
import { carteOccupee } from "../outils";
import { useStudio } from "../studio";
import { Bouton, Carte, cx, EnTete, Pastille, Squelette } from "../ui";

function Section({ icone, titre, children, action }: { icone: ReactNode; titre: string; children: ReactNode; action?: ReactNode }) {
  return (
    <Carte className="p-7">
      <div className="mb-5 flex items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="grid size-9 place-items-center rounded-[10px] bg-carte-2 text-doux ring-1 ring-ligne">{icone}</div>
          <h2 className="text-[17px] font-semibold">{titre}</h2>
        </div>
        {action}
      </div>
      {children}
    </Carte>
  );
}

function useAction(apres?: () => void) {
  const [charge, setCharge] = useState(false);
  const [message, setMessage] = useState<{ texte: string; erreur?: boolean } | null>(null);
  const lancer = async (chemin: string) => {
    setCharge(true);
    setMessage(null);
    try {
      const r = await agir(chemin);
      setMessage({ texte: r.message });
      apres?.();
    } catch (e) {
      setMessage({ texte: e instanceof Error ? e.message : String(e), erreur: true });
    } finally {
      setCharge(false);
    }
  };
  return { charge, message, lancer };
}

function Message({ m }: { m: { texte: string; erreur?: boolean } | null }) {
  if (!m) return null;
  return <div className={cx("mt-4 rounded-[10px] px-4 py-3 text-[13px]", m.erreur ? "bg-rouge-sombre text-rouge" : "bg-vert-sombre text-vert")}>{m.texte}</div>;
}

export function Systeme() {
  const { machine } = useStudio();
  const { donnees: versions, relire: relireVersions } = useLire<Versions>("/versions", 60000);
  const { donnees: sauvegardes, relire: relireSauvegardes } = useLire<Sauvegardes>("/sauvegardes", 10000);
  const { donnees: cles } = useLire<Cle[]>("/cles");
  const { donnees: etat } = useLire<Etat>("/etat");
  const maj = useAction(relireVersions);
  const sauver = useAction(relireSauvegardes);
  const tel = useTelephone();
  const carte = /(\d+)\s*%\s*·\s*([\d,]+)\s*\/\s*([\d,]+)/.exec(machine?.carte ?? "");

  return (
    <>
      <EnTete titre="Système" sous="Fabrique et ce PC." >
        {etat?.mode === "simulation" && <Pastille ton="bleu">Mode essai : rien n'est fabriqué pour de vrai</Pastille>}
      </EnTete>
      <div className="grid gap-6 xl:grid-cols-2">
        <Section icone={<Sparkles className="size-[18px]" />} titre="Mises à jour">
          {!versions ? (
            <Squelette className="h-20" />
          ) : (
            <>
              <div className="flex items-center justify-between gap-6">
                <div>
                  <div className="text-[14px] text-doux">Version installée</div>
                  <div className="mt-0.5 text-[24px] font-semibold tabular-nums">{versions.installee}</div>
                </div>
                {versions.proposee && !versions.raison ? (
                  <Bouton genre="principal" icone={<Download className="size-4" />} charge={maj.charge} onClick={() => maj.lancer("/versions/mettre-a-jour")}>
                    Installer la {versions.proposee}
                  </Bouton>
                ) : versions.proposee ? (
                  <Pastille ton="ambre">Version {versions.proposee} prête</Pastille>
                ) : (
                  <Pastille ton="vert">
                    <CircleCheck className="size-3.5" /> À jour
                  </Pastille>
                )}
              </div>
              {versions.proposee && versions.raison && (
                <div className="mt-4 rounded-[10px] bg-ambre-sombre/60 px-4 py-3 text-[13px] text-ambre-vif">
                  Elle s'installera plus tard : {versions.raison}.
                </div>
              )}
              {versions.proposee && versions.nouveautes.length > 0 && (
                <ul className="mt-5 flex list-disc flex-col gap-1.5 pl-5 text-[14px] leading-relaxed text-doux">
                  {versions.nouveautes.map((n) => (
                    <li key={n}>{n}</li>
                  ))}
                </ul>
              )}
              <Message m={maj.message} />
            </>
          )}
        </Section>

        <Section
          icone={<ShieldCheck className="size-[18px]" />}
          titre="Sauvegardes"
          action={
            <Bouton charge={sauver.charge} onClick={() => sauver.lancer("/sauvegardes")}>
              Sauvegarder maintenant
            </Bouton>
          }
        >
          {!sauvegardes ? (
            <Squelette className="h-20" />
          ) : sauvegardes.liste.length ? (
            <div className="flex flex-col">
              {sauvegardes.liste.slice(0, 5).map((s, i) => (
                <div key={s.nom} className="flex items-center gap-4 border-b border-ligne py-3 last:border-0">
                  <div className="flex-1 text-[14px]">{s.date}</div>
                  <span className="text-[13px] text-pale tabular-nums">{s.taille_mo.toLocaleString("fr-FR", { maximumFractionDigits: 1 })} Mo</span>
                  {i === 0 && <Pastille ton="vert">La plus récente</Pastille>}
                  <Restaurer nom={s.nom} date={s.date} />
                </div>
              ))}
            </div>
          ) : (
            <div className="text-[14px] text-doux">Aucune sauvegarde pour l'instant. Fabrique en fait une chaque jour ; vous pouvez aussi en faire une maintenant.</div>
          )}
          <Message m={sauver.message} />
        </Section>

        <Section icone={<Cpu className="size-[18px]" />} titre="Ce PC">
          {!machine ? (
            <Squelette className="h-20" />
          ) : (
            <div className="grid grid-cols-2 gap-4">
              <div className="rounded-[12px] bg-carte-2 p-4 ring-1 ring-ligne">
                <div className="flex items-center gap-2 text-[13px] text-doux">
                  <Cpu className="size-4" /> Carte graphique
                </div>
                <div className="mt-2 text-[20px] font-semibold">{carte ? `${carte[1]} %` : "—"}</div>
                <div className="mt-0.5 text-[12px] text-pale">{carte ? `${carte[2]} Go utilisés sur ${carte[3]}` : "indisponible"}</div>
                {machine.carte_prise && <div className="mt-2 text-[12px] leading-snug text-ambre-vif">{carteOccupee(machine.carte_prise)}</div>}
              </div>
              <div className="rounded-[12px] bg-carte-2 p-4 ring-1 ring-ligne">
                <div className="flex items-center gap-2 text-[13px] text-doux">
                  <HardDrive className="size-4" /> Disque
                </div>
                <div className="mt-2 text-[20px] font-semibold">{machine.disque_go} Go</div>
                <div className="mt-0.5 text-[12px] text-pale">libres</div>
              </div>
            </div>
          )}
        </Section>

        <Section
          icone={<Smartphone className="size-[18px]" />}
          titre="iPhone"
          action={
            <Bouton charge={tel.charge} onClick={tel.demander}>
              Relier un iPhone
            </Bouton>
          }
        >
          {tel.code ? (
            <div className="flex items-center gap-6">
              <div className="copiable rounded-[12px] bg-carte-2 px-5 py-3 font-mono text-[30px] font-semibold tracking-[0.3em] ring-1 ring-ligne">{tel.code.code}</div>
              <div className="text-[13px] leading-relaxed text-doux">
                Sur l'iPhone, ouvrez Fabrique et tapez ce code.
                <br />
                Il expire à {tel.code.expire}.
              </div>
            </div>
          ) : (
            <div className="text-[14px] text-doux">Suivez la fabrication et regardez les vidéos depuis votre iPhone, sur le même réseau que ce PC.</div>
          )}
          {tel.erreur && <Message m={{ texte: tel.erreur, erreur: true }} />}
        </Section>

        <Section icone={<KeyRound className="size-[18px]" />} titre="Services en ligne">
          {!cles ? (
            <Squelette className="h-20" />
          ) : (
            <div className="flex flex-col">
              {cles.map((c) => (
                <div key={c.nom} className="flex items-center justify-between border-b border-ligne py-3 last:border-0">
                  <span className="text-[14px]">{c.titre}</span>
                  {c.ok ? <Pastille ton="vert">Relié</Pastille> : <Pastille>Pas relié</Pastille>}
                </div>
              ))}
            </div>
          )}
        </Section>
      </div>
    </>
  );
}

function useTelephone() {
  const [charge, setCharge] = useState(false);
  const [code, setCode] = useState<{ code: string; expire: string } | null>(null);
  const [erreur, setErreur] = useState("");
  return {
    charge,
    code,
    erreur,
    demander: async () => {
      setCharge(true);
      setErreur("");
      try {
        setCode(await agir<{ code: string; expire: string }>("/telephone/code"));
      } catch (e) {
        setErreur(e instanceof Error ? e.message : String(e));
      } finally {
        setCharge(false);
      }
    },
  };
}

function Restaurer({ nom, date }: { nom: string; date: string }) {
  const [ouvert, setOuvert] = useState(false);
  const action = useAction();
  return (
    <Dialogue.Root open={ouvert} onOpenChange={setOuvert}>
      <Dialogue.Trigger asChild>
        <Bouton genre="discret" className="h-8 px-2.5" icone={<ArchiveRestore className="size-4" />} title="Revenir à cette sauvegarde" />
      </Dialogue.Trigger>
      <Dialogue.Portal>
        <Dialogue.Overlay className="animate-entree fixed inset-0 z-40 bg-black/70" />
        <Dialogue.Content className="animate-entree fixed top-1/2 left-1/2 z-50 w-[460px] -translate-x-1/2 -translate-y-1/2 rounded-[16px] border border-ligne-forte bg-carte p-7 shadow-haut outline-none">
          <Dialogue.Title className="text-[18px] font-semibold">Revenir à la sauvegarde du {date} ?</Dialogue.Title>
          <Dialogue.Description className="mt-2 text-[14px] leading-relaxed text-doux">
            Les séries reviennent à leur état de ce jour-là. L'état actuel est d'abord mis de côté : rien n'est perdu.
          </Dialogue.Description>
          <Message m={action.message} />
          <div className="mt-6 flex justify-end gap-2">
            <Dialogue.Close asChild>
              <Bouton genre="discret">Fermer</Bouton>
            </Dialogue.Close>
            {!action.message && (
              <Bouton genre="principal" charge={action.charge} onClick={() => action.lancer(`/sauvegardes/${encodeURIComponent(nom)}/restaurer`)}>
                Revenir à cette sauvegarde
              </Bouton>
            )}
          </div>
        </Dialogue.Content>
      </Dialogue.Portal>
    </Dialogue.Root>
  );
}
