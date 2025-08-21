import subprocess
import tempfile
import os
import signal

from dotenv import load_dotenv

load_dotenv()
username = os.environ.get('PROTON_USERNAME')
password = os.environ.get('PROTON_PASS')

# Chemin vers openvpn.exe et le fichier .ovpn
openvpn_path = r"C:\Program Files\OpenVPN\bin\openvpn.exe"
config_path = r"C:\Users\mouri\OpenVPN\config\FOV_Italy_freeopenvpn_udp.ovpn"

# Crée un fichier temporaire pour auth
with tempfile.NamedTemporaryFile(mode='w', delete=False) as auth_file:
    auth_file.write(f"{username}\n{password}\n")
    auth_file_path = auth_file.name

# Lancer OpenVPN avec le fichier auth
process = subprocess.Popen(
    [openvpn_path, "--config", config_path, "--auth-user-pass", auth_file_path],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    universal_newlines=True
)

try:
    for line in process.stdout:
        print(line, end="")
        if "Initialization Sequence Completed" in line:
            print("✅ VPN connecté !")
except KeyboardInterrupt:
    print("🛑 Arrêt du VPN...")
    process.send_signal(signal.CTRL_C_EVENT)  # Pour Windows
finally:
    process.terminate()
    os.remove(auth_file_path)  # Supprime le fichier temporaire
    print("Fichier d'authentification supprimé.")
