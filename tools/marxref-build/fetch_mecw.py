"""按需下载 MECW 英文 HTML（选编卷用）。

作品卷（3—34）整卷下；书信卷（38—50）只下日期能和中文书信对上的，
否则要拉四千多封，没必要。
"""
import os, sys, json, time, subprocess
import concurrent.futures as cf

ROOT = os.path.dirname(os.path.abspath(__file__))
BASE = "https://raw.githubusercontent.com/MARX-ZH-CN/MARX-ZH-CN.github.io/main/en/MECW"


def fetch(job):
    vol, fn = job
    d = os.path.join(ROOT, "raw", f"mecw{vol}")
    os.makedirs(d, exist_ok=True)
    dst = os.path.join(d, fn)
    if os.path.exists(dst) and os.path.getsize(dst) > 400:
        return True
    for _ in range(3):
        subprocess.run(["curl", "-sS", "--max-time", "60", "-o", dst,
                        f"{BASE}/{vol}/{fn}"], capture_output=True)
        if os.path.exists(dst) and os.path.getsize(dst) > 400:
            return True
        time.sleep(0.6)
    return False


def main():
    jobs = []
    for fn in json.load(open(os.path.join(ROOT, "index/dl_works.json"), encoding="utf-8")):
        vol = int(fn[4:6])
        jobs.append((vol, fn))
    for r in json.load(open(os.path.join(ROOT, "index/dl_letters.json"), encoding="utf-8")):
        jobs.append((r["vol"], r["file"]))

    print("待下载", len(jobs), flush=True)
    t0 = time.time()
    ok = fail = 0
    bad = []
    with cf.ThreadPoolExecutor(6) as ex:
        for job, res in zip(jobs, ex.map(fetch, jobs)):
            if res:
                ok += 1
            else:
                fail += 1
                bad.append(job)
            if (ok + fail) % 200 == 0:
                print(f"  {ok+fail}/{len(jobs)}  {time.time()-t0:.0f}s", flush=True)
    print(f"ok {ok}  fail {fail}  {time.time()-t0:.0f}s")
    if bad:
        json.dump([f"{v}/{f}" for v, f in bad],
                  open(os.path.join(ROOT, "index/dl_fail.json"), "w"), ensure_ascii=False)
        print("失败清单 → index/dl_fail.json")


if __name__ == "__main__":
    main()
