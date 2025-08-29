import time
import pyautogui
import subprocess

interval = 50

windowsRun = False

def update_position():
    while True:
        x, y = pyautogui.position()
        print(f"Position actuelle : X={x}, Y={y}")

def run_change_vpn():
    result = subprocess.run(['sudo', './connectVPN.sh'], capture_output=True, text=True)
    print("stdout:", result.stdout)
    print("stderr:", result.stderr)
    time.sleep(15)

def changeVPN():
    if windowsRun:
        #Windows versions
        pyautogui.moveTo(1181, 1057, duration=0.1)
        pyautogui.click()
        pyautogui.moveTo(1156, 374, duration=0.5)
        pyautogui.click()
        pyautogui.moveTo(1022, 384, duration=0.5)
        pyautogui.click()
        """
        time.sleep(17)
        pyautogui.moveTo(66, 574, duration=0.1)
        pyautogui.click()
        pyautogui.moveTo(1100, 390, duration=2)
        pyautogui.click()
        pyautogui.moveTo(1100, 390, duration=1)
        pyautogui.click()
        """
    else:
        run_change_vpn()



def main():
    next_change = time.time() + interval
    try:
        while True:
            update_position()

            if time.time() >= next_change:
                changeVPN()
                next_change = time.time() + interval

            time.sleep(0.1)

    except KeyboardInterrupt:
        print("\nProgramme arrêté.")
