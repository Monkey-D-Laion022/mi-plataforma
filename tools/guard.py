    items = live.get("items", [])
    from_iptv_org = str(live.get("origin", "")).startswith("iptv-org")
    ar_items = [c for c in items if c.get("country") == "AR"]
    if not items:
        failures.append("live.json no tiene canales: la API de iptv-org no respondió o cambió de formato.")
    elif from_iptv_org and not ar_items:
        failures.append("live.json no tiene canales de Argentina (¿cambió el formato de la API?).")

    for name, cat in (("live", live), ("movies", movies), ("series", series)):
        s = report["catalogs"][name]
        real = [st for st in s["by_status"] if st not in (STATUS_FIXTURE, STATUS_EXTERNAL)]
        checked = sum(s["by_status"][st] for st in real if st != "unchecked")
        # Solo LIVE puede frenar la publicación; en el resto, estos problemas son advertencias.
        problems = failures if name == "live" else warnings
        if strict and (str(cat.get("origin", "")).startswith("DATOS DE PRUEBA") or s["by_status"].get(STATUS_FIXTURE)):
            failures.append(f"{name}: contiene datos de prueba en una corrida real.")
        if checked >= 10 and s["network_errors"] / max(checked, 1) > 0.9:
            problems.append(f"{name}: {s['network_errors']} de {checked} fuentes sin respuesta de red.")
        if name == "live" and checked >= 20 and s["by_status"].get(STATUS_OK, 0) == 0:
            failures.append("live: ninguna de las fuentes verificadas dio 'ok'. Revisá el verificador.")
            
