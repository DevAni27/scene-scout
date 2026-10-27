import base64,shutil,subprocess
def narrate(message):
    # Local voice output only; no provider keys, subscription or network TTS call.
    if shutil.which('powershell.exe'):
        encoded=base64.b64encode(message.encode('utf-8')).decode('ascii')
        ps="Add-Type -AssemblyName System.Speech; $s=New-Object System.Speech.Synthesis.SpeechSynthesizer; $t=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('"+encoded+"')); $s.Speak($t)"
        cmd=['powershell.exe','-NoProfile','-NonInteractive','-EncodedCommand',base64.b64encode(ps.encode('utf-16le')).decode('ascii')]
    elif shutil.which('espeak-ng'): cmd=['espeak-ng','-s','155',message]
    elif shutil.which('say'): cmd=['say',message]
    else:
        print('Voice unavailable: on WSL enable Windows interoperability, or install espeak-ng on Linux. Text/rig still work.'); return False
    try:
        p=subprocess.run(cmd,capture_output=True,timeout=100)
        if p.returncode: print('Local voice failed; the deployed scouting scene remains available.'); return False
        return True
    except (OSError,subprocess.TimeoutExpired):
        print('Local voice did not finish; continue using text.'); return False
