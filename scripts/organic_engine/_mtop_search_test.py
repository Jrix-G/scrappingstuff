"""Test décisif : sur IP propre (hors cooldown x5sec), l'endpoint mtop de
recherche avec ventes est-il bloqué ou non ? Et quel volume tient-il ?"""
from curl_cffi import requests as creq
import hashlib, time, json, urllib.parse
APPKEY="12574478"
s=creq.Session(impersonate="chrome131")
H={"accept-language":"en-US,en;q=0.9"}
s.get("https://www.aliexpress.com/",headers=H,timeout=20)
def tok():
    for c in s.cookies.jar:
        if c.name=="_m_h5_tk": return c.value.split("_")[0]
    return ""
def mtop(api,data_obj):
    data=json.dumps(data_obj,separators=(",",":"))
    for a in range(3):
        token=tok();t=str(int(time.time()*1000))
        sign=hashlib.md5(f"{token}&{t}&{APPKEY}&{data}".encode()).hexdigest()
        params={"jsv":"2.5.1","appKey":APPKEY,"t":t,"sign":sign,"api":api,"v":"1.0","type":"originaljson","dataType":"json"}
        r=s.post(f"https://acs.aliexpress.com/h5/{api}/1.0/?"+urllib.parse.urlencode(params),
                 headers={**H,"content-type":"application/x-www-form-urlencoded","referer":"https://www.aliexpress.com/"},
                 data={"data":data},timeout=20)
        body=r.text
        try: ret=",".join(json.loads(body).get("ret",[]))
        except: ret=body[:50].replace("\n"," ")
        if "TOKEN_EMPTY" in ret or "TOKEN_EXPIRED" in ret: continue
        return ret,body
    return "exhausted",""

api="mtop.relationrecommend.wirelessrecommend.recommend"
print("Test wirelessrecommend (recherche) sur IP fraîche, 8 appels rapides:")
for i in range(8):
    ret,body=mtop(api,{"appId":"34385","params":json.dumps({"keyword":"ceiling fan","page":str(i+1)})})
    punish="punish" in body
    sold=("tradeDesc" in body) or ('"sold"' in body)
    print(f"[{i+1}] ret={ret[:40]:40} punish={punish} sold={sold} len={len(body)}")
    if i==0 and (sold or "SUCCESS" in ret):
        print("   ÉCHANTILLON:", body[:400])
    time.sleep(2)
