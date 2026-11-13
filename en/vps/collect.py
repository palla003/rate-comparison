"""VPSの公開料金APIから月額を集めて data/en_vps.json に保存する。
Vultr・Linodeは認証不要。DigitalOcean(DO_TOKEN)・Hetzner(HCLOUD_TOKEN)は読み取りトークンがあれば追加。"""
import datetime as dt
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from common import get_json, save, update_history  # noqa: E402

SITES = {
    "Vultr": "https://www.vultr.com/products/cloud-compute/",
    "Linode": "https://www.linode.com/pricing/",
    "DigitalOcean": "https://www.digitalocean.com/pricing/droplets",
    "Hetzner": "https://www.hetzner.com/cloud/",
}
VULTR_KIND = {"vc2": ("Regular", "shared"), "vhf": ("High Frequency", "shared"), "vhp": ("High Performance", "shared"),
              "voc": ("Optimized", "dedicated"), "vdc": ("Dedicated", "dedicated")}


def vultr():
    out = []
    for p in get_json("https://api.vultr.com/v2/plans?per_page=500", check_robots=False)["plans"]:
        kind = VULTR_KIND.get(p["type"]) or (VULTR_KIND["voc"] if p["type"].startswith("voc") else None)
        if not kind or not p.get("locations"):
            continue
        out.append(dict(provider="Vultr", plan=p["id"], family=kind[0], cpu=kind[1], vcpu=p["vcpu_count"],
                        ram_gb=p["ram"] / 1024, disk_gb=p["disk"] * max(1, p.get("disk_count", 1)),
                        transfer_tb=p["bandwidth"] / 1000, monthly=float(p["monthly_cost"]), regions=len(p["locations"])))
    return out


def linode():
    out = []
    for p in get_json("https://api.linode.com/v4/linode/types?page_size=500", check_robots=False)["data"]:
        if p.get("gpus") or p["class"] in ("gpu", "accelerated") or not p.get("price", {}).get("monthly"):
            continue
        out.append(dict(provider="Linode", plan=p["id"], family=("Shared " + p["label"][7:]) if p["label"].startswith("Linode ") else p["label"],
                        cpu="dedicated" if p["class"] in ("dedicated", "premium", "highmem") else "shared",
                        vcpu=p["vcpus"], ram_gb=p["memory"] / 1024, disk_gb=p["disk"] / 1024,
                        transfer_tb=p["transfer"] / 1000, monthly=float(p["price"]["monthly"]), regions=None))
    return out


def digitalocean():
    tok = os.environ.get("DO_TOKEN")
    if not tok:
        return None
    out = []
    for p in get_json("https://api.digitalocean.com/v2/sizes?per_page=200", check_robots=False,
                      headers={"Authorization": f"Bearer {tok}"})["sizes"]:
        if not p.get("available") or p["slug"].startswith("gpu"):
            continue
        out.append(dict(provider="DigitalOcean", plan=p["slug"], family=p.get("description") or "Droplet",
                        cpu="dedicated" if p["slug"].split("-")[0] in ("c", "c2", "g", "gd", "m", "m3", "so", "so1_5", "m6", "g6", "c6") else "shared",
                        vcpu=p["vcpus"], ram_gb=p["memory"] / 1024, disk_gb=p["disk"], transfer_tb=p["transfer"],
                        monthly=float(p["price_monthly"]), regions=len(p.get("regions", []))))
    return out


def hetzner():
    tok = os.environ.get("HCLOUD_TOKEN")
    if not tok:
        return None
    usd = get_json("https://api.frankfurter.app/latest?from=EUR&to=USD", check_robots=False)["rates"]["USD"]
    out = []
    for p in get_json("https://api.hetzner.cloud/v1/server_types?per_page=50", check_robots=False,
                      headers={"Authorization": f"Bearer {tok}"})["server_types"]:
        if p.get("deprecated") or p.get("deprecation") or not p.get("prices"):
            continue
        eur = min(float(x["price_monthly"]["net"]) for x in p["prices"])
        tb = min((x.get("included_traffic") or 0) for x in p["prices"]) / 1e12
        out.append(dict(provider="Hetzner", plan=p["name"], family=p.get("description") or p["name"], cpu=p["cpu_type"],
                        vcpu=p["cores"], ram_gb=float(p["memory"]), disk_gb=p["disk"], transfer_tb=round(tb, 1) or None,
                        monthly=round(eur * usd, 2), regions=len(p["prices"]), note="EUR price converted, excl. VAT"))
    return out


def main():
    rows, status = [], {}
    for name, fn in (("Vultr", vultr), ("Linode", linode), ("DigitalOcean", digitalocean), ("Hetzner", hetzner)):
        try:
            got = fn()
            status[name] = "skipped (no token)" if got is None else f"ok {len(got)}"
            rows += got or []
        except Exception as ex:
            status[name] = f"error {type(ex).__name__}: {str(ex)[:120]}"
        print(name, status[name], flush=True)
    for r in rows:
        r["url"] = SITES[r["provider"]]
        r["key"] = f"{r['provider']}|{r['plan']}"
        r["per_vcpu"] = round(r["monthly"] / r["vcpu"], 2) if r["vcpu"] else None
        r["per_gb"] = round(r["monthly"] / r["ram_gb"], 2) if r["ram_gb"] else None
    rows.sort(key=lambda r: r["monthly"])
    update_history("en_vps_history.json", {r["key"]: r["monthly"] for r in rows}, keep_days=365)
    save("en_vps.json", {"checked": dt.datetime.utcnow().strftime("%Y-%m-%d %H:%M"), "status": status, "items": rows})
    print(f"{len(rows)} plans")
    if not rows:
        sys.exit(1)


if __name__ == "__main__":
    main()
