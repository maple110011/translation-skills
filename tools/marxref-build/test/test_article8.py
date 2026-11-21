import sys
sys.path.insert(0, '.')
from engine import Engine
import article as A

MD = """# 测试

马克思在《宣言》里写道：“A spectre is haunting Europe, the spectre of communism”。后来在《哥达纲领批判》里又说：“Labor is not the source of all wealth.”

> The proletarians have nothing to lose but their chains. They have a world to win.

这里引用一句无关的话：“the quick brown fox jumps over the lazy dog”。
"""

out, items, st = A.process(MD, Engine())
print("stats", st)
for it in items:
    print(f"  [{it['status']}] 卷{it.get('vol')} 页{it.get('page')} 分{it['score']:.2f} | {it['quote'][:40]}")
    if it["status"] != "unmatched":
        print("      ->", (it["zh"] or "")[:50])
print("\n--- 回填后 ---")
for line in out.splitlines():
    if "【中译" in line:
        print(line[:150])
