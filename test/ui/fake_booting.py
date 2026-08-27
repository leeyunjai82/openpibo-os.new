"""booting.py(:8080) 흉내. 와이파이 중계 시험용."""
from fastapi import FastAPI, Body
from fastapi.responses import JSONResponse
app = FastAPI()

@app.get('/wifi_scan')
async def scan():
    return JSONResponse([{'ssid':'pibo-classroom','signal':'82'},
                         {'ssid':'school-wifi','signal':'55'}])

@app.get('/wifi')
async def wifi():
    return JSONResponse({'result':'ok','ssid':'pibo-classroom','psk':'secret123',
                         'ipaddress':'192.168.0.42','eth1':'','identity':'','key-mgmt':'wpa-psk'})

@app.post('/wifi')
async def wifi_set(data: dict = Body(...)):
    return JSONResponse('ok')

if __name__ == '__main__':
    import uvicorn; uvicorn.run(app, host='127.0.0.1', port=8080, log_level='error')
