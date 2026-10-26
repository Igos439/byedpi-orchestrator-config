import json, time
p="/app/state/yt_hosts_cache.json"
d=json.load(open(p))
now=time.time()
for k,v in d.items():
    media=v.get("media") or []
    exp=[]
    for x in media:
        if "expire=" in x:
            try: exp.append(int(x.split("expire=")[1].split("&")[0]))
            except Exception: pass
    print(k[-11:], "age_min=%d" % ((now-float(v.get("ts",0)))/60), "hosts=%d" % len(v.get("hosts") or []), "ttl_min=%s" % [round((e-now)/60) for e in exp])
print("entries", len(d))
