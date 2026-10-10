"""Force N cold starts of a Lambda and report Init Duration / Duration / Max Memory.
usage: python benchmark.py <function-name> [N=30] [action=hash]"""
import base64, json, re, statistics as st, sys, time, uuid
import boto3

lam = boto3.client("lambda")
fn = sys.argv[1]
n = int(sys.argv[2]) if len(sys.argv) > 2 else 30
action = sys.argv[3] if len(sys.argv) > 3 else "hash"

inits, durs, mems = [], [], []
for i in range(n):
    # changing an env var recycles the execution environment => guaranteed cold start
    lam.update_function_configuration(
        FunctionName=fn, Environment={"Variables": {"BUMP": uuid.uuid4().hex}})
    lam.get_waiter("function_updated").wait(FunctionName=fn)
    r = lam.invoke(FunctionName=fn, LogType="Tail", Payload=json.dumps({"action": action}))
    log = base64.b64decode(r["LogResult"]).decode()

    init = re.search(r"Init Duration: ([\d.]+) ms", log)
    dur = re.search(r"\bDuration: ([\d.]+) ms", log)
    mem = re.search(r"Max Memory Used: (\d+) MB", log)
    if init and dur and mem:
        inits.append(float(init[1]))
        durs.append(float(dur[1]))
        mems.append(float(mem[1]))
    time.sleep(0.5)

p99 = lambda x: sorted(x)[max(int(len(x) * 0.99) - 1, 0)]
print(f"{fn} [{action}]: n={len(inits)}")
print(f"  init        mean={st.mean(inits):.0f} ms   p99={p99(inits):.0f} ms")
print(f"  handler     mean={st.mean(durs):.0f} ms")
print(f"  end-to-end  mean={st.mean(inits) + st.mean(durs):.0f} ms")
print(f"  max memory  mean={st.mean(mems):.0f} MB")