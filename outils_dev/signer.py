"""Signe un programme (repris de Bramble Studio, même certificat : aucun nouveau certificat chez RT) avec le certificat de signature de code maison de ce PC : python outils_dev\\signer.py <fichier> [<fichier>…]
Le certificat (« StudioKids (Bramble Studio) », auto-signé, clé non exportable) vit dans le magasin PERSONNEL de l'utilisateur ; il est créé au
premier besoin. Ce n'est pas un réglage de sécurité : Windows ne lui fait confiance que si RT le demande dans l'app (Système → À propos).
Horodatage si le réseau le permet. Appelé par construire.py (lanceur) et par Inno Setup (installateur, désinstallateur).
Outil de développement (Windows) : jamais livré."""
import os
import subprocess
import sys

SUJET = "CN=StudioKids (Bramble Studio)"
SCRIPT = r"""
$ErrorActionPreference = 'Stop'
$c = Get-ChildItem Cert:\CurrentUser\My -CodeSigningCert | Where-Object { $_.Subject -eq $env:SIGNER_SUJET -and $_.HasPrivateKey -and $_.NotAfter -gt (Get-Date).AddDays(30) } | Sort-Object NotAfter -Descending | Select-Object -First 1
if (-not $c) { $c = New-SelfSignedCertificate -Type CodeSigningCert -Subject $env:SIGNER_SUJET -KeyExportPolicy NonExportable -KeyUsage DigitalSignature -HashAlgorithm SHA256 -NotAfter (Get-Date).AddYears(10) -CertStoreLocation Cert:\CurrentUser\My }
$s = $null
try { $s = Set-AuthenticodeSignature -LiteralPath $env:SIGNER_FICHIER -Certificate $c -HashAlgorithm SHA256 -TimestampServer 'http://timestamp.digicert.com' } catch { }
if (-not $s -or -not $s.SignerCertificate -or -not $s.TimeStamperCertificate) { $s = Set-AuthenticodeSignature -LiteralPath $env:SIGNER_FICHIER -Certificate $c -HashAlgorithm SHA256 }
$v = Get-AuthenticodeSignature -LiteralPath $env:SIGNER_FICHIER
if (-not $v.SignerCertificate -or $v.SignerCertificate.Thumbprint -ne $c.Thumbprint -or $v.Status -notin 'Valid','UnknownError') { throw "signature non posée : $($v.Status) $($v.StatusMessage)" }
"$($c.Thumbprint) $(if ($v.TimeStamperCertificate) { 'horodatée' } else { 'sans horodatage' })"
"""


def signer(fichier) -> str:
    """Signe le fichier ; rend « <empreinte du certificat> horodatée | sans horodatage ». Lève RuntimeError si la signature n'a pas pu être posée."""
    r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", SCRIPT], capture_output=True, text=True,
                       env={**os.environ, "SIGNER_SUJET": SUJET, "SIGNER_FICHIER": str(fichier)}, creationflags=subprocess.CREATE_NO_WINDOW)
    if r.returncode or not r.stdout.strip():
        raise RuntimeError(f"signature de {fichier} : {r.stderr.strip()[-600:] or r.stdout.strip()}")
    return r.stdout.strip().splitlines()[-1]


if __name__ == "__main__":
    for f in sys.argv[1:]:
        print(f"[signer] {f} : {signer(f)}", flush=True)
