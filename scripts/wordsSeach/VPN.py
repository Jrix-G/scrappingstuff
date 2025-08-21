import time
import pyautogui

interval = 50

def update_position():
    while True:
        x, y = pyautogui.position()
        print(f"Position actuelle : X={x}, Y={y}")

def changeVPN():
    pyautogui.moveTo(1181, 1057, duration=0.1)
    pyautogui.click()
    pyautogui.moveTo(1156, 374, duration=0.5)
    pyautogui.click()
    pyautogui.moveTo(1022, 384, duration=0.5)
    pyautogui.click()
    time.sleep(17)

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
