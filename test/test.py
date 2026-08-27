import os
import sys
import time
import json
import asyncio
from threading import Thread

# --- FastAPI and Web Server Imports ---
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse # Replaced EventSourceResponse
from fastapi.middleware.cors import CORSMiddleware

# --- OpenPibo Hardware Imports ---
from openpibo.board import BOARD
from openpibo.oled import get_display
from openpibo.audio import Audio
from openpibo.motion import Motion
from openpibo.device import get_device
from openpibo.vision_camera import Camera

# ==============================================================================
# 1. INITIALIZE FASTAPI APP AND HARDWARE
# ==============================================================================

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Initialize Hardware Objects (globally, once) ---
try:
    oled_obj = get_display()      # 보드에 맞는 디스플레이
    audio_obj = Audio()
    motion_obj = Motion()
    device_obj = get_device()     # 보드에 맞는 device
    camera_obj = Camera()
    os.system('sudo /home/pi/.pyenv/bin/python3 /home/pi/openpibo-os/system/network_disp.py')
except Exception as e:
    print(f"Error initializing hardware: {e}")
    oled_obj = audio_obj = motion_obj = device_obj = camera_obj = None

# ==============================================================================
# 2. HARDWARE CONTROL AND SYSTEM INFO FUNCTIONS
# ==============================================================================

# --- System Information Functions ---
def get_serial():
    try:
        with open('/proc/cpuinfo', 'r') as f:
            for line in f:
                if line.startswith('Serial'):
                    return line.split(':')[1].strip()
    except Exception:
        return "N/A"

def get_fw():
    try:
        data = device_obj.send_raw("#10:!")
        return data.split(":")[1]
    except Exception:
        return "N/A"

def get_os():
    try:
        return os.popen('cat /home/pi/.OS_VERSION').read().strip()
    except Exception:
        return "N/A"

def get_memory():
    try:
        data = os.popen("vcgencmd get_config total_mem").read().strip()
        mem_gb = int(data.split("=")[1]) / 1024
        return f"{mem_gb:.1f} GB"
    except Exception:
        return "N/A"

def get_board():
    try:
        return os.popen('cat /proc/device-tree/model').read().strip()
    except Exception:
        return "N/A"

# --- Hardware Test Functions ---
def oled_test():
    oled_obj.set_font(size=30)
    oled_obj.clear()
    oled_obj.draw_text((0, 0), "Oled")
    oled_obj.draw_text((0, 30), "Testing...")
    oled_obj.show()
    time.sleep(2)
    oled_obj.clear()
    oled_obj.show()
    os.system('sudo /home/pi/.pyenv/bin/python3 /home/pi/openpibo-os/system/network_disp.py')
    return {"status": "OLED test executed"}

def audio_test():
    audio_file = "/home/pi/openpibo-files/audio/effect/opening.mp3"
    if os.path.exists(audio_file):
        audio_obj.play(filename=audio_file, volume=80)
        time.sleep(5)
        audio_obj.stop()
        return {"status": "Audio test executed"}
    else:
        raise HTTPException(status_code=404, detail=f"Audio file not found: {audio_file}")

def motor_test():
    motor_list = ['foot_right', 'leg_right', 'shoulder_right', 'hand_right', 'head_pan', 'head_tilt', 'foot_left', 'leg_left', 'shoulder_left', 'hand_left']
    motion_obj.set_motors([0]*10)
    time.sleep(1)
    for i in range(10):
        motion_obj.set_speed(i, 30)
        motion_obj.set_acceleration(i, 0)
        motion_obj.set_motor(i, 10)
        time.sleep(0.3)
        motion_obj.set_motor(i, -10)
        time.sleep(0.3)
        motion_obj.set_motor(i, 0)
        time.sleep(0.5)
    return {"status": "Motor test executed"}

def mic_test():
    try:
        audio_obj.record(filename="stream.wav", timeout=5)
        audio_obj.play(filename="stream.wav", volume=100, background=False)
        return {"status": "Mic test executed"}
    finally:
        if os.path.exists("stream.wav"):
            os.remove("stream.wav")

def camera_test():
    img_path = "/tmp/pibo_capture.jpg"
    try:
        frame = camera_obj.read()
        camera_obj.imwrite(img_path, frame)
        return FileResponse(img_path, media_type="image/jpeg")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Camera capture failed: {e}")

def neopixel_test():
    device_obj.send_raw("#20:255,0,0!")
    time.sleep(0.3)
    device_obj.send_raw("#20:0,255,0!")
    time.sleep(0.3)
    device_obj.send_raw("#20:0,0,255!")
    time.sleep(0.3)
    device_obj.send_raw("#20:0,0,0!")
    return {"status": "Neopixel test executed"}

def battery_test():
    data = device_obj.send_cmd(Device.code_list['BATTERY']).split(":")[1]
    return {"battery_status": data}

async def system_stream_generator():
    """
    A generator that yields system status data in the SSE format.
    Format: "data: <json_string>\n\n"
    """
    device_obj.send_cmd(Device.code_list['PIR'], "on")
    for i in range(20):
        data = device_obj.send_cmd(Device.code_list['SYSTEM']).split(':')[1].split('-')

        # Safely get data from the split list
        pir = data[0] if len(data) > 0 and data[0] else "nobody"
        touch = data[1] if len(data) > 1 and data[1] else "No signal"
        dc = data[2] if len(data) > 2 and data[2] else "No signal"
        button = data[3] if len(data) > 3 and data[3] else "No signal"

        response_data = {
            "pir": pir,
            "touch": touch,
            "dc": dc,
            "button": button,
            "count": i + 1
        }
        # Manually format the data for SSE
        yield f"data: {json.dumps(response_data)}\n\n"
        await asyncio.sleep(1)
    device_obj.send_cmd(Device.code_list['PIR'], "off")


# ==============================================================================
# 3. API ENDPOINTS
# ==============================================================================

# Map test names to functions
TEST_FUNCTIONS = {
    "oled": oled_test,
    "audio": audio_test,
    "motor": motor_test,
    "mic": mic_test,
    "neopixel": neopixel_test,
    "battery": battery_test,
}

@app.get("/api/system-info")
async def get_system_info():
    """Returns a JSON object with all system hardware/software details."""
    return {
        "serial": get_serial(),
        "firmware": get_fw(),
        "os_version": get_os(),
        "board": get_board(),
        "memory": get_memory(),
    }

@app.post("/api/test/{test_name}")
async def run_test(test_name: str):
    """Runs a standard hardware test."""
    if test_name not in TEST_FUNCTIONS:
        raise HTTPException(status_code=404, detail="Test not found")

    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, TEST_FUNCTIONS[test_name])
        return JSONResponse(content=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/test/camera")
async def run_camera_test():
    """Handles the camera test specifically to return an image file."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, camera_test)

@app.get("/api/test/system")
async def run_system_test_stream():
    """Streams system sensor data using FastAPI's native StreamingResponse."""
    return StreamingResponse(system_stream_generator(), media_type="text/event-stream")

@app.post("/api/halt")
async def halt_system():
    """Shuts down the Raspberry Pi."""
    oled_obj.draw_text((10, 25), "Shutting down...")
    oled_obj.show()
    if BOARD.features.has_mcu:      # MCU 가 없는 보드에는 /dev/ttyS0 이 없다
        os.system('echo "#11:!" > /dev/ttyS0')
    os.system('sudo shutdown -h now &')
    return {"message": "System is shutting down."}

# ==============================================================================
# 4. RUN THE SERVER
# ==============================================================================

if __name__ == "__main__":
    if any(obj is None for obj in [oled_obj, audio_obj, motion_obj, device_obj, camera_obj]):
         print("\nWARNING: One or more hardware components failed to initialize.")
         print("The API will run, but hardware-related endpoints may fail.")

    print("\nStarting OpenPibo Web Test Interface.")
    print("Access the frontend at http://<your-robot-ip>:8000/ in your browser.")

    @app.get("/")
    async def read_root():
        return FileResponse('index.html')

    uvicorn.run(app, host="0.0.0.0", port=8000)
