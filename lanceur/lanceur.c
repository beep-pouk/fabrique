/* Lanceur natif de Fabrique (« Fabrique.exe »), repris de Bramble Studio.
   Charge runtime\python312.dll dans CE processus et joue « -B -m fabrique <arguments> » : chaque processus de Fabrique porte le nom de l'exe.
   Sous-système fenêtre (jamais de console), sans bibliothèque C : kernel32, user32, shell32 seulement.
   Les chemins de Python viennent de runtime\python312._pth (à côté de la DLL), jamais de PYTHONHOME ni de PYTHONPATH :
   les outils lancés par l'app (ComfyUI, environnements, WSL) en hériteraient. */
#include <windows.h>
#include <shellapi.h>

#define MAXC 32768 /* longueur maximale d'un chemin long de Windows */
#define DLL L"\\runtime\\python312.dll"

typedef int (*py_main)(int, wchar_t **);
static wchar_t exe[MAXC], dll[MAXC]; /* statiques : pas de grande pile sans la bibliothèque C (__chkstk) */

static void echec(const wchar_t *texte)
{
    MessageBoxW(NULL, texte, L"Fabrique", MB_OK | MB_ICONERROR);
    ExitProcess(1);
}

void entree(void)
{
    int argc = 0, i;
    wchar_t **argv = CommandLineToArgvW(GetCommandLineW(), &argc), **args, *p, *fin = NULL;
    DWORD n = GetModuleFileNameW(NULL, exe, MAXC);
    HMODULE python;
    py_main Py_Main;

    if (!argv || !n || n + lstrlenW(DLL) >= MAXC)
        echec(L"Fabrique n'a pas pu lire son propre emplacement.");
    lstrcpyW(dll, exe);
    for (p = dll; *p; p++)
        if (*p == L'\\')
            fin = p;
    if (!fin)
        echec(L"Fabrique n'a pas pu lire son propre emplacement.");
    lstrcpyW(fin, DLL);
    python = LoadLibraryExW(dll, NULL, LOAD_WITH_ALTERED_SEARCH_PATH); /* ses DLL voisines (vcruntime140) viennent du même dossier */
    Py_Main = python ? (py_main)GetProcAddress(python, "Py_Main") : NULL;
    if (!Py_Main)
        echec(L"Fabrique est incomplet : le dossier « runtime » est absent ou abîmé.\n\nRéinstallez Fabrique.");
    args = HeapAlloc(GetProcessHeap(), 0, (argc + 4) * sizeof *args);
    if (!args)
        echec(L"Mémoire insuffisante pour démarrer Fabrique.");
    args[0] = exe;
    args[1] = L"-B"; /* le dossier du programme n'est jamais écrit : le code y est précompilé */
    args[2] = L"-m";
    args[3] = L"fabrique";
    for (i = 1; i < argc; i++)
        args[i + 3] = argv[i];
    args[argc + 3] = NULL;
    ExitProcess((UINT)Py_Main(argc + 3, args));
}
