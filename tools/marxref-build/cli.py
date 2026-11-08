"""命令行：给英文引文，出中文位置。

用法：
    python cli.py "Force is the midwife of every old society pregnant with a new one."
    type quote.txt | python cli.py        # 或从标准输入读
"""
import sys, os

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from locate_sent import SentLocator


def main():
    root = os.path.dirname(os.path.abspath(__file__))
    q = " ".join(sys.argv[1:]).strip()
    if not q:
        q = sys.stdin.read().strip()
    if not q:
        print("用法: python cli.py \"<英文引文>\"")
        return
    loc = SentLocator(root)
    res = loc.locate(q, topk=3)
    if not res:
        print("未找到候选。")
        return
    print(f"引文: {q[:100]}{'…' if len(q) > 100 else ''}\n")
    for k, r in enumerate(res):
        flag = "★ 最佳" if k == 0 else f"  备选{k}"
        pg = f"第 {r['print_page']} 页" if r.get("print_page") else "页码待核"
        print(f"{flag}  [{r['chapter']}] {pg}  置信度 {r['score']:.2f}"
              f"  (词覆盖 {r['cover']:.2f} / 连续词串 {r['ngram']:.2f} / 跨 {r['span']} 句)")
        print(f"   中文: {r.get('zh') or '（该句未对齐，需人工核）'}")
        if k == 0 and r["evidence"]:
            print(f"   依据: {'; '.join(r['evidence'])}")
        print()
    if res[0].get("unaligned"):
        print("注意：英文引文已定位，但对应中文句未对齐（两边段落划分错开所致），需人工核对。")
    if res[0]["score"] < 0.55:
        print("提示：置信度偏低。这类位置通常是两边段落划分错开所致，建议人工核对。")


if __name__ == "__main__":
    main()
